import os

import pytest

from novem.cli.gql import (
    _build_var_lookup,
    _format_var_value,
    _process_message,
    _render_inline_ansi,
    _render_message_lines,
    _render_vde_var_ansi,
    _resolve_mentions,
)
from novem.comments import (
    Comment,
    Context,
    Message,
    Topic,
    _dict_to_comment,
    _dict_to_topic,
    _gen_slug,
    _parse_fqnp,
    _split_comment_path,
)

# ---------------------------------------------------------------------------
# FQNP parsing
# ---------------------------------------------------------------------------


def test_parse_fqnp_vis():
    user, vis_type, vis_id = _parse_fqnp("/u/alice/p/myplot")
    assert user == "alice"
    assert vis_type == "plots"
    assert vis_id == "myplot"


def test_parse_fqnp_grid():
    user, vis_type, vis_id = _parse_fqnp("/u/bob/g/mygrid")
    assert user == "bob"
    assert vis_type == "grids"
    assert vis_id == "mygrid"


def test_parse_fqnp_mail():
    user, vis_type, vis_id = _parse_fqnp("/u/charlie/m/newsletter")
    assert user == "charlie"
    assert vis_type == "mails"
    assert vis_id == "newsletter"


def test_parse_fqnp_user_only():
    user, vis_type, vis_id = _parse_fqnp("/u/alice")
    assert user == "alice"
    assert vis_type is None
    assert vis_id is None


def test_parse_fqnp_org():
    name, vis_type, vis_id = _parse_fqnp("/o/myorg")
    assert name == "myorg"
    assert vis_type is None
    assert vis_id is None


def test_parse_fqnp_invalid():
    with pytest.raises(ValueError, match="Invalid FQNP"):
        _parse_fqnp("/x")


def test_parse_fqnp_invalid_prefix():
    with pytest.raises(ValueError, match="Invalid FQNP prefix"):
        _parse_fqnp("/z/foo/p/bar")


def test_split_comment_path_no_comments():
    base, segs = _split_comment_path("/u/alice/p/myplot")
    assert base == "/u/alice/p/myplot"
    assert segs == []


def test_split_comment_path_single():
    base, segs = _split_comment_path("/u/alice/p/myplot/c/@sen~topic")
    assert base == "/u/alice/p/myplot"
    assert segs == ["@sen~topic"]


def test_split_comment_path_nested():
    fqnp = "/u/trt/p/ex-spx-treemap/c/@sen~color-config/c/@trt~css-override/c/@mmy~diverging-palettes"
    base, segs = _split_comment_path(fqnp)
    assert base == "/u/trt/p/ex-spx-treemap"
    assert segs == ["@sen~color-config", "@trt~css-override", "@mmy~diverging-palettes"]


def test_parse_fqnp_strips_comment_segments():
    user, vis_type, vis_id = _parse_fqnp("/u/alice/p/myplot/c/@sen~topic/c/@bob~reply")
    assert user == "alice"
    assert vis_type == "plots"
    assert vis_id == "myplot"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_gen_slug():
    s = _gen_slug()
    assert s.startswith("r")
    assert s[1:].isdigit()


def test_message():
    m = Message("Hello world")
    assert m.text == "Hello world"


# ---------------------------------------------------------------------------
# Tree data structures
# ---------------------------------------------------------------------------


def test_comment_ref():
    c = Comment(slug="nice", message="Great!", creator="bob", depth=1)
    assert c.ref == "@bob~nice"
    assert c.replies == []


def test_topic_ref():
    t = Topic(slug="design", message="Design thread", creator="alice")
    assert t.ref == "@alice~design"
    assert t.comments == []


def test_dict_to_comment():
    d = {
        "comment_id": 42,
        "slug": "nice",
        "message": "Great topic!",
        "depth": 1,
        "deleted": False,
        "edited": True,
        "num_replies": 1,
        "likes": 3,
        "dislikes": 0,
        "my_reaction": "like",
        "created": "2025-01-01T00:00:00Z",
        "updated": "2025-01-01T01:00:00Z",
        "creator": {"username": "bob"},
        "replies": [
            {
                "comment_id": 43,
                "slug": "thanks",
                "message": "Thanks!",
                "depth": 2,
                "creator": {"username": "charlie"},
                "replies": [],
            }
        ],
    }
    c = _dict_to_comment(d)
    assert c.slug == "nice"
    assert c.creator == "bob"
    assert c.ref == "@bob~nice"
    assert c.edited is True
    assert c.likes == 3
    assert len(c.replies) == 1
    assert c.replies[0].slug == "thanks"
    assert c.replies[0].creator == "charlie"


def test_dict_to_topic():
    d = {
        "topic_id": 7,
        "slug": "design",
        "message": "Design thread",
        "audience": "public",
        "status": "active",
        "num_comments": 1,
        "likes": 0,
        "dislikes": 0,
        "edited": False,
        "created": "2025-01-01T00:00:00Z",
        "updated": "2025-01-01T00:00:00Z",
        "creator": {"username": "alice"},
        "comments": [
            {
                "comment_id": 10,
                "slug": "nice",
                "message": "Nice!",
                "depth": 1,
                "creator": {"username": "bob"},
                "replies": [],
            }
        ],
    }
    t = _dict_to_topic(d)
    assert t.slug == "design"
    assert t.creator == "alice"
    assert t.ref == "@alice~design"
    assert len(t.comments) == 1
    assert t.comments[0].ref == "@bob~nice"


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


def test_context_threads_base():
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    ctx = Context("/u/alice/p/myplot", config_path=config_file)
    assert ctx._threads_base == "vis/plots/myplot/threads"
    assert ctx._user == "alice"
    assert ctx._vis_type == "plots"
    assert ctx._vis_id == "myplot"


def test_context_comment_chain():
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    ctx = Context("/u/alice/p/myplot/c/@sen~topic/c/@bob~reply", config_path=config_file)
    assert ctx._threads_base == "vis/plots/myplot/threads"
    assert ctx._user == "alice"
    assert ctx._comment_chain == ["@sen~topic", "@bob~reply"]


def test_context_user_only_no_threads():
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    ctx = Context("/u/alice", config_path=config_file)
    with pytest.raises(RuntimeError, match="does not reference a visualization"):
        _ = ctx._threads_base


def test_context_topic_and_comment_navigation():
    """Test that .topic and .comment navigate the loaded tree."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    ctx = Context(
        "/u/alice/p/myplot/c/@alice~design/c/@bob~nice/c/@charlie~thanks",
        config_path=config_file,
    )
    # Inject a pre-built tree to avoid GQL calls
    ctx._raw_topics = []
    ctx._topics = [
        Topic(
            slug="design",
            message="Design thread",
            creator="alice",
            comments=[
                Comment(
                    slug="nice",
                    message="Nice!",
                    creator="bob",
                    depth=1,
                    replies=[
                        Comment(slug="thanks", message="Thanks!", creator="charlie", depth=2),
                    ],
                ),
            ],
        ),
    ]

    assert ctx.topic is not None
    assert ctx.topic.ref == "@alice~design"
    assert ctx.comment is not None
    assert ctx.comment.ref == "@charlie~thanks"


def test_context_reply_with_chain(requests_mock):
    import re

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    threads_re = re.compile(r".*/vis/plots/myplot/threads/.*")
    requests_mock.register_uri("PUT", threads_re, status_code=201)
    requests_mock.register_uri("POST", threads_re, status_code=200)

    # FQNP with /c/ chain — reply() builds the full REST path
    ctx = Context("/u/alice/p/myplot/c/@sen~topic/c/@bob~reply", config_path=config_file)
    ctx.reply("Great point!")

    history = requests_mock.request_history
    put_reqs = [r for r in history if r.method == "PUT" and "threads" in r.path]
    post_reqs = [r for r in history if r.method == "POST" and "threads" in r.path]
    assert len(put_reqs) >= 1
    assert len(post_reqs) >= 1
    # Should build full chain: topic/comments/comment/comments/@me~slug
    assert "@sen~topic/comments/@bob~reply/comments/@sondov~r" in put_reqs[-1].path
    assert "/msg" in post_reqs[-1].path


def test_context_reply_with_title(requests_mock):
    import re

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    threads_re = re.compile(r".*/vis/plots/myplot/threads/.*")
    requests_mock.register_uri("PUT", threads_re, status_code=201)
    requests_mock.register_uri("POST", threads_re, status_code=200)

    ctx = Context("/u/alice/p/myplot/c/@sen~topic", config_path=config_file)
    ctx.reply("I agree!", title="agreed")

    history = requests_mock.request_history
    put_reqs = [r for r in history if r.method == "PUT" and "threads" in r.path]
    # Slug should be "agreed", not auto-generated
    assert "@sen~topic/comments/@sondov~agreed" in put_reqs[-1].path


def test_context_reply_deep_chain(requests_mock):
    import re

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    threads_re = re.compile(r".*/vis/plots/myplot/threads/.*")
    requests_mock.register_uri("PUT", threads_re, status_code=201)
    requests_mock.register_uri("POST", threads_re, status_code=200)

    # 4-level deep chain
    ctx = Context(
        "/u/alice/p/myplot/c/@sen~topic/c/@bob~mid/c/@charlie~leaf",
        config_path=config_file,
    )
    ctx.reply("Deep reply!", title="deeper")

    history = requests_mock.request_history
    put_reqs = [r for r in history if r.method == "PUT" and "threads" in r.path]
    expected = "@sen~topic/comments/@bob~mid/comments/@charlie~leaf/comments/@sondov~deeper"
    assert expected in put_reqs[-1].path


# ---------------------------------------------------------------------------
# Mention resolution
# ---------------------------------------------------------------------------


def test_resolve_mentions_basic():
    mentions = [{"nonce": "_m0123456789abcdef", "user": {"username": "alice"}}]
    msg = "Hey @_m0123456789abcdef check this out"
    result = _resolve_mentions(msg, mentions)
    assert result == "Hey @alice check this out"


def test_resolve_mentions_multiple():
    mentions = [
        {"nonce": "_maaaaaaaaaaaaaaaa", "user": {"username": "alice"}},
        {"nonce": "_mbbbbbbbbbbbbbbbb", "user": {"username": "bob"}},
    ]
    msg = "@_maaaaaaaaaaaaaaaa and @_mbbbbbbbbbbbbbbbb please review"
    result = _resolve_mentions(msg, mentions)
    assert result == "@alice and @bob please review"


def test_resolve_mentions_none():
    assert _resolve_mentions("no mentions here", None) == "no mentions here"
    assert _resolve_mentions("no mentions here", []) == "no mentions here"


def test_resolve_mentions_unknown_nonce():
    msg = "Hey @_m0000000000000000 unknown"
    result = _resolve_mentions(msg, [])
    assert result == msg


# ---------------------------------------------------------------------------
# VDE variable formatting
# ---------------------------------------------------------------------------


def test_format_var_percent():
    assert _format_var_value("0.1523", "+,.1%", "relative", "0") == "+15.2%"


def test_format_var_percent_negative():
    assert _format_var_value("-0.05", "+,.1%", "relative", "0") == "\u22125.0%"


def test_format_var_float():
    assert _format_var_value("3.14159", ".2f", "number", None) == "3.14"


def test_format_var_float_comma():
    assert _format_var_value("1234567.89", ",.0f", "number", None) == "1,234,568"


def test_format_var_money():
    assert _format_var_value("1234.5", "$2m", "number", None) == "$1,234.50"


def test_format_var_text():
    assert _format_var_value("hello world", "st", "text", None) == "hello world"


def test_format_var_date():
    assert _format_var_value("2025-03-12", "%Y-%m-%d", "date", None) == "2025-03-12"


def test_format_var_none():
    assert _format_var_value(None, "+,.1%", "relative", "0") == ""


def test_format_var_nan():
    assert _format_var_value("not-a-number", ".2f", "number", None) == "not-a-number"


def test_format_var_no_format():
    assert _format_var_value("42", None, None, None) == "42"


# ---------------------------------------------------------------------------
# VDE variable ANSI rendering
# ---------------------------------------------------------------------------


def test_render_vde_var_ansi_up():
    result = _render_vde_var_ansi("0.15", "+,.1%", "relative", "0")
    assert "\u25b2" in result  # up triangle
    assert "+15.0%" in result
    assert "\033[48;5;22m" in result  # green background


def test_render_vde_var_ansi_down():
    result = _render_vde_var_ansi("-0.05", "+,.1%", "relative", "0")
    assert "\u25bc" in result  # down triangle
    assert "\033[48;5;52m" in result  # red background


def test_render_vde_var_ansi_neutral():
    result = _render_vde_var_ansi("42", ".2f", "absolute", None)
    assert "\u25b2" not in result
    assert "\u25bc" not in result
    assert "42.00" in result
    assert "\033[48;5;236m" in result  # gray background pill


# ---------------------------------------------------------------------------
# Var lookup building
# ---------------------------------------------------------------------------


def test_build_var_lookup():
    vde_vars = [
        {"id": "revenue", "value": "1000", "format": ",.0f", "type": "number", "threshold": None},
        {"id": "growth", "value": "0.15", "format": "+,.1%", "type": "relative", "threshold": "0"},
    ]
    lookup = _build_var_lookup(vde_vars, "alice", "plots", "myplot")
    assert "/u/alice/p/myplot/v/revenue" in lookup
    assert "/u/alice/p/myplot/v/growth" in lookup
    assert lookup["/u/alice/p/myplot/v/revenue"]["value"] == "1000"


# ---------------------------------------------------------------------------
# Full message processing
# ---------------------------------------------------------------------------


def test_process_message_mentions_and_vars():
    mentions = [{"nonce": "_maaaaaaaaaaaaaaaa", "user": {"username": "alice"}}]
    var_lookup = {
        "/u/bob/p/dashboard/v/ytd": {"value": "0.12", "format": "+,.1%", "type": "relative", "threshold": "0"},
    }
    msg = "Hey @_maaaaaaaaaaaaaaaa, YTD return is {/u/bob/p/dashboard/v/ytd}"
    result = _process_message(msg, mentions, var_lookup)
    assert "@alice" in result
    assert "+12.0%" in result
    assert "{" not in result


def test_process_message_unknown_var():
    # When a var is in the lookup but not found, show path in gray
    var_lookup = {"/u/other/p/x/v/y": {"value": "1", "format": None, "type": None, "threshold": None}}
    msg = "Check {/u/unknown/p/test/v/missing}"
    result = _process_message(msg, None, var_lookup)
    assert "/u/unknown/p/test/v/missing" in result
    assert "{" not in result


# ---------------------------------------------------------------------------
# Inline markdown rendering
# ---------------------------------------------------------------------------


def test_inline_bold():
    result = _render_inline_ansi("Hello **world**")
    assert "\033[1m" in result
    assert "world" in result
    assert "**" not in result


def test_inline_italic():
    result = _render_inline_ansi("Hello *world*")
    assert "\033[3m" in result
    assert "world" in result
    assert result.count("*") == 0


def test_inline_code():
    result = _render_inline_ansi("Use `foo()` here")
    assert "foo()" in result
    assert "`" not in result
    assert "\033[48;5;236m" in result  # gray background


def test_inline_strikethrough():
    result = _render_inline_ansi("This is ~~wrong~~ right")
    assert "\033[9m" in result
    assert "wrong" in result
    assert "~~" not in result


def test_inline_link():
    result = _render_inline_ansi("See [docs](https://example.com)")
    assert "\033[4m" in result  # underline
    assert "docs" in result
    assert "https://example.com" in result
    assert "[docs]" not in result


def test_inline_mention_with_map():
    mention_map = {"_maaaaaaaaaaaaaaaa": "alice"}
    result = _render_inline_ansi("Hey @_maaaaaaaaaaaaaaaa", mention_map)
    assert "@alice" in result
    assert "_m" not in result


def test_inline_vde_var():
    var_lookup = {"/u/bob/p/dash/v/ret": {"value": "0.1", "format": "+,.1%", "type": "relative", "threshold": "0"}}
    result = _render_inline_ansi("Return is {/u/bob/p/dash/v/ret}", var_lookup=var_lookup)
    assert "+10.0%" in result
    assert "{" not in result


def test_inline_nested_bold_italic():
    result = _render_inline_ansi("**bold and *italic* text**")
    assert "\033[1m" in result  # bold
    assert "bold and" in result


# ---------------------------------------------------------------------------
# Block-level message rendering
# ---------------------------------------------------------------------------


def test_message_lines_code_block():
    msg = "Look:\n```python\ndef foo():\n    pass\n```\nDone."
    lines = _render_message_lines(msg, "  ", 80)
    # Should have code block lines with gray background
    code_lines = [ln for ln in lines if "def foo():" in ln]
    assert len(code_lines) == 1
    assert "\033[48;5;236m" in code_lines[0]


def test_message_lines_heading():
    msg = "# Big Title\nSome text"
    lines = _render_message_lines(msg, "  ", 80)
    assert any("Big Title" in ln and "\033[1m" in ln for ln in lines)


def test_message_lines_blockquote():
    msg = "> quoted text\n> more quote"
    lines = _render_message_lines(msg, "  ", 80)
    assert any("\u2502" in ln and "quoted text" in ln for ln in lines)


def test_message_lines_list():
    msg = "- item one\n- item two"
    lines = _render_message_lines(msg, "  ", 80)
    assert any("\u2022" in ln and "item one" in ln for ln in lines)
    assert any("\u2022" in ln and "item two" in ln for ln in lines)


def test_message_lines_hr():
    msg = "above\n---\nbelow"
    lines = _render_message_lines(msg, "  ", 80)
    assert any("\u2500" in ln for ln in lines)


def test_message_lines_paragraph():
    msg = "Just a simple paragraph."
    lines = _render_message_lines(msg, "| ", 80)
    assert lines == ["| Just a simple paragraph."]
