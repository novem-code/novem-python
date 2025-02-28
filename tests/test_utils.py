from novem.utils import ansi_escape, pretty_format_inner


def test_pretty_format_basic() -> None:
    obj = [
        {
            "id": "apple",
            "type": "fruit",
        },
        {
            "id": "potato",
            "type": "dirty-ground-vegetable",
        },
    ]

    h = [
        {
            "key": "id",
            "header": "ID",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type of thing in list",
            "type": "text",
            "overflow": "truncate",
        },
    ]
    res = pretty_format_inner(obj, h, col=100)

    # strip all ansi color codes, and trailing whitespace
    res = "\n".join(x.strip() for x in ansi_escape.sub("", res).split("\n"))

    assert (
        res
        == """\
ID      Type of thing in list
╌╌╌╌╌╌  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
apple   fruit
potato  dirty-ground-vegetable
"""
    )


def test_pretty_format_hard_truncate() -> None:
    obj = [
        {
            "id": "apple",
            "type": "fruit",
        },
        {
            "id": "potato",
            "type": "dirty-ground-vegetable",
        },
    ]

    h = [
        {
            "key": "id",
            "header": "ID",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type of thing in list",
            "type": "text",
            "overflow": "truncate",
        },
    ]
    res = pretty_format_inner(obj, h, col=10)

    # strip all ansi color codes, and trailing whitespace
    res = "\n".join(x.strip() for x in ansi_escape.sub("", res).split("\n"))

    assert (
        res
        == """\
ID      Type of thing in list
╌╌╌╌╌╌  ╌╌╌╌╌
apple   fruit
potato  di...
"""
    )
