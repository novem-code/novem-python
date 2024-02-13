from typing import Any, Dict, Optional

from novem.vis import NovemVisAPI

from .cell import NovemCellConfig
from .colors import NovemColors
from .plot_config import NovemPlotConfig


class Plot(NovemVisAPI):
    """
    Novem plot class
    """

    colors: Optional[NovemColors] = None
    cell: Optional[NovemCellConfig] = None
    config: Optional[NovemPlotConfig] = None

    def __init__(self, id: str, **kwargs: Any) -> None:
        """
        :id plot name, duplicate entry will update the plot

        :type the type of plot
        :caption caption of the plot
        :title title of the plot
        """

        # if we have an @ name we will override id and user
        if id[0] == "@":
            cand = id[1:].split("~")
            id = cand[1]
            uname = cand[0]
            kwargs["user"] = uname

        self.id = id

        self._vispath = "plots"
        self._type = "plot"

        self._freeze: bool = False

        # store pending updates when plot is frozen
        self._pending: Dict[str, str] = {}

        self.colors = NovemColors(self)
        self.cell = NovemCellConfig(self)
        self.config = NovemPlotConfig(self)

        super().__init__(**kwargs)

        self._parse_kwargs(**kwargs)

    def _set_data(self, data: Any, **kwargs: Any) -> Any:
        """
        Set's the data of the plot

        The parameter either needs to be a text string
        of CSV formatted text or an object with a to_csv
        function.
        """

        raw_str: str = ""
        to_csv = getattr(data, "to_csv", None)

        if callable(to_csv):
            # if data has a callable csv funciton we'll
            # assume it's a pandas dataframe
            raw_str = data.to_csv()
        else:
            raw_str = str(data)

        # invoke server write
        self._write("/data", raw_str)

        # also update our chart varibales
        self._parse_kwargs(**kwargs)

        # return a reference to the plot, from experience
        # after sending a dataframe to the plot the user
        # would rather operate on the plot object itself
        return self

    def __call__(self, data: Any, **kwargs: Any) -> Any:
        return self._set_data(data, **kwargs)

    def _parse_kwargs(self, **kwargs: Any) -> None:

        # first let our super do it's thing
        super()._parse_kwargs(**kwargs)

        # get a list of valid properties
        # exclude data as it needs to be run last
        props = [x for x in dir(self) if x[0] != "_" and x not in ["data", "read", "delete", "write"]]

        do_data = False
        for k, v in kwargs.items():
            if k == "data":
                do_data = True

            if k not in props:
                continue

            # print(f"{k} :: {v}")
            # set our value
            setattr(self, k, v)

        if do_data:
            data = kwargs["data"]
            setattr(self, "data", data)

    def _read(self, path: str) -> str:
        if self._freeze:
            if path in self._pending:
                return self._pending[path]

        return self.api_read(path)

    def _write(self, path: str, value: str) -> None:
        if self._freeze:
            self._pending[path] = value
        else:
            self.api_write(path, value)

    # we'll implement generic properties common across all plots here
    @property
    def type(self) -> str:
        return self._read("/config/type").strip()

    @type.setter
    def type(self, value: str) -> None:
        return self._write("/config/type", value)

    @property
    def name(self) -> str:
        return self._read("/name").strip()

    @name.setter
    def name(self, value: str) -> None:
        return self._write("/name", value)

    @property
    def description(self) -> str:
        return self._read("/description")

    @description.setter
    def description(self, value: str) -> None:
        return self._write("/description", value)

    @property
    def summary(self) -> str:
        return self._read("/summary")

    @summary.setter
    def summary(self, value: str) -> None:
        return self._write("/summary", value)

    @property
    def data(self) -> str:
        return self._read("/data")

    @data.setter
    def data(self, value: str) -> None:
        self._set_data(value)
        return None
        # return self._write("/data", value)

    @property
    def url(self) -> str:
        return self._read("/url").strip()

    @property
    def shortname(self) -> str:
        return self._read("/shortname").strip()

    ###
    # Interactive utility functions
    ###

    def df(self, data: Any, **kwargs: Any) -> Any:
        """
        Expects a dataframe as input and returns the
        same dataframe so it can be chained
        """
        self._set_data(data, **kwargs)
        return data

    # chainable utility function for setting values
    def w(self, key: str, value: str) -> Any:
        """
        Set a novem plot property, if key is a valid
        class porp then it will set that, else it will
        try to invoke an api call

        w('type','bar') -> invokes set attribute type
        w('/config/type','bar') -> invokes the api

        (both options results in the same effect)
        """
        props = [x for x in dir(self) if x[0] != "_" and x not in ["data", "read", "delete", "write"]]

        if key in props:
            self.__setattr__(key, value)
        else:
            self._write(key, value)

        return self

    # print our ansi version
    @property
    def x(self) -> None:
        print(self._read("/files/plot.ansi"))

        return None

    # print our img (png) special utility for qtconsole
    @property
    def i(self) -> Any:
        """
        Utility for getting a qtconsole image representation
        """
        from IPython.core.display import Image  # type: ignore

        return Image(
            self.api_read_bytes(f"/files/{self._type}.png"),
            retina=False,  # todo: lookup if computer supports retina and
            # request 2x resolution and set this variable
            width=900,  # todo: get img width from current session
        )

    ###
    # config variables
    ###

    # set the plot caption
    @property
    def caption(self) -> str:
        return self._read("/config/caption")

    @caption.setter
    def caption(self, value: str) -> None:
        return self._write("/config/caption", value)

    # set the plot title
    @property
    def title(self) -> str:
        return self._read("/config/title")

    @title.setter
    def title(self, value: str) -> None:
        return self._write("/config/title", value)

    ###
    # Deal with frozen plots
    ###

    def freeze(self) -> None:
        self._freeze = True

    def run(self) -> None:
        # push pending updates to server
        for path, value in self._pending.items():
            self.api_write(path, value)

        self._freeze = False

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "colors" and self.colors:
            self.colors.set(value)
        else:
            super().__setattr__(name, value)
