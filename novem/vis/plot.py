from typing import Any

from novem.vis import NovemVisAPI


class Plot(NovemVisAPI):
    """
    Novem plot class
    """

    def __init__(self, id: str, **kwargs: Any) -> None:
        """
        :name plot name, duplicate entry will update the plot

        :type the type of plot
        :caption caption of the plot
        :title title of the plot
        """
        self.id = id

        super().__init__(**kwargs)

        # let's create our plot
        self.api_create("")

        # if information neccessary to
        # terminate and print
        self.parse_kwargs(**kwargs)

    def __call__(self, data: Any, **kwargs: Any) -> Any:
        """
        Set's the data of the plot

        The paramter either needs to be a text string
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

        # setting the data object will invoke a server write
        self.data = raw_str

        # also update our chart varibales
        self.parse_kwargs(**kwargs)

        # return the original object so users can chain the dataframe
        return data

    # we'll implement generic properties common across all plots here
    @property
    def type(self) -> str:
        return self.api_read("/config/type").strip()

    @type.setter
    def type(self, value: str) -> None:
        return self.api_write("/config/type", value)

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
    def data(self) -> str:
        return self.api_read("/data")

    @data.setter
    def data(self, value: str) -> None:
        return self.api_write("/data", value)

    @property
    def url(self) -> str:
        return self.api_read("/url").strip()
