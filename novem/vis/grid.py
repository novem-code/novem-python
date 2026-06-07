from __future__ import annotations

from typing import Any, Optional, Union

from novem.vis import NovemVisAPI

from .grid_helpers import GridMap


class Grid(NovemVisAPI):
    """A novem grid (dashboard layout), addressed by name.

    Content properties (``layout``, ``mapping``, ``theme``, ``type``, …) may be
    passed to the constructor or set as attributes; changes are written live.
    ``layout`` depends on ``mapping``, so it is always applied last. Connection
    options are resolved from the arguments, ``novem.config``, the environment,
    or the config file — see the README.
    """

    _content_props = ("name", "description", "summary", "mapping", "layout", "theme", "type")
    # mapping first, layout last (layout depends on mapping)
    _content_deferred = ("mapping", "layout")

    def __init__(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        summary: Optional[str] = None,
        mapping: Optional[str] = None,
        layout: Optional[str] = None,
        theme: Optional[str] = None,
        type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        :id grid name, duplicate entry will update the grid

        Connection options and behaviour flags are accepted via **kwargs and
        resolved by the super chain. Unknown extras are warned and ignored.
        """

        # if we have an @ name we will override id and user
        if id[0] == "@":
            cand = id[1:].split("~")
            id = cand[1]
            kwargs["user"] = cand[0]

        self.id = id

        self._vispath = "grids"
        self._type = "grid"

        super().__init__(**kwargs)

        self._parse_kwargs(
            name=name,
            description=description,
            summary=summary,
            mapping=mapping,
            layout=layout,
            theme=theme,
            type=type,
            **kwargs,
        )

    def __call__(self, content: Any, **kwargs: Any) -> Any:
        """
        Set's the layout of the grid

        This parameter is expected to be one of the valid layout
        strings or formats
        """

        raw_str: str = str(content)

        # setting the content object will invoke a server write
        self.layout = raw_str

        # also update our varibales
        self._parse_kwargs(**kwargs)

        # return the original object so users can chain the contentframe
        return content

    @property
    def name(self) -> str:
        return self.api_read("/name").strip()

    @name.setter
    def name(self, value: str) -> None:
        return self.api_write("/name", value)

    @property
    def description(self) -> str:
        return self.api_read("/description")

    @description.setter
    def description(self, value: str) -> None:
        return self.api_write("/description", value)

    @property
    def summary(self) -> str:
        return self.api_read("/summary")

    @summary.setter
    def summary(self, value: str) -> None:
        return self.api_write("/summary", value)

    @property
    def url(self) -> str:
        return self.api_read("/url").strip()

    @property
    def shortname(self) -> str:
        return self.api_read("/shortname").strip()

    ###
    # Important attributes that cause render
    ###

    @property
    def mapping(self) -> str:
        return self.api_read("/mapping")

    @mapping.setter
    def mapping(self, value: Union[str, GridMap]) -> None:
        if isinstance(value, GridMap):
            value = str(value)
        return self.api_write("/mapping", value)

    @property
    def layout(self) -> str:
        return self.api_read("/layout")

    @layout.setter
    def layout(self, value: str) -> None:
        return self.api_write("/layout", value)

    ###
    # Config
    ###

    @property
    def theme(self) -> str:
        return self.api_read("/config/theme")

    @theme.setter
    def theme(self, value: str) -> None:
        return self.api_write("/config/theme", value)

    @property
    def type(self) -> str:
        return self.api_read("/config/type")

    @type.setter
    def type(self, value: str) -> None:
        return self.api_write("/config/type", value)

    ###
    # Interactive utility functions
    ###

    @property
    def x(self) -> None:
        """Print ANSI representation of the grid."""
        print(self.api_read("/files/grid.ansi"))
        return None

    @property
    def i(self) -> Any:
        """
        Utility for getting a qtconsole/Jupyter image representation.
        """
        from IPython.core.display import Image  # type: ignore

        return Image(
            self.api_read_bytes(f"/files/{self._type}.png"),
            retina=False,
            width=900,
        )
