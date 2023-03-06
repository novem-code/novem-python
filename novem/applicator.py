class Applicator(object):
    """
    A novem base class for creating strings to apply to table
    selections
    """

    def __init__(self, string: str) -> None:
        self.string = string

    def __str__(self) -> str:
        return self.string
