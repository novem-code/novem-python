from typing import Any

from novem.utils import ansi_escape, colors, pretty_format_inner


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


def test_pretty_format_fmt_receives_original_value() -> None:
    """Test that fmt function receives the original value, not a truncated string."""
    colors()

    # Simulates the share_fmt pattern: fmt receives a list and extracts first chars
    def share_fmt(share: Any, _cl: Any) -> str:
        # This should receive a list like ["public", "+"], not a string like "['pu..."
        sl = [x[0] for x in share]
        pub = "P" if "p" in sl else "-"
        org = "+" if "+" in sl else "-"
        return f"{pub} {org}"

    obj = [
        {"id": "item1", "shared": ["public", "+"]},
        {"id": "item2", "shared": ["public"]},
        {"id": "item3", "shared": ["+"]},
    ]

    h = [
        {"key": "id", "header": "ID", "type": "text", "overflow": "keep"},
        {"key": "shared", "header": "Shared", "type": "text", "fmt": share_fmt, "overflow": "keep"},
    ]

    res = pretty_format_inner(obj, h, col=100)
    res = "\n".join(x.strip() for x in ansi_escape.sub("", res).split("\n"))

    assert (
        res
        == """\
ID     Shared
╌╌╌╌╌  ╌╌╌╌╌╌
item1  P +
item2  P -
item3  - +
"""
    )


def test_pretty_format_fmt_with_list_not_truncated_to_string() -> None:
    """Regression test: ensure list values aren't converted to string before fmt."""
    colors()

    # Track what the fmt function receives
    received_values: list = []

    def tracking_fmt(value: Any, _cl: Any) -> str:
        received_values.append(value)
        if isinstance(value, list):
            return f"list:{len(value)}"
        return f"other:{type(value).__name__}"

    obj = [
        {"id": "test", "data": ["a", "b", "c", "d", "e"]},
    ]

    h = [
        {"key": "id", "header": "ID", "type": "text", "overflow": "keep"},
        {"key": "data", "header": "Data", "type": "text", "fmt": tracking_fmt, "overflow": "keep"},
    ]

    pretty_format_inner(obj, h, col=100)

    # The fmt function is called twice: once for width calculation, once for rendering
    # Both times it should receive the original list, not a string
    assert len(received_values) == 2
    for val in received_values:
        assert isinstance(val, list)
        assert val == ["a", "b", "c", "d", "e"]
