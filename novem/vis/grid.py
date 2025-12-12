from __future__ import annotations

from typing import Any

from novem.vis import NovemVisAPI


class Grid(NovemVisAPI):
    """
    Novem grid class
    """

    def __init__(self, id: str, **kwargs: Any) -> None:
        """
        :id grid name, duplicate entry will update the grid

        """

        # if we have an @ name we will override id and user
        if id[0] == "@":
            cand = id[1:].split("~")
            id = cand[1]
            uname = cand[0]
            kwargs["user"] = uname

        self.id = id

        self._vispath = "grids"
        self._type = "grid"

        super().__init__(**kwargs)

        self._parse_kwargs(**kwargs)

    def __call__(self, content: Any, **kwargs: Any) -> Any:
        """
        Set's the layout of the grid

        This paramter is expected to be one of the valid layout
        strings or formats
        """

        raw_str: str = str(content)

        # setting the content object will invoke a server write
        self.layout = raw_str

        # also update our varibales
        self._parse_kwargs(**kwargs)

        # return the original object so users can chain the contentframe
        return content

    def _parse_kwargs(self, **kwargs: Any) -> None:

        # first let our super do it's thing
        super()._parse_kwargs(**kwargs)

        # get a list of valid properties
        # exclude mapping and layout as they needs to be run last
        props = [
            x for x in dir(self) if x[0] != "_" and x not in ["layout", "mapping", "read", "delete", "write", "create"]
        ]

        do_layout = False
        do_mapping = False
        for k, v in kwargs.items():
            if k == "layout":
                do_layout = True

            if k == "mapping":
                do_mapping = True

            if k not in props:
                continue

            # print(f"{k} :: {v}")
            # set our value
            setattr(self, k, v)

        # mapping first
        if do_mapping:
            mapping = kwargs["mapping"]
            setattr(self, "mapping", mapping)

        # layout last, as it depends on mapping
        if do_layout:
            layout = kwargs["layout"]
            setattr(self, "layout", layout)

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
    def mapping(self, value: str) -> None:
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
