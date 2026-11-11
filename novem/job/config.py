from typing import TYPE_CHECKING, Any, Dict

from ..api_ref import NovemChainError
from .chain import Chain, HasChainRef
from .chains import NovemJobChains

if TYPE_CHECKING:
    from novem.job import NovemJobAPI

_STEP_KEYS = ("extract", "render")


def _legacy_ref(value: Any) -> str:
    """A reference in the form the single-image config keys take."""
    if isinstance(value, str):
        return str(value)
    ref = getattr(value, "ref", None)
    if isinstance(value, HasChainRef) and callable(ref):
        return str(ref())
    return str(value)


class NovemJobConfig:
    """
    Provide utility objects for novem jobs

    ``extract`` and ``render`` are steps of the job's chain. On a job created
    with an explicit non-chains ``type`` they are the single-image config keys
    of that type instead.
    """

    def __init__(self, api: "NovemJobAPI") -> None:
        """Initialize the Job object"""
        self.api: "NovemJobAPI" = api

    def set(self, config: Dict[str, Any]) -> None:
        """
        Set config options
        """
        if "type" in config:
            self.type = config["type"]

        steps = {k: config[k] for k in _STEP_KEYS if k in config}

        if "chains" in config:
            if steps:
                raise NovemChainError("Give either 'chains' or 'extract'/'render', not both")
            self.chains = config["chains"]
        elif self.api._legacy_runtime():
            for k, v in steps.items():
                setattr(self, k, v)
        elif steps:
            self._upsert(steps)

    def _upsert(self, steps: Dict[str, Any]) -> None:
        chain = self.api.chains.get()
        for name in _STEP_KEYS:
            if name not in steps:
                continue
            if name in chain or name == "render":
                chain[name] = steps[name]
            else:
                # extract runs first
                head = Chain({name: steps[name]})
                head += chain
                chain = head
        self.api.chains.set(chain)

    def _step(self, name: str) -> str:
        chain = self.api.chains.get()
        return str(chain[name].ref) if name in chain else ""

    @property
    def type(self) -> str:
        return self.api.type

    @type.setter
    def type(self, value: str) -> None:
        self.api.type = value

    @property
    def chains(self) -> NovemJobChains:
        return self.api.chains

    @chains.setter
    def chains(self, value: Any) -> None:
        self.api.chains = value

    @property
    def extract(self) -> str:
        if self.api._legacy_runtime():
            return self.api.api_read("/config/extract").strip()
        return self._step("extract")

    @extract.setter
    def extract(self, value: Any) -> None:
        if self.api._legacy_runtime():
            return self.api.api_write("/config/extract", _legacy_ref(value))
        self._upsert({"extract": value})

    @property
    def render(self) -> str:
        if self.api._legacy_runtime():
            return self.api.api_read("/config/render").strip()
        return self._step("render")

    @render.setter
    def render(self, value: Any) -> None:
        if self.api._legacy_runtime():
            return self.api.api_write("/config/render", _legacy_ref(value))
        self._upsert({"render": value})
