"""Thread context, comment interaction, and MCP server for the novem platform."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .api_ref import NovemAPI
from .utils import API_ROOT

# Single-letter FQNP type codes to API path plurals
_TYPE_MAP: Dict[str, str] = {
    "p": "plots",
    "g": "grids",
    "m": "mails",
    "d": "docs",
    "j": "jobs",
    "r": "repos",
}


def _split_comment_path(fqnp: str) -> Tuple[str, List[str]]:
    """Split a FQNP into (base, comment_segments).

    Examples:
        "/u/alice/p/myplot/c/@sen~topic/c/@bob~reply"
        -> ("/u/alice/p/myplot", ["@sen~topic", "@bob~reply"])

        "/u/alice/p/myplot" -> ("/u/alice/p/myplot", [])
    """
    parts = fqnp.strip("/").split("/")
    base_parts: List[str] = []
    comment_segs: List[str] = []
    i = 0
    while i < len(parts):
        if parts[i] == "c" and i + 1 < len(parts):
            comment_segs.append(parts[i + 1])
            i += 2
        else:
            base_parts.append(parts[i])
            i += 1
    return "/" + "/".join(base_parts), comment_segs


@dataclass
class ParsedFQNP:
    """Parsed components of a Fully Qualified Name Path."""

    user: Optional[str] = None
    org: Optional[str] = None
    vis_type: Optional[str] = None
    vis_id: Optional[str] = None
    group_name: Optional[str] = None
    group_type: Optional[str] = None  # "org_group" or "user_group"

    @property
    def is_vis(self) -> bool:
        return self.vis_type is not None

    @property
    def is_group(self) -> bool:
        return self.group_name is not None

    @property
    def owner(self) -> str:
        """The owner/namespace identifier (user or org)."""
        return self.user or self.org or ""


def _parse_fqnp(fqnp: str) -> ParsedFQNP:
    """Parse a FQNP into its components.

    Strips /c/ segments before parsing.

    Examples:
        "/u/alice/p/myplot"              -> ParsedFQNP(user="alice", vis_type="plots", vis_id="myplot")
        "/u/alice/grp/mygroup"           -> ParsedFQNP(user="alice", group_name="mygroup", group_type="user_group")
        "/o/myorg/g/mygroup"             -> ParsedFQNP(org="myorg", group_name="mygroup", group_type="org_group")
        "/u/alice/p/myplot/c/@sen~topic" -> ParsedFQNP(user="alice", vis_type="plots", vis_id="myplot")
        "/u/alice"                       -> ParsedFQNP(user="alice")
        "/o/myorg"                       -> ParsedFQNP(org="myorg")
    """
    base, _ = _split_comment_path(fqnp)
    parts = [p for p in base.strip("/").split("/") if p]

    if len(parts) < 2:
        raise ValueError(f"Invalid FQNP: {fqnp}")

    if parts[0] == "u":
        user = parts[1]
        if len(parts) >= 4:
            if parts[2] == "grp":
                return ParsedFQNP(user=user, group_name=parts[3], group_type="user_group")
            if parts[2] in _TYPE_MAP:
                return ParsedFQNP(user=user, vis_type=_TYPE_MAP[parts[2]], vis_id=parts[3])
        return ParsedFQNP(user=user)

    if parts[0] == "o":
        org = parts[1]
        if len(parts) >= 4 and parts[2] == "g":
            return ParsedFQNP(org=org, group_name=parts[3], group_type="org_group")
        return ParsedFQNP(org=org)

    raise ValueError(f"Invalid FQNP prefix: {parts[0]}")


def _gen_slug() -> str:
    """Generate a slug from the current timestamp."""
    return f"r{int(time.time() * 1000) % 10**10}"


# ---------------------------------------------------------------------------
# Tree data structures — mirror the GQL response
# ---------------------------------------------------------------------------


@dataclass
class Comment:
    """A comment in a thread tree."""

    slug: str
    message: str
    creator: str
    depth: int
    replies: List["Comment"] = field(default_factory=list)
    comment_id: Optional[int] = None
    deleted: bool = False
    edited: bool = False
    num_replies: int = 0
    likes: int = 0
    dislikes: int = 0
    my_reaction: Optional[str] = None
    created: str = ""
    updated: str = ""

    @property
    def ref(self) -> str:
        """REST-style reference: @creator~slug."""
        return f"@{self.creator}~{self.slug}"


@dataclass
class Topic:
    """A topic (thread root) on a visualization."""

    slug: str
    message: str
    creator: str
    comments: List[Comment] = field(default_factory=list)
    topic_id: Optional[int] = None
    audience: str = "public"
    status: str = "active"
    num_comments: int = 0
    likes: int = 0
    dislikes: int = 0
    my_reaction: Optional[str] = None
    edited: bool = False
    created: str = ""
    updated: str = ""

    @property
    def ref(self) -> str:
        """REST-style reference: @creator~slug."""
        return f"@{self.creator}~{self.slug}"


def _dict_to_comment(d: Dict[str, Any]) -> Comment:
    """Convert a GQL comment dict to a Comment."""
    return Comment(
        slug=d.get("slug", ""),
        message=d.get("message", "") or "",
        creator=d.get("creator", {}).get("username", ""),
        depth=d.get("depth", 0),
        replies=[_dict_to_comment(r) for r in (d.get("replies") or [])],
        comment_id=d.get("comment_id"),
        deleted=d.get("deleted", False),
        edited=d.get("edited", False),
        num_replies=d.get("num_replies", 0),
        likes=d.get("likes", 0),
        dislikes=d.get("dislikes", 0),
        my_reaction=d.get("my_reaction"),
        created=d.get("created", ""),
        updated=d.get("updated", ""),
    )


def _dict_to_topic(d: Dict[str, Any]) -> Topic:
    """Convert a GQL topic dict to a Topic."""
    return Topic(
        slug=d.get("slug", ""),
        message=d.get("message", "") or "",
        creator=d.get("creator", {}).get("username", ""),
        comments=[_dict_to_comment(c) for c in (d.get("comments") or [])],
        topic_id=d.get("topic_id"),
        audience=d.get("audience", "public"),
        status=d.get("status", "active"),
        num_comments=d.get("num_comments", 0),
        likes=d.get("likes", 0),
        dislikes=d.get("dislikes", 0),
        my_reaction=d.get("my_reaction"),
        edited=d.get("edited", False),
        created=d.get("created", ""),
        updated=d.get("updated", ""),
    )


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------


class Message:
    """A comment or reply to post (kept for backward compatibility)."""

    def __init__(self, text: str) -> None:
        self.text = text


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


class Context(NovemAPI):
    """Thread context for a FQNP.

    Loads the full topic/comment tree from GraphQL and provides navigation
    via /c/ segments in the FQNP.

    Usage::

        # Load full VDE context, focused on a specific comment
        ctx = Context("/u/alice/p/myplot/c/@sen~topic/c/@bob~reply")
        ctx.topics           # all topics on the VDE
        ctx.topic            # the focused Topic (@sen~topic)
        ctx.comment          # the focused Comment (@bob~reply)

        ctx.reply("Thanks!")                     # reply under @bob~reply
        ctx.reply("Great!", title="agreed")      # slug = @me~agreed

        # Async variants
        await ctx.aload()
        print(await ctx.atxt())
        await ctx.areply("Thanks!")
    """

    def __init__(self, fqnp: str, **kwargs: Any) -> None:
        self._fqnp = fqnp
        self._parsed = _parse_fqnp(fqnp)
        _, self._comment_chain = _split_comment_path(fqnp)
        super().__init__(**kwargs)
        self._raw_topics: Optional[List[Dict[str, Any]]] = None
        self._raw_vars: Optional[List[Dict[str, Any]]] = None
        self._topics: Optional[List[Topic]] = None

    # Convenience accessors for backward compat
    @property
    def _user(self) -> str:
        return self._parsed.user or self._parsed.org or ""

    @property
    def _vis_type(self) -> Optional[str]:
        return self._parsed.vis_type

    @property
    def _vis_id(self) -> Optional[str]:
        return self._parsed.vis_id

    @property
    def _threads_base(self) -> str:
        """REST API base path for threads on this resource."""
        p = self._parsed
        me = self._config.get("username", "")

        # Org group: orgs/{org}/groups/{group}/threads
        if p.group_type == "org_group":
            return f"orgs/{p.org}/groups/{p.group_name}/threads"

        # User group: groups/{group}/threads or users/{user}/groups/{group}/threads
        if p.group_type == "user_group":
            prefix = f"users/{p.user}/" if p.user and p.user != me else ""
            return f"{prefix}groups/{p.group_name}/threads"

        # VDE: vis/{type}/{id}/threads or users/{user}/vis/{type}/{id}/threads
        if not p.vis_type or not p.vis_id:
            raise RuntimeError(f"FQNP {self._fqnp} does not reference a visualization or group")
        prefix = f"users/{p.user}/" if p.user and p.user != me else ""
        return f"{prefix}vis/{p.vis_type}/{p.vis_id}/threads"

    # -- Tree access --

    def _load(self) -> None:
        """Lazy-load the topic tree from GQL."""
        if self._raw_topics is not None:
            return
        self._raw_topics, self._raw_vars = self._fetch_raw_topics()
        self._topics = [_dict_to_topic(t) for t in self._raw_topics]

    @property
    def topics(self) -> List[Topic]:
        """All topics on this visualization."""
        self._load()
        assert self._topics is not None
        return self._topics

    @property
    def topic(self) -> Optional[Topic]:
        """The focused topic (first /c/ segment), or None."""
        if not self._comment_chain:
            return None
        ref = self._comment_chain[0]
        for t in self.topics:
            if t.ref == ref:
                return t
        return None

    @property
    def comment(self) -> Optional[Comment]:
        """The deepest focused comment (from /c/ chain), or None."""
        if len(self._comment_chain) < 2:
            return None
        t = self.topic
        if not t:
            return None
        node: Optional[Comment] = None
        comments = t.comments
        for ref in self._comment_chain[1:]:
            for c in comments:
                if c.ref == ref:
                    node = c
                    comments = c.replies
                    break
            else:
                return node
        return node

    # -- Sync interface --

    @property
    def _var_lookup(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Build a var lookup dict from loaded VDE vars."""
        from .cli.gql import _build_var_lookup

        if not self._raw_vars or self._parsed.is_group:
            return None
        return _build_var_lookup(self._raw_vars, self._user, self._vis_type or "", self._vis_id or "")

    @property
    def txt(self) -> str:
        """ANSI-rendered thread listing."""
        from .cli.gql import render_topics

        self._load()
        username = self._config.get("username", "")
        api_root = self._config.get("api_root") or API_ROOT
        session = self._session if hasattr(self, "_session") else None
        return render_topics(
            self._raw_topics or [],
            me=username,
            var_lookup=self._var_lookup,
            session=session,
            api_root=api_root,
        )

    @property
    def ansi(self) -> str:
        """ANSI-rendered thread listing (alias for txt)."""
        return self.txt

    def reply(self, text: str, title: Optional[str] = None) -> None:
        """Post a reply at the current focus point.

        Args:
            text: The message body.
            title: Optional slug for the comment. Auto-generated if omitted.
        """
        self._do_reply(text, title)

    # -- Async interface --

    async def aload(self) -> None:
        """Async: pre-load the topic tree."""
        await asyncio.to_thread(self._load)

    async def atxt(self) -> str:
        """Async: ANSI-rendered thread listing."""
        from .cli.gql import render_topics

        await self.aload()
        username = self._config.get("username", "")
        api_root = self._config.get("api_root") or API_ROOT
        session = self._session if hasattr(self, "_session") else None
        return render_topics(
            self._raw_topics or [],
            me=username,
            var_lookup=self._var_lookup,
            session=session,
            api_root=api_root,
        )

    async def areply(self, text: str, title: Optional[str] = None) -> None:
        """Async: post a reply."""
        await asyncio.to_thread(self._do_reply, text, title)

    # -- Internal --

    def _fetch_raw_topics(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        from .cli.gql import NovemGQL, fetch_group_topics_gql, fetch_vde_topics_gql

        gql_kwargs: Dict[str, Any] = {}
        if hasattr(self, "token"):
            gql_kwargs["token"] = self.token
        if hasattr(self, "_api_root"):
            gql_kwargs["api_root"] = self._api_root

        gql = NovemGQL(**gql_kwargs)
        p = self._parsed

        if p.is_group:
            topics = fetch_group_topics_gql(
                gql,
                group_name=p.group_name or "",
                group_type=p.group_type or "",
                parent=p.org or p.user or "",
            )
            return topics, []

        return fetch_vde_topics_gql(gql, self._vis_type or "", self._vis_id or "", author=self._user)

    def _do_reply(self, text: str, title: Optional[str] = None) -> None:
        base = self._threads_base
        username = self._config.get("username", "")
        slug = title or _gen_slug()
        my_ref = f"@{username}~{slug}"

        # Build path from /c/ chain
        if self._comment_chain:
            path = f"{base}/{self._comment_chain[0]}"
            for seg in self._comment_chain[1:]:
                path += f"/comments/{seg}"
            path += f"/comments/{my_ref}"
        else:
            # No focus — reply to latest topic, or create new one
            self._load()
            if self._topics:
                path = f"{base}/{self._topics[0].ref}/comments/{my_ref}"
            else:
                path = f"{base}/{my_ref}"

        self.create(path)
        self.write(f"{path}/msg", text)


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


def _check_mcp_deps() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP

        return FastMCP
    except ImportError:
        raise ImportError('The "mcp" extra is required. Install with: pip install novem[mcp]')


def _fmt_comment(c: Comment, indent: int = 0) -> str:
    """Plain-text comment formatter (no ANSI — intended for LLM consumption)."""
    prefix = "  " * indent
    header = f"{prefix}@{c.creator} ({c.ref})"
    if c.edited:
        header += " [edited]"
    if c.deleted:
        header += " [deleted]"
    lines = [header]
    for line in c.message.splitlines():
        lines.append(f"{prefix}  {line}")
    for r in c.replies:
        lines.append(_fmt_comment(r, indent + 1))
    return "\n".join(lines)


def _fmt_topic(t: Topic) -> str:
    """Plain-text topic formatter (no ANSI — intended for LLM consumption)."""
    header = f"Topic {t.ref} by @{t.creator} [{t.status}]"
    if t.num_comments:
        header += f" ({t.num_comments} comments)"
    lines = [header]
    for line in t.message.splitlines():
        lines.append(f"  {line}")
    for c in t.comments:
        lines.append(_fmt_comment(c, 1))
    return "\n".join(lines)


def _fmt_topics(topics: List[Topic]) -> str:
    if not topics:
        return "No topics found."
    return "\n\n".join(_fmt_topic(t) for t in topics)


def MCP(fqnp: str, **kwargs: Any) -> Any:
    """Create an MCP server scoped to a comment FQNP.

    The returned server exposes tools for exploring the conversation tree
    and replying at the mention location.

    Usage::

        from novem.comments import MCP

        server = MCP("/u/alice/p/myplot/c/@sen~topic/c/@bob~reply")
        server.run()  # stdio transport

    Args:
        fqnp: Fully Qualified Name Path, e.g.
              ``/u/alice/p/myplot/c/@sen~topic/c/@bob~reply``
        **kwargs: Passed through to :class:`Context`
                  (``config_profile``, ``token``, ``config_path``, …).

    Returns:
        A ``FastMCP`` server instance.
    """
    FastMCP = _check_mcp_deps()

    parsed = _parse_fqnp(fqnp)
    ctx = Context(fqnp, **kwargs)

    # Build a short human-readable label for the server
    if parsed.is_vis:
        label = f"{parsed.vis_type}/{parsed.vis_id}"
    elif parsed.is_group:
        label = f"group/{parsed.group_name}"
    else:
        label = parsed.owner
    server = FastMCP(f"novem-comments ({label})")

    # -- Anthropic SDK helper -------------------------------------------

    async def api_tools() -> List[Dict[str, Any]]:
        """Return tools in Anthropic API format."""
        mcp_tools = await server.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in mcp_tools
        ]

    server.api_tools = api_tools  # type: ignore[attr-defined]

    # -- read-only tools ------------------------------------------------

    @server.tool()
    def get_thread_context() -> str:
        """Get the full conversation thread as plain text.

        Returns every topic and its nested comments for the visualization
        or group that this server is scoped to.
        """
        return _fmt_topics(ctx.topics)

    @server.tool()
    def list_topics() -> str:
        """List topics with a one-line summary each.

        Use this for an overview before drilling into a specific topic.
        """
        lines: List[str] = []
        for t in ctx.topics:
            preview = t.message.replace("\n", " ")[:120]
            lines.append(f"- {t.ref} by @{t.creator} [{t.status}] ({t.num_comments} comments): {preview}")
        return "\n".join(lines) or "No topics found."

    @server.tool()
    def get_topic(ref: str) -> str:
        """Get a single topic and its full comment tree.

        Args:
            ref: Topic reference, e.g. ``@alice~my-topic``.
        """
        for t in ctx.topics:
            if t.ref == ref:
                return _fmt_topic(t)
        return f"Topic {ref} not found."

    @server.tool()
    def get_vis_info() -> str:
        """Get metadata about the visualization this thread belongs to.

        Returns type, owner, and id.  Only available when the FQNP
        points to a visualization (plot, grid, mail, …).
        """
        if not parsed.is_vis:
            return "This FQNP does not reference a visualization."
        lines = [
            f"type: {parsed.vis_type}",
            f"id: {parsed.vis_id}",
            f"owner: {parsed.owner}",
        ]
        # Try to read title/caption from the API
        try:
            prefix = f"users/{parsed.user}/" if parsed.user else ""
            base = f"{prefix}vis/{parsed.vis_type}/{parsed.vis_id}"
            for prop in ("name", "caption", "description"):
                val = ctx.read(f"{base}/config/{prop}")
                if val:
                    lines.append(f"{prop}: {val}")
        except Exception:
            pass
        return "\n".join(lines)

    # -- write tool -----------------------------------------------------

    @server.tool()
    def reply(text: str) -> str:
        """Reply to the comment or topic that triggered this context.

        The reply is posted at the deepest /c/ segment in the FQNP —
        i.e. directly where the mention happened.

        Args:
            text: The message body (plain text or markdown).
        """
        ctx.reply(text)
        return "Reply posted."

    return server
