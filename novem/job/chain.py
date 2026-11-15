"""The job chain grammar as python values.

A job's ``config/chains`` file says what the job runs: one repo image, or
several steps piped together::

    fetch  <- @alice/data_fetcher:latest
    render <- @alice/chart_builder:prod,mem=1G

    fetch -> render

:class:`Chain` builds, parses, validates and renders that text without
talking to the API, so ``print(chain)`` shows exactly what would be written::

    Chain({"fetch": fetch_repo, "render": render_repo.ref("prod")})

    Chain().step("split", a).fan("render", b).step("collect", c)

Anywhere a step name is accepted, an edge token is accepted too: ``.name``
fans out over the previous step's files, ``!name`` holds before the step and
``name!`` after it.
"""

import re
from datetime import timedelta
from typing import Any, Dict, Iterator, List, Mapping, Optional, Set, Tuple, Union

from typing_extensions import Protocol, runtime_checkable

from ..api_ref import NovemChainError

__all__ = ["Chain", "Step", "RepoRef", "HasChainRef", "NovemChainError"]

_NAME = r"[A-Za-z0-9_-]+"
_FULL_PATH_RE = re.compile(rf"^/u/({_NAME})/([jr])/({_NAME})(?::([A-Za-z0-9._-]+))?$")
_SHORT_PATH_RE = re.compile(rf"^/([jr])/({_NAME})(?::([A-Za-z0-9._-]+))?$")
_LEGACY_RE = re.compile(rf"^/?({_NAME})/({_NAME})(?::(\S+))?$")
_STEP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SIZE_RE = re.compile(r"^([0-9]+)(m|mb|mib|mi|g|gb|gib|gi)$")
_DURATION_RE = re.compile(r"^([0-9]+)([smh])$")
_DURATION_SECONDS = {"s": 1, "m": 60, "h": 3600}
_RESERVED_NAMES = {"README"}
_HOLDS = {None: (False, False), "before": (True, False), "after": (False, True), "both": (True, True)}


@runtime_checkable
class HasChainRef(Protocol):
    """Anything that can be the target of a chain step (a repo, a job)."""

    def get_chain_ref(self) -> str: ...


class RepoRef(str):
    """A repo image reference, as returned by ``Repo.ref()``.

    Its text is ``/user/repo:label``, the form the single-image job config
    keys take; a chain reads it as ``@user/repo:label``.
    """

    user: str
    repo: str
    label: str

    def __new__(cls, user: str, repo: str, label: str = "latest") -> "RepoRef":
        obj = super().__new__(cls, f"/{user}/{repo}:{label}")
        obj.user = user
        obj.repo = repo
        obj.label = label
        return obj

    def get_chain_ref(self) -> str:
        return f"@{self.user}/{self.repo}:{self.label}"


class _Ref:
    """One parsed reference: a repo image, another job, or nothing (``_``)."""

    def __init__(self, kind: str, name: str = "", user: Optional[str] = None, label: Optional[str] = None) -> None:
        self.kind = kind  # "repo" | "job" | "none"
        self.name = name
        self.user = user
        self.label = label

    def __str__(self) -> str:
        if self.kind == "none":
            return "_"
        if self.kind == "job":
            return f"/u/{self.user}/j/{self.name}" if self.user else f"/j/{self.name}"
        if self.user:
            return f"@{self.user}/{self.name}:{self.label or 'latest'}"
        return f"{self.name}:{self.label}" if self.label else self.name

    def key(self) -> Tuple[str, Optional[str], str, Optional[str]]:
        label = None if self.kind != "repo" else (self.label or "latest")
        return (self.kind, self.user, self.name, label)

    def copy(self) -> "_Ref":
        return _Ref(self.kind, self.name, self.user, self.label)


def _parse_ref(expr: str, owner: Optional[str] = None) -> _Ref:
    line = expr.strip()
    if not line:
        raise NovemChainError("Empty reference")
    if line == "_":
        return _Ref("none")

    ref: Optional[_Ref] = None
    if line.startswith("/"):
        full = _FULL_PATH_RE.match(line)
        short = None if full else _SHORT_PATH_RE.match(line)
        if full or short:
            if full:
                user, kind, name, label = full.group(1), full.group(2), full.group(3), full.group(4)
            else:
                assert short is not None
                user, kind, name, label = None, short.group(1), short.group(2), short.group(3)
            if kind == "j":
                if label is not None:
                    raise NovemChainError(f"Job references do not take a label: {line}")
                ref = _Ref("job", name, user)
            else:
                ref = _Ref("repo", name, user, label)
    elif line.startswith("@"):
        user, _, rest = line[1:].partition("/")
        name, sep, label = rest.partition(":")
        if user and name and "/" not in rest and (label or not sep):
            ref = _Ref("repo", name, user, label or None)
    elif "/" not in line:
        name, sep, label = line.partition(":")
        if name and (label or not sep):
            ref = _Ref("repo", name, None, label or None)

    if ref is None:
        # the older "/user/repo:label" and "user/repo:label" spellings
        legacy = _LEGACY_RE.match(line)
        if not legacy:
            raise NovemChainError(f"Invalid chain reference: {line}")
        ref = _Ref("repo", legacy.group(2), legacy.group(1), legacy.group(3))

    if not re.match(rf"^{_NAME}$", ref.name) or (ref.user is not None and not re.match(rf"^{_NAME}$", ref.user)):
        raise NovemChainError(f"Invalid chain reference: {line}")
    if ref.user is None and owner:
        ref.user = owner
    return ref


def _parse_cpu(value: Any) -> int:
    if isinstance(value, bool) or not (isinstance(value, int) or (isinstance(value, str) and value.isdigit())):
        raise NovemChainError(f"cpu must be a whole number of cores, e.g. cpu=4: {value!r}")
    if int(value) < 1:
        raise NovemChainError(f"cpu must be a whole number of cores, e.g. cpu=4: {value!r}")
    return int(value)


def _parse_size(key: str, value: Any) -> int:
    m = _SIZE_RE.match(value.strip().lower()) if isinstance(value, str) else None
    if not m:
        raise NovemChainError(f"{key} must be a size with a unit, e.g. {key}='4G' or {key}='512M': {value!r}")
    amount = int(m.group(1))
    if amount == 0:
        raise NovemChainError(f"{key} must be greater than zero: {value!r}")
    return amount * (1024 if m.group(2).startswith("g") else 1)


def _parse_timeout(value: Any) -> int:
    seconds: Optional[int] = None
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
    elif isinstance(value, int) and not isinstance(value, bool):
        seconds = value
    elif isinstance(value, str):
        m = _DURATION_RE.match(value.strip().lower())
        if m:
            seconds = int(m.group(1)) * _DURATION_SECONDS[m.group(2)]
    if seconds is None:
        raise NovemChainError(f"timeout must be a duration, e.g. timeout='30s' or timeout='5m': {value!r}")
    if seconds <= 0:
        raise NovemChainError(f"timeout must be greater than zero: {value!r}")
    return seconds


def _render_size(mb: int) -> str:
    return f"{mb // 1024}G" if mb % 1024 == 0 else f"{mb}M"


def _render_duration(seconds: int) -> str:
    for unit, mult in (("h", 3600), ("m", 60)):
        if seconds % mult == 0:
            return f"{seconds // mult}{unit}"
    return f"{seconds}s"


_ATTRS = {
    "cpu": _parse_cpu,
    "mem": lambda v: _parse_size("mem", v),
    "disk": lambda v: _parse_size("disk", v),
    "timeout": _parse_timeout,
}


def _split_attrs(expr: str) -> Tuple[str, Dict[str, int]]:
    """Split ``ref,key=value,...`` into the reference and its resources."""
    ref_expr, *attrs = (part.strip() for part in expr.split(","))
    values: Dict[str, int] = {}
    for attr in attrs:
        key, sep, value = (part.strip() for part in attr.partition("="))
        key = key.lower()
        if not sep or not value:
            raise NovemChainError(f"Step attribute must be key=value: {attr!r}")
        if key not in _ATTRS:
            raise NovemChainError(f"Unknown step attribute {key!r} (known: {', '.join(sorted(_ATTRS))})")
        if key in values:
            raise NovemChainError(f"Duplicate step attribute: {key}")
        values[key] = _ATTRS[key](value)
    return ref_expr, values


def _parse_token(token: str) -> Tuple[str, bool, bool, bool]:
    """Split an edge token into ``(name, fan, hold_before, hold_after)``."""
    token = token.strip()
    if not token:
        raise NovemChainError("Empty step name")
    for char, what in ((",", "AND dependencies"), ("|", "OR dependencies"), (":", "Error handlers")):
        if char in token:
            raise NovemChainError(f"{what} ('{char}') are not supported: {token!r}")
    leading, trailing = token.startswith("."), token.endswith(".")
    bare = token.strip(".")
    if leading and trailing and bare:
        raise NovemChainError(f"Cross-join syntax ('.X.') is not supported: {token!r}")
    hold_before, hold_after = bare.startswith("!"), bare.endswith("!")
    name = bare.strip("!")
    if not name or "." in name or "!" in name:
        raise NovemChainError(f"Invalid step name: {token!r}")
    return name, leading, hold_before, hold_after


class Step:
    """One step of a chain: a reference plus its options.

    ``ref`` is a ``Repo``, ``Repo.ref(label)``, a ``Job``, or a string in the
    chain grammar (``"repo"``, ``"@user/repo:label"``, ``"/j/job"``, ``"_"``).
    ``hold`` is ``"before"``, ``"after"`` or ``"both"``; ``True`` means
    ``"after"``. ``mem`` and ``disk`` take a unit (``"4G"``, ``"512M"``);
    ``timeout`` is ``"30s"`` / ``"5m"`` / ``"1h"``, seconds, or a timedelta.
    """

    def __init__(
        self,
        ref: Any,
        *,
        name: Optional[str] = None,
        fan: bool = False,
        hold: Union[None, bool, str] = None,
        cpu: Any = None,
        mem: Any = None,
        disk: Any = None,
        timeout: Any = None,
        _lenient: bool = False,
    ) -> None:
        self.name: Optional[str] = None
        self.fan = bool(fan)
        self.cpu: Optional[int] = None
        self.mem: Optional[int] = None  # MiB
        self.disk: Optional[int] = None  # MiB
        self.timeout: Optional[int] = None  # seconds

        if hold is True:
            hold = "after"
        elif hold is False:
            hold = None
        if hold not in _HOLDS:
            raise NovemChainError(f"hold must be 'before', 'after' or 'both': {hold!r}")
        self.hold_before, self.hold_after = _HOLDS[hold]

        self._set_ref(ref)
        if cpu is not None:
            self.cpu = _parse_cpu(cpu)
        if mem is not None:
            self.mem = _parse_size("mem", mem)
        if disk is not None:
            self.disk = _parse_size("disk", disk)
        if timeout is not None:
            self.timeout = _parse_timeout(timeout)
        if name is not None:
            self._apply_token(name, _lenient)

    def _set_ref(self, ref: Any) -> None:
        if isinstance(ref, _Ref):
            self.ref = ref.copy()
            return
        if ref is None:
            raise NovemChainError("A step needs a reference; use '_' for a step that only holds")
        if isinstance(ref, HasChainRef):  # before str: a RepoRef is both
            self.ref = _parse_ref(ref.get_chain_ref())
            return
        if not isinstance(ref, str):
            raise NovemChainError(f"Cannot use {type(ref).__name__} as a chain reference")
        expr, attrs = _split_attrs(ref)
        self.ref = _parse_ref(expr)
        for key, value in attrs.items():
            setattr(self, key, value)

    def _apply_token(self, token: str, lenient: bool = False) -> None:
        name, fan, before, after = _parse_token(token)
        if not lenient and (not _STEP_NAME_RE.match(name) or name in _RESERVED_NAMES):
            raise NovemChainError(
                f"Invalid step name {name!r}: use letters, digits, '_' and '-', starting with a letter or digit"
            )
        self.name = name
        self.fan = self.fan or fan
        self.hold_before = self.hold_before or before
        self.hold_after = self.hold_after or after

    def _marks(self) -> Tuple[bool, bool]:
        # a step with no image runs nothing, so before and after coincide
        if self.ref.kind == "none" and (self.hold_before or self.hold_after):
            return True, False
        return self.hold_before, self.hold_after

    @property
    def hold(self) -> Optional[str]:
        before, after = self._marks()
        return "both" if before and after else "before" if before else "after" if after else None

    @property
    def resources(self) -> str:
        parts: List[str] = []
        if self.cpu is not None:
            parts.append(f"cpu={self.cpu}")
        if self.mem is not None:
            parts.append(f"mem={_render_size(self.mem)}")
        if self.disk is not None:
            parts.append(f"disk={_render_size(self.disk)}")
        if self.timeout is not None:
            parts.append(f"timeout={_render_duration(self.timeout)}")
        return ",".join(parts)

    @property
    def target(self) -> str:
        """The reference with its resources, as written after ``<-``."""
        res = self.resources
        return f"{self.ref},{res}" if res else str(self.ref)

    @property
    def token(self) -> str:
        """The step as it appears in the edge line, e.g. ``.render`` or ``gen!``."""
        before, after = self._marks()
        return f"{'.' if self.fan else ''}{'!' if before else ''}{self.name or 'main'}{'!' if after else ''}"

    def copy(self) -> "Step":
        s = Step(self.ref)
        s.name, s.fan = self.name, self.fan
        s.hold_before, s.hold_after = self.hold_before, self.hold_after
        s.cpu, s.mem, s.disk, s.timeout = self.cpu, self.mem, self.disk, self.timeout
        return s

    def _key(self) -> Tuple[Any, ...]:
        return (self.ref.key(), self.fan, self._marks(), self.cpu, self.mem, self.disk, self.timeout)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Step):
            return NotImplemented
        return self.name == other.name and self._key() == other._key()

    def __repr__(self) -> str:
        return f"Step({self.token!r} <- {self.target!r})"


def _named(value: Any, name: Optional[str] = None) -> Step:
    if isinstance(value, Step):
        step = value.copy()
        if name is not None:
            given = step.name
            step._apply_token(name)
            if given is not None and given != step.name:
                raise NovemChainError(f"Step is named {given!r} but was placed under {step.name!r}")
        return step
    return Step(value, name=name)


def _parse_text(text: str) -> List[Step]:
    """Parse the binding/edge form of the grammar."""
    bindings: Dict[str, Step] = {}
    edges: List[Tuple[str, str]] = []
    fan: Set[str] = set()
    before: Set[str] = set()
    after: Set[str] = set()
    bare: List[str] = []

    def mark(token: str) -> str:
        name, is_fan, hold_before, hold_after = _parse_token(token)
        if is_fan:
            fan.add(name)
        if hold_before:
            before.add(name)
        if hold_after:
            after.add(name)
        return name

    for line in (ln.strip() for ln in text.strip().splitlines()):
        if not line:
            continue
        if "<-" in line:
            name, _, expr = line.partition("<-")
            name = name.strip()
            if not name:
                raise NovemChainError(f"Empty step name in binding: {line}")
            if name in bindings:
                raise NovemChainError(f"Duplicate step name: {name}")
            step = Step(expr.strip())
            step._apply_token(name, lenient=True)
            if step.fan or step.hold_before or step.hold_after:
                raise NovemChainError(f"Fan-out and hold marks go in the edge line, not the binding: {line}")
            bindings[name] = step
        elif "->" in line:
            names = [mark(part) for part in line.split("->")]
            edges.extend(zip(names, names[1:]))
        else:
            name = mark(line)
            if name in fan:
                raise NovemChainError(f"A fan-out step needs an edge: {line!r}")
            bare.append(name)

    if not bindings:
        raise NovemChainError("A chain needs at least one step")
    for name in bare:
        if name not in bindings:
            raise NovemChainError(f"Unrecognized line: {name}")

    order = list(bindings)
    if edges:
        succ: Dict[str, str] = {}
        pred: Dict[str, str] = {}
        for src, dst in edges:
            for name in (src, dst):
                if name not in bindings:
                    raise NovemChainError(f"Undefined step in edge: {name}")
            if src in succ:
                raise NovemChainError(f"Branching is not supported: {src} -> {succ[src]} and {src} -> {dst}")
            if dst in pred:
                raise NovemChainError(f"Merging is not supported: {pred[dst]} -> {dst} and {src} -> {dst}")
            succ[src], pred[dst] = dst, src
        loose = sorted(set(bindings) - set(succ) - set(pred))
        if loose:
            raise NovemChainError(f"Disconnected step(s): {', '.join(loose)}")
        starts = [name for name in bindings if name not in pred]
        if len(starts) != 1:
            raise NovemChainError("A chain must form a single linear sequence")
        order = []
        current: Optional[str] = starts[0]
        while current is not None:
            order.append(current)
            current = succ.get(current)
        if len(order) != len(bindings):
            raise NovemChainError("A chain must form a single linear sequence")

    steps = []
    for name in order:
        step = bindings[name]
        step.fan = name in fan
        step.hold_before, step.hold_after = name in before, name in after
        steps.append(step)
    return steps


class Chain:
    """A job chain: an ordered list of steps.

    Build one from a reference, grammar text, a dict (keys are step names or
    edge tokens, in run order), a list, or with the chainable
    :meth:`step` / :meth:`fan` / :meth:`hold`. ``str(chain)`` is the text for
    ``config/chains``.
    """

    def __init__(self, source: Any = None, *, owner: Optional[str] = None) -> None:
        self._steps: List[Step] = []
        self._hold_next = False
        for step in self._coerce(source):
            self._append(step)
        if owner:
            for step in self._steps:
                if step.ref.kind != "none" and step.ref.user is None:
                    step.ref.user = owner

    @classmethod
    def parse(cls, text: str, owner: Optional[str] = None) -> "Chain":
        """Read ``config/chains`` text. ``owner`` resolves short references."""
        return cls(text, owner=owner)

    @staticmethod
    def _coerce(source: Any) -> List[Step]:
        if source is None:
            return []
        if isinstance(source, Chain):
            return [s.copy() for s in source._steps]
        if isinstance(source, (Step, HasChainRef)):
            return [_named(source)]
        if isinstance(source, str):
            if not source.strip():
                return []
            if "<-" in source:
                return _parse_text(source)
            return [Step(source)]
        if isinstance(source, Mapping):
            return [_named(value, str(key)) for key, value in source.items()]
        if isinstance(source, (list, tuple)):
            return [_named(value) for value in source]
        raise NovemChainError(f"Cannot build a chain from {type(source).__name__}")

    def _name_of(self, step: Step) -> str:
        if step.name is None:
            if step.ref.kind == "none":
                raise NovemChainError("A step that only holds needs a name")
            step.name = step.ref.name
        return step.name

    def _append(self, step: Step) -> None:
        if self._steps:
            self._name_of(self._steps[0])
            if self._name_of(step) in self:
                raise NovemChainError(f"Duplicate step name: {step.name}")
        elif step.name is None and step.ref.kind == "none":
            raise NovemChainError("A step that only holds needs a name")
        if self._hold_next:
            step.hold_before = True
            self._hold_next = False
        self._steps.append(step)

    def _index(self, name: str) -> int:
        plain = _parse_token(name)[0]
        for i, step in enumerate(self._steps):
            if (step.name or "main") == plain:
                return i
        return -1

    # -- building ------------------------------------------------------------
    def step(
        self,
        name: str,
        ref: Any,
        *,
        hold: Union[None, bool, str] = None,
        cpu: Any = None,
        mem: Any = None,
        disk: Any = None,
        timeout: Any = None,
    ) -> "Chain":
        """Append a step that runs once on the previous step's output."""
        self._append(Step(ref, name=name, hold=hold, cpu=cpu, mem=mem, disk=disk, timeout=timeout))
        return self

    def fan(
        self,
        name: str,
        ref: Any,
        *,
        cpu: Any = None,
        mem: Any = None,
        disk: Any = None,
        timeout: Any = None,
    ) -> "Chain":
        """Append a fan-out step: one run per file the previous step produced."""
        self._append(Step(ref, name=name, fan=True, cpu=cpu, mem=mem, disk=disk, timeout=timeout))
        return self

    def hold(self, name: Optional[str] = None) -> "Chain":
        """Stop the run here and wait for a person.

        Without a name the stop belongs to the previous step (``prev!``), or
        to the next one when the chain is still empty (``!next``). With a
        name it becomes a step of its own that runs nothing.
        """
        if name is not None:
            self._append(Step("_", name=name, hold="before"))
        elif not self._steps:
            self._hold_next = True
        elif self._steps[-1].fan:
            raise NovemChainError(
                f"Step {self._steps[-1].name!r} is a fan-out and cannot hold. "
                "Put the hold on the step after it: .step(name, ref, hold='before')"
            )
        else:
            self._steps[-1].hold_after = True
        return self

    def validate(self) -> "Chain":
        """Raise :class:`NovemChainError` if the chain cannot run."""
        steps = self._steps
        if not steps or self._hold_next:
            raise NovemChainError("A chain needs at least one step")
        for s in steps:
            label = s.name or "main"
            if s.ref.kind == "none":
                if s.hold is None:
                    raise NovemChainError(f"Step {label!r} binds no image ('_') and carries no hold, so it cannot run")
                if s.resources:
                    raise NovemChainError(f"Step {label!r} runs nothing, so it takes no resources")
            if s.ref.kind == "job" and s.resources:
                raise NovemChainError(
                    f"Step {label!r} references a job and takes no resources; set them in that job's own chain"
                )
            if s.ref.kind == "job" and s.fan:
                raise NovemChainError(f"Step {label!r} references a job and cannot fan out")
            if s.fan and s.hold is not None:
                raise NovemChainError(f"Step {label!r} is a fan-out and cannot hold")

        at = [i for i, s in enumerate(steps) if s.fan]
        if at:
            if at != list(range(at[0], at[-1] + 1)):
                raise NovemChainError(f"Fan-out steps must be consecutive: {', '.join(str(steps[i].name) for i in at)}")
            if at[0] == 0:
                raise NovemChainError(f"Fan-out step {steps[0].name or 'main'!r} needs a step before it")
            if at[-1] == len(steps) - 1:
                raise NovemChainError(f"Fan-out step {steps[-1].name!r} needs a step after it to collect its output")
            prev = steps[at[0] - 1]
            if prev.hold_after or (prev.ref.kind == "none" and prev.hold is not None):
                raise NovemChainError(
                    f"A hold may not stop right before fan-out step {steps[at[0]].name!r}: "
                    "put a step between them to pass the files on"
                )
        return self

    # -- reading and editing -------------------------------------------------
    @property
    def steps(self) -> List[Step]:
        return list(self._steps)

    @property
    def edges(self) -> List[Tuple[str, str]]:
        names = [s.name or "main" for s in self._steps]
        return list(zip(names, names[1:]))

    @property
    def refs(self) -> List[str]:
        """Unique references, in run order."""
        seen: List[str] = []
        for s in self._steps:
            if s.ref.kind != "none" and str(s.ref) not in seen:
                seen.append(str(s.ref))
        return seen

    def __getitem__(self, name: str) -> Step:
        i = self._index(name)
        if i < 0:
            raise KeyError(name)
        return self._steps[i]

    def __setitem__(self, name: str, value: Any) -> None:
        i = self._index(name)
        if i < 0:
            self._append(_named(value, name))
        elif isinstance(value, Step):
            self._steps[i] = _named(value, name)
        else:
            # rebind: keep the step's place, marks and resources
            current = self._steps[i]
            fresh = Step(value)
            current.ref = fresh.ref
            for key in ("cpu", "mem", "disk", "timeout"):
                if getattr(fresh, key) is not None:
                    setattr(current, key, getattr(fresh, key))
            current._apply_token(name, lenient=True)

    def __delitem__(self, name: str) -> None:
        i = self._index(name)
        if i < 0:
            raise KeyError(name)
        del self._steps[i]

    def __iadd__(self, other: Any) -> "Chain":
        for step in self._coerce(other):
            self._append(step)
        return self

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self._index(name) >= 0

    def __len__(self) -> int:
        return len(self._steps)

    def __iter__(self) -> Iterator[Step]:
        return iter(self._steps)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Chain):
            try:
                other = Chain(other)
            except NovemChainError:
                return NotImplemented
        mine = [(s.name or "main", s._key()) for s in self._steps]
        theirs = [(s.name or "main", s._key()) for s in other._steps]
        return mine == theirs

    __hash__ = None  # type: ignore[assignment]

    def __str__(self) -> str:
        steps = self._steps
        if not steps:
            return ""
        if len(steps) == 1:
            s = steps[0]
            marked = s.fan or s.hold is not None
            if s.name in (None, "main") and not marked and s.ref.kind != "none":
                return s.target
            lines = [f"{s.name or 'main'} <- {s.target}"]
            if marked:
                lines += ["", s.token]
            return "\n".join(lines)
        lines = [f"{s.name} <- {s.target}" for s in steps]
        lines += ["", " -> ".join(s.token for s in steps)]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Chain({' -> '.join(s.token for s in self._steps)!r})"
