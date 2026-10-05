"""GraphQL topic fetching and ANSI rendering behind novem.comments.

Moved here from the old Python CLI (novem.cli.gql).
"""

import datetime
import functools
import re
import shutil
import textwrap
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from .utils import API_ROOT, cl, colors, get_current_config, parse_api_datetime


def _get_gql_endpoint(api_root: str) -> str:
    """Convert REST API root to GraphQL endpoint by replacing /v1 with /gql."""
    # Remove trailing slash if present, then replace /v1 with /gql
    api_root = api_root.rstrip("/")
    return re.sub(r"/v\d+$", "/gql", api_root)


class NovemGQL:
    """GraphQL client for the topic queries."""

    def __init__(self, **connection: Any) -> None:
        # ``connection`` is the curated set of connection options (token,
        # api_root, profile, config_path, …)
        _, config = get_current_config(**connection)
        self._config = config
        self._session = requests.Session()
        self._session.request = functools.partial(  # type: ignore[method-assign]
            self._session.request, timeout=(10, 120)
        )

        token = config.get("token")
        if token:
            self._session.headers.update({"Authorization": f"Bearer {token}"})

        api_root = config.get("api_root") or API_ROOT
        self._endpoint = _get_gql_endpoint(api_root)

    def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query and return the result."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self._session.post(self._endpoint, json=payload)
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            raise Exception(f"GraphQL error: {result['errors']}")

        return result.get("data", {})


_COMMENT_FIELDS = """
    comment_id
    slug
    message
    depth
    deleted
    edited
    num_replies
    likes
    dislikes
    my_reaction
    created
    updated
    creator { username }
    mentions { nonce user { username } }
"""


def _build_comment_fragment(depth: int = 4) -> str:
    """Build a nested comment/replies fragment to the given depth."""
    fragment = _COMMENT_FIELDS
    for _ in range(depth):
        fragment = f"""
    {_COMMENT_FIELDS}
    replies {{{fragment}
    }}"""
    return fragment


_TOPICS_QUERY_TPL = """
query GetTopics($id: ID!, $author: String) {{
  me {{ username }}
  {vis_type}(id: $id, author: $author) {{
    vars {{ id value format type threshold }}
    topics {{
      topic_id
      slug
      message
      audience
      status
      num_comments
      likes
      dislikes
      my_reaction
      edited
      created
      updated
      creator {{ username }}
      mentions {{ nonce user {{ username }} }}
      comments {{{comment_fragment}
      }}
    }}
  }}
}}
"""


def _build_topics_query(vis_type: str, depth: int = 3) -> str:
    """Build a topics query for a given vis type (plots, grids, mails, etc.)."""
    comment_fragment = _build_comment_fragment(depth)
    return _TOPICS_QUERY_TPL.format(vis_type=vis_type, comment_fragment=comment_fragment)


def _has_truncated_replies(comments: List[Dict[str, Any]]) -> bool:
    """Check if any comment has num_replies > 0 but empty replies list."""
    for c in comments:
        replies = c.get("replies", []) or []
        if c.get("num_replies", 0) > 0 and not replies:
            return True
        if replies and _has_truncated_replies(replies):
            return True
    return False


def _fetch_vde_topics_gql(
    gql: NovemGQL, vis_type: str, vis_id: str, author: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """Fetch topics, comments, VDE vars, and current username. Returns (topics, vars, username)."""
    variables: Dict[str, Any] = {"id": vis_id}
    if author:
        variables["author"] = author

    depth = 3
    max_depth = 12
    topics: List[Dict[str, Any]] = []
    vde_vars: List[Dict[str, Any]] = []
    username = ""

    while depth <= max_depth:
        query = _build_topics_query(vis_type, depth=depth)
        data = gql._query(query, variables)
        username = (data.get("me") or {}).get("username", "")
        items = data.get(vis_type, [])
        if not items:
            return [], [], username
        topics = items[0].get("topics", [])
        vde_vars = items[0].get("vars", []) or []

        # Check if any topic has truncated comment trees
        truncated = any(_has_truncated_replies(t.get("comments", [])) for t in topics)
        if not truncated:
            break
        depth += 3

    return topics, vde_vars, username


# ---------------------------------------------------------------------------
# Group topics (org groups and user groups)
# ---------------------------------------------------------------------------

_GROUP_TOPICS_QUERY_TPL = """
query GetGroupTopics($name: String!, $type: GroupType!, $parent_group: String) {{
  me {{ username }}
  groups(name: $name, type: $type, parent_group: $parent_group) {{
    topics {{
      topic_id
      slug
      message
      audience
      status
      num_comments
      likes
      dislikes
      my_reaction
      edited
      created
      updated
      creator {{ username }}
      mentions {{ nonce user {{ username }} }}
      comments {{{comment_fragment}
      }}
    }}
  }}
}}
"""


def _build_group_topics_query(depth: int = 3) -> str:
    """Build a topics query for a group."""
    comment_fragment = _build_comment_fragment(depth)
    return _GROUP_TOPICS_QUERY_TPL.format(comment_fragment=comment_fragment)


def _fetch_group_topics_gql(
    gql: NovemGQL, group_name: str, group_type: str, parent: str
) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch topics and comments for a group. Returns (topics, username)."""
    variables: Dict[str, Any] = {
        "name": group_name,
        "type": group_type,
        "parent_group": parent,
    }

    depth = 3
    max_depth = 12
    topics: List[Dict[str, Any]] = []
    username = ""

    while depth <= max_depth:
        query = _build_group_topics_query(depth=depth)
        data = gql._query(query, variables)
        username = (data.get("me") or {}).get("username", "")
        groups = data.get("groups", [])
        if not groups:
            return [], username
        topics = groups[0].get("topics", [])

        truncated = any(_has_truncated_replies(t.get("comments", [])) for t in topics)
        if not truncated:
            break
        depth += 3

    return topics, username


# ---------------------------------------------------------------------------
# Message processing: mentions, VDE variable embeds, and markdown rendering
# ---------------------------------------------------------------------------

_VDE_VAR_RE = re.compile(r"\{(/u/[A-Za-z0-9_.-]+/[pgmdrj]/[A-Za-z0-9_.-]+/v/[A-Za-z0-9_.-]+)\}")
_MENTION_RE = re.compile(r"@(_m[a-f0-9]{16})")

# ANSI attribute codes (use specific on/off to allow nesting)
_ANSI_BOLD_ON = "\033[1m"
_ANSI_BOLD_OFF = "\033[22m"
_ANSI_ITALIC_ON = "\033[3m"
_ANSI_ITALIC_OFF = "\033[23m"
_ANSI_STRIKE_ON = "\033[9m"
_ANSI_STRIKE_OFF = "\033[29m"
_ANSI_UNDERLINE_ON = "\033[4m"
_ANSI_UNDERLINE_OFF = "\033[24m"
_ANSI_DIM_ON = "\033[2m"
_ANSI_DIM_OFF = "\033[22m"
# 256-color backgrounds for pills
_ANSI_BG_GREEN = "\033[48;5;22m"
_ANSI_BG_RED = "\033[48;5;52m"
_ANSI_BG_GRAY = "\033[48;5;236m"
_ANSI_BG_OFF = "\033[49m"
_ANSI_FG_OFF = "\033[39m"

# Inline markdown regex — single pass, mirrors webapp's inlineRe
# Groups: 1=code, 2=bold, 3=strike, 4=italic, 5+6=link text+url,
#         7=mention nonce, 8=superscript, 9=subscript, 10=vde var
_INLINE_RE = re.compile(
    r"`([^`]+)`"  # 1: inline code
    r"|\*\*(.+?)\*\*"  # 2: bold
    r"|~~(.+?)~~"  # 3: strikethrough
    r"|\*(.+?)\*"  # 4: italic
    r"|\[([^\]]+)\]\(((?:https?://|/)[^\s)]+)\)"  # 5,6: link
    r"|@(_m[a-f0-9]{16})"  # 7: mention
    r"|\^([^^]+?)\^"  # 8: superscript
    r"|~([^~]+?)~"  # 9: subscript
    r"|\{(/u/[A-Za-z0-9_.-]+/[pgmdrj]/[A-Za-z0-9_.-]+/v/[A-Za-z0-9_.-]+)\}"  # 10: vde var
)


def _resolve_mentions(message: str, mentions: Optional[List[Dict[str, Any]]]) -> str:
    """Replace @_m<nonce> placeholders with @username."""
    if not mentions:
        return message
    nonce_map = {}
    for m in mentions:
        nonce = m.get("nonce", "")
        username = (m.get("user") or {}).get("username", "")
        if nonce and username:
            nonce_map[nonce] = username

    def _repl(match: re.Match) -> str:  # type: ignore[type-arg]
        nonce = match.group(1)
        username = nonce_map.get(nonce)
        return f"@{username}" if username else match.group(0)

    return _MENTION_RE.sub(_repl, message)


def _format_var_value(
    value: Optional[str], fmt: Optional[str], var_type: Optional[str], threshold: Optional[str]
) -> str:
    """Format a VDE variable value according to its format string.

    Mirrors the webapp's formatVar.ts logic.
    """
    if value is None:
        return ""

    # Text passthrough
    if fmt == "st" or var_type == "text":
        return value

    # Date passthrough
    if fmt and fmt.startswith("%"):
        return value

    try:
        num = float(value)
    except (ValueError, TypeError):
        return value

    is_percent = bool(fmt and "%" in fmt)
    show_sign = bool(fmt and "+" in fmt)
    use_comma = bool(fmt and "," in fmt)

    # Parse precision from format string
    precision = 0
    if fmt:
        # Money: "$2m" → 2
        money_match = re.match(r"^([$€£])(\d+)m$", fmt)
        if money_match:
            symbol = money_match.group(1)
            precision = int(money_match.group(2))
            display = abs(num)
            formatted = f"{display:.{precision}f}"
            formatted = _comma_group(formatted)
            if num < 0:
                formatted = "\u2212" + formatted
            elif show_sign:
                formatted = "+" + formatted
            return f"{symbol}{formatted}"

        # .Nf or .N%
        prec_match = re.search(r"\.(\d+)", fmt)
        if prec_match:
            precision = int(prec_match.group(1))

    display_num = num * 100 if is_percent else num
    formatted = f"{abs(display_num):.{precision}f}"

    if use_comma:
        formatted = _comma_group(formatted)

    if display_num < 0:
        formatted = "\u2212" + formatted
    elif show_sign and display_num >= 0:
        formatted = "+" + formatted

    if is_percent:
        formatted += "%"

    return formatted


def _comma_group(s: str) -> str:
    """Add thousands separators to a formatted number string."""
    parts = s.split(".")
    digits = parts[0]
    grouped = ""
    for i, ch in enumerate(reversed(digits)):
        if i > 0 and i % 3 == 0:
            grouped = "," + grouped
        grouped = ch + grouped
    parts[0] = grouped
    return ".".join(parts)


def _render_vde_var_ansi(
    value: Optional[str],
    fmt: Optional[str],
    var_type: Optional[str],
    threshold: Optional[str],
) -> str:
    """Render a VDE variable as an ANSI-colored inline pill."""
    formatted = _format_var_value(value, fmt, var_type, threshold)
    if not formatted:
        return ""

    # Direction indicator for relative type — colored pill with triangle
    if var_type == "relative" and value is not None and threshold is not None:
        try:
            val = float(value)
            thresh = float(threshold)
            if val > thresh:
                return f"{_ANSI_BG_GREEN}{cl.OKGREEN} \u25b2 {formatted} {cl.ENDC}"
            elif val < thresh:
                return f"{_ANSI_BG_RED}{cl.FAIL} \u25bc {formatted} {cl.ENDC}"
            else:
                return f"{_ANSI_BG_GRAY}\033[97m \u25b6 {formatted} {cl.ENDC}"
        except (ValueError, TypeError):
            pass

    # Non-relative vars — subtle gray pill
    return f"{_ANSI_BG_GRAY}\033[97m {formatted} {cl.ENDC}"


def _build_var_lookup(
    vde_vars: List[Dict[str, Any]], user: str, vis_type: str, vis_id: str
) -> Dict[str, Dict[str, Any]]:
    """Build a lookup dict from VDE var FQNP path to var data.

    Maps e.g. "/u/alice/p/myplot/v/revenue" -> {"value": "0.15", "format": "+,.1%", ...}
    """
    # Reverse the type map: "plots" -> "p", "grids" -> "g", etc.
    type_to_code = {"plots": "p", "grids": "g", "mails": "m", "docs": "d", "jobs": "j", "repos": "r"}
    code = type_to_code.get(vis_type, "")
    lookup: Dict[str, Dict[str, Any]] = {}
    for v in vde_vars:
        var_id = v.get("id", "")
        if var_id:
            path = f"/u/{user}/{code}/{vis_id}/v/{var_id}"
            lookup[path] = v
    return lookup


_TYPE_CODE_TO_GQL = {"p": "plots", "g": "grids", "m": "mails", "d": "docs", "j": "jobs", "r": "repos"}


def _collect_var_refs(topics: List[Dict[str, Any]]) -> Set[str]:
    """Scan all messages in topics/comments for VDE var FQNP paths."""
    refs: Set[str] = set()

    def _scan(msg: Optional[str]) -> None:
        if msg:
            refs.update(m.group(1) for m in _VDE_VAR_RE.finditer(msg))

    for t in topics:
        _scan(t.get("message"))
        _scan_comments(t.get("comments") or [], refs)
    return refs


def _scan_comments(comments: List[Dict[str, Any]], refs: Set[str]) -> None:
    for c in comments:
        msg = c.get("message")
        if msg:
            refs.update(m.group(1) for m in _VDE_VAR_RE.finditer(msg))
        _scan_comments(c.get("replies") or [], refs)


def _fetch_all_cross_vars(
    session: requests.Session,
    api_root: str,
    var_paths: Set[str],
    existing_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Fetch vars for all referenced VDEs in a single aliased GQL query.

    Groups var paths by VDE, skips VDEs already in existing_lookup,
    builds one GQL query with aliases, returns a full var_path -> var_data lookup.
    """
    # Group by VDE (user/type_code/vis_id), skip paths already resolved
    vde_to_alias: Dict[str, str] = {}  # "user/type_code/vis_id" -> alias
    vde_info: Dict[str, Tuple[str, str, str, str]] = {}  # alias -> (user, vis_type, vis_id, type_code)

    for path in var_paths:
        if existing_lookup and path in existing_lookup:
            continue
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) != 6 or parts[0] != "u" or parts[4] != "v":
            continue
        user, type_code, vis_id = parts[1], parts[2], parts[3]
        vis_type = _TYPE_CODE_TO_GQL.get(type_code)
        if not vis_type:
            continue
        vde_key = f"{user}/{type_code}/{vis_id}"
        if vde_key not in vde_to_alias:
            alias = f"vde_{len(vde_to_alias)}"
            vde_to_alias[vde_key] = alias
            vde_info[alias] = (user, vis_type, vis_id, type_code)

    if not vde_info:
        return {}

    # Build single aliased GQL query
    fragments: List[str] = []
    for alias, (user, vis_type, vis_id, _) in vde_info.items():
        fragments.append(
            f'  {alias}: {vis_type}(id: "{vis_id}", author: "{user}") {{ vars {{ id value format type threshold }} }}'
        )
    query = "query {\n" + "\n".join(fragments) + "\n}"

    gql_endpoint = _get_gql_endpoint(api_root)
    try:
        resp = session.post(gql_endpoint, json={"query": query})
        resp.raise_for_status()
        result = resp.json()
        data = result.get("data", {})
    except Exception:
        return {}

    # Build lookup from results
    lookup: Dict[str, Dict[str, Any]] = {}
    for alias, (user, vis_type, vis_id, type_code) in vde_info.items():
        items = data.get(alias)
        if not items:
            continue
        # GQL returns either a list of VDEs or a single VDE object
        vde_obj = items[0] if isinstance(items, list) else items
        for v in vde_obj.get("vars", []) or []:
            var_id = v.get("id", "")
            if var_id:
                fqnp = f"/u/{user}/{type_code}/{vis_id}/v/{var_id}"
                lookup[fqnp] = v

    return lookup


def _render_inline_ansi(
    text: str,
    mention_map: Optional[Dict[str, str]] = None,
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Render inline markdown elements to ANSI escape codes.

    Handles: bold, italic, strikethrough, inline code, links,
    mentions, superscript, subscript, and VDE variable embeds.
    """
    if not text:
        return text

    parts: List[str] = []
    last_end = 0

    for m in _INLINE_RE.finditer(text):
        # Append plain text before this match
        if m.start() > last_end:
            parts.append(text[last_end : m.start()])

        if m.group(1):  # inline code
            parts.append(f"{_ANSI_BG_GRAY}\033[37m {m.group(1)} {cl.ENDC}")
        elif m.group(2):  # bold
            inner = _render_inline_ansi(m.group(2), mention_map, var_lookup)
            parts.append(f"{_ANSI_BOLD_ON}{inner}{_ANSI_BOLD_OFF}")
        elif m.group(3):  # strikethrough
            inner = _render_inline_ansi(m.group(3), mention_map, var_lookup)
            parts.append(f"{_ANSI_STRIKE_ON}{inner}{_ANSI_STRIKE_OFF}")
        elif m.group(4):  # italic
            inner = _render_inline_ansi(m.group(4), mention_map, var_lookup)
            parts.append(f"{_ANSI_ITALIC_ON}{inner}{_ANSI_ITALIC_OFF}")
        elif m.group(5):  # link [text](url)
            link_text = _render_inline_ansi(m.group(5), mention_map, var_lookup)
            url = m.group(6)
            parts.append(f"{_ANSI_UNDERLINE_ON}{link_text}{_ANSI_UNDERLINE_OFF}")
            parts.append(f" {cl.FGGRAY}({url}){cl.ENDC}")
        elif m.group(7):  # mention @_m<nonce>
            nonce = m.group(7)
            username = (mention_map or {}).get(nonce)
            if username:
                parts.append(f"{cl.OKCYAN}@{username}{cl.ENDC}")
            else:
                parts.append(m.group(0))
        elif m.group(8):  # superscript
            parts.append(m.group(8))
        elif m.group(9):  # subscript
            parts.append(m.group(9))
        elif m.group(10):  # VDE var embed
            path = m.group(10)
            var_data = (var_lookup or {}).get(path)
            if var_data:
                parts.append(
                    _render_vde_var_ansi(
                        var_data.get("value"),
                        var_data.get("format"),
                        var_data.get("type"),
                        var_data.get("threshold"),
                    )
                )
            else:
                parts.append(f"{cl.FGGRAY}{path}{cl.ENDC}")

        last_end = m.end()

    # Trailing text
    if last_end < len(text):
        parts.append(text[last_end:])

    return "".join(parts)


def _build_mention_map(mentions: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, str]]:
    """Build nonce -> username map from mentions list."""
    if not mentions:
        return None
    result: Dict[str, str] = {}
    for m in mentions:
        nonce = m.get("nonce", "")
        username = (m.get("user") or {}).get("username", "")
        if nonce and username:
            result[nonce] = username
    return result or None


def _render_message_lines(
    message: str,
    prefix: str,
    width: int,
    mentions: Optional[List[Dict[str, Any]]] = None,
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    """Render a message with markdown, mentions, and VDE vars into prefixed lines.

    Handles block-level elements (code blocks, blockquotes, lists, headings, hr)
    and inline elements (bold, italic, code, strikethrough, links, mentions, vars).
    """
    if not message:
        return []

    mention_map = _build_mention_map(mentions)
    indent_width = _visible_len(prefix)
    available = max(20, width - indent_width)
    lines: List[str] = []
    src_lines = message.split("\n")
    i = 0

    while i < len(src_lines):
        line = src_lines[i]

        # --- Fenced code block ---
        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < len(src_lines) and not src_lines[i].startswith("```"):
                code_lines.append(src_lines[i])
                i += 1
            if i < len(src_lines):
                i += 1  # skip closing ```

            # Render code block: gray background, dim language label
            if lang:
                lines.append(f"{prefix}{_ANSI_BG_GRAY}\033[37m {lang} {cl.ENDC}")
            for cl_line in code_lines:
                lines.append(f"{prefix}{_ANSI_BG_GRAY}\033[37m {cl_line:{available - 1}}{cl.ENDC}")
            continue

        # --- Heading ---
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = _render_inline_ansi(heading_match.group(2), mention_map, var_lookup)
            if level <= 2:
                lines.append(f"{prefix}{_ANSI_BOLD_ON}{cl.OKCYAN}{text}{cl.ENDC}")
            else:
                lines.append(f"{prefix}{_ANSI_BOLD_ON}{text}{_ANSI_BOLD_OFF}")
            i += 1
            continue

        # --- Horizontal rule ---
        if re.match(r"^---+\s*$", line):
            rule = "\u2500" * min(available, 40)
            lines.append(f"{prefix}{cl.FGGRAY}{rule}{cl.ENDC}")
            i += 1
            continue

        # --- Blockquote ---
        if line.startswith("> ") or line == ">":
            quote_lines: List[str] = []
            while i < len(src_lines) and (src_lines[i].startswith("> ") or src_lines[i] == ">"):
                quote_lines.append(re.sub(r"^>\s?", "", src_lines[i]))
                i += 1
            quote_prefix = f"{prefix}{cl.FGGRAY}\u2502{cl.ENDC} "
            for ql in quote_lines:
                rendered = _render_inline_ansi(ql, mention_map, var_lookup)
                lines.extend(_wrap_ansi_text(rendered, quote_prefix, width))
            continue

        # --- Unordered list ---
        if re.match(r"^[-*]\s", line):
            while i < len(src_lines) and re.match(r"^[-*]\s", src_lines[i]):
                item_text = src_lines[i][2:]
                rendered = _render_inline_ansi(item_text, mention_map, var_lookup)
                bullet_prefix = f"{prefix}\u2022 "
                cont_prefix = f"{prefix}  "
                wrapped = _wrap_ansi_text(rendered, cont_prefix, width)
                if wrapped:
                    wrapped[0] = (
                        f"{bullet_prefix}{rendered}"
                        if len(wrapped) == 1
                        else bullet_prefix + wrapped[0][len(cont_prefix) :]
                    )
                    lines.extend(wrapped)
                else:
                    lines.append(bullet_prefix)
                i += 1
            continue

        # --- Blank line ---
        if not line.strip():
            lines.append(prefix)
            i += 1
            continue

        # --- Paragraph (default) ---
        rendered = _render_inline_ansi(line, mention_map, var_lookup)
        lines.extend(_wrap_ansi_text(rendered, prefix, width))
        i += 1

    return lines


def _wrap_ansi_text(text: str, prefix: str, width: int) -> List[str]:
    """Wrap ANSI-formatted text to fit within width, prepending prefix.

    Uses _visible_len to handle ANSI escape codes correctly.
    Falls back to textwrap on the plain-text version, then re-applies
    the ANSI codes line by line.
    """
    indent_width = _visible_len(prefix)
    available = max(20, width - indent_width)

    # For short text that fits, just return it directly
    if _visible_len(text) <= available:
        return [f"{prefix}{text}"]

    # Strip ANSI for wrapping, then re-render each wrapped line
    plain = re.sub(r"\033\[[0-9;]*m", "", text)
    wrapped = textwrap.wrap(plain, width=available) or [""]

    # If the text has no ANSI codes, simple case
    if plain == text:
        return [f"{prefix}{wl}" for wl in wrapped]

    # Re-render: for each wrapped plain line, find matching portion in original
    # and extract with ANSI codes intact
    result: List[str] = []
    src_pos = 0
    for wl in wrapped:
        # Find where this wrapped line starts in the plain text
        plain_idx = plain.find(wl, src_pos)
        if plain_idx == -1:
            result.append(f"{prefix}{wl}")
            continue

        # Map plain_idx back to position in ANSI text
        ansi_start = _plain_to_ansi_pos(text, plain_idx)
        ansi_end = _plain_to_ansi_pos(text, plain_idx + len(wl))
        segment = text[ansi_start:ansi_end]
        result.append(f"{prefix}{segment}")
        src_pos = plain_idx + len(wl)

    return result


def _plain_to_ansi_pos(ansi_text: str, plain_pos: int) -> int:
    """Map a position in plain text to position in ANSI-coded text."""
    ansi_re = re.compile(r"\033\[[0-9;]*m")
    plain_count = 0
    i = 0
    while i < len(ansi_text) and plain_count < plain_pos:
        m = ansi_re.match(ansi_text, i)
        if m:
            i = m.end()
        else:
            plain_count += 1
            i += 1
    # Skip any trailing ANSI codes at the boundary
    while i < len(ansi_text):
        m = ansi_re.match(ansi_text, i)
        if m:
            i = m.end()
        else:
            break
    return i


# Keep these for backward compatibility and testing
def _process_message(
    message: str,
    mentions: Optional[List[Dict[str, Any]]] = None,
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Process a message: resolve mentions and render VDE variable embeds."""
    if not message:
        return message

    mention_map = _build_mention_map(mentions)
    return _render_inline_ansi(message, mention_map, var_lookup)


def _relative_time(dt: datetime.datetime) -> str:
    """Return a human-friendly relative time string."""
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    return dt.strftime("%b %d, %Y")


def _visible_len(s: str) -> int:
    """Return the visible length of a string, ignoring ANSI escape codes."""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def _wrap_text(text: str, prefix: str, width: int) -> List[str]:
    """Wrap text to fit within width, prepending prefix to each line."""
    indent_width = _visible_len(prefix)
    available = width - indent_width
    if available < 20:
        available = 20

    result: List[str] = []
    for line in text.splitlines():
        if not line:
            result.append(prefix)
        else:
            wrapped = textwrap.wrap(line, width=available) or [""]
            for wl in wrapped:
                result.append(f"{prefix}{wl}")
    return result


def _get_term_width() -> int:
    """Get terminal width, capped at 120."""
    return min(120, shutil.get_terminal_size().columns)


def _render_comment(
    comment: Dict[str, Any],
    prefix: str,
    connector: str,
    child_prefix: str,
    width: int = 0,
    me: str = "",
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Render a single comment and its replies as a tree."""
    if not width:
        width = _get_term_width()

    lines: List[str] = []

    username = comment.get("creator", {}).get("username", "?")
    message = comment.get("message", "") or ""
    mentions = comment.get("mentions")
    deleted = comment.get("deleted", False)
    edited = comment.get("edited", False)
    created_str = comment.get("created", "")

    # Timestamp
    ts = ""
    dt = parse_api_datetime(created_str)
    if dt:
        ts = _relative_time(dt)

    # Markers
    markers: List[str] = []
    if edited:
        markers.append("edited")
    if deleted:
        markers.append("deleted")
    marker_str = f" {cl.FGGRAY}({', '.join(markers)}){cl.ENDC}" if markers else ""

    # Reactions
    reactions: List[str] = []
    likes = comment.get("likes", 0)
    dislikes = comment.get("dislikes", 0)
    if likes:
        reactions.append(f"+{likes}")
    if dislikes:
        reactions.append(f"-{dislikes}")
    reaction_str = f" {cl.FGGRAY}[{' '.join(reactions)}]{cl.ENDC}" if reactions else ""

    # Header line
    user_color = cl.WARNING if me and username == me else cl.OKCYAN
    header = (
        f"{prefix}{connector}"
        f"{user_color}@{username}{cl.ENDC}"
        f" {cl.FGGRAY}·{cl.ENDC} "
        f"{cl.FGGRAY}{ts}{cl.ENDC}"
        f"{marker_str}{reaction_str}"
    )
    lines.append(header)

    # Message body
    body_prefix = f"{prefix}{child_prefix}"
    if deleted:
        lines.append(f"{body_prefix}{cl.FGGRAY}[deleted]{cl.ENDC}")
    elif message:
        lines.extend(_render_message_lines(message, body_prefix, width, mentions, var_lookup))

    # Replies
    replies = comment.get("replies", []) or []
    for i, reply in enumerate(replies):
        is_last = i == len(replies) - 1
        rc = "└ " if is_last else "├ "
        rp = "  " if is_last else "│ "
        lines.append(
            _render_comment(
                reply,
                f"{prefix}{child_prefix}",
                rc,
                rp,
                width,
                me=me,
                var_lookup=var_lookup,
            )
        )

    return "\n".join(lines)


def render_topics(
    topics: List[Dict[str, Any]],
    me: str = "",
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    session: Optional[requests.Session] = None,
    api_root: str = "",
) -> str:
    """Render a list of topics with their comment trees."""
    colors()

    if not topics:
        return f"{cl.FGGRAY}No topics{cl.ENDC}"

    # Scan messages for cross-VDE var references and batch-fetch in one GQL call
    if session and api_root:
        var_refs = _collect_var_refs(topics)
        if var_refs:
            cross_vars = _fetch_all_cross_vars(session, api_root, var_refs, var_lookup)
            if cross_vars:
                var_lookup = dict(var_lookup or {}, **cross_vars)

    width = _get_term_width()
    parts: List[str] = []

    for topic in topics:
        lines: List[str] = []

        username = topic.get("creator", {}).get("username", "?")
        message = topic.get("message", "") or ""
        mentions = topic.get("mentions")
        audience = topic.get("audience", "")
        status = topic.get("status", "")
        num_comments = topic.get("num_comments", 0)
        edited = topic.get("edited", False)
        created_str = topic.get("created", "")

        # Timestamp
        ts = ""
        dt = parse_api_datetime(created_str)
        if dt:
            ts = _relative_time(dt)

        # Metadata tags
        tags: List[str] = []
        if audience:
            tags.append(audience)
        if status and status != "active":
            tags.append(status)
        tag_str = f" {cl.FGGRAY}({', '.join(tags)}){cl.ENDC}" if tags else ""

        # Reactions
        reactions: List[str] = []
        likes = topic.get("likes", 0)
        dislikes = topic.get("dislikes", 0)
        if likes:
            reactions.append(f"+{likes}")
        if dislikes:
            reactions.append(f"-{dislikes}")
        reaction_str = f" {cl.FGGRAY}[{' '.join(reactions)}]{cl.ENDC}" if reactions else ""

        edited_str = f" {cl.FGGRAY}(edited){cl.ENDC}" if edited else ""

        comment_count = f" {cl.FGGRAY}· {num_comments} comment{'s' if num_comments != 1 else ''}{cl.ENDC}"

        # Topic header
        user_color = cl.WARNING if me and username == me else cl.OKCYAN
        header = (
            f"{cl.BOLD}┌{cl.ENDC} "
            f"{user_color}@{username}{cl.ENDC}"
            f" {cl.FGGRAY}·{cl.ENDC} "
            f"{cl.FGGRAY}{ts}{cl.ENDC}"
            f"{tag_str}{edited_str}{reaction_str}{comment_count}"
        )
        lines.append(header)

        # Topic body
        body_prefix = f"{cl.BOLD}│{cl.ENDC} "
        if message:
            lines.extend(_render_message_lines(message, body_prefix, width, mentions, var_lookup))

        # Comments
        comments = topic.get("comments", []) or []
        for i, comment in enumerate(comments):
            is_last = i == len(comments) - 1
            connector = "├ " if not is_last else "└ "
            child_prefix = "│ " if not is_last else "  "
            lines.append(
                _render_comment(
                    comment,
                    body_prefix,
                    connector,
                    child_prefix,
                    width,
                    me=me,
                    var_lookup=var_lookup,
                )
            )

        if not comments:
            lines.append(f"{cl.BOLD}└{cl.ENDC} {cl.FGGRAY}(no comments){cl.ENDC}")

        # Cap the last line: replace topic-level bold │ with bold └
        topic_text = "\n".join(lines)
        all_lines = topic_text.split("\n")
        bold_pipe = f"{cl.BOLD}│{cl.ENDC}"
        bold_cap = f"{cl.BOLD}└{cl.ENDC}"
        all_lines[-1] = all_lines[-1].replace(bold_pipe, bold_cap, 1)
        parts.append("\n".join(all_lines))

    return "\n\n".join(parts)
