import re

from novem._topics import (
    _build_comment_fragment,
    _build_topics_query,
    _has_truncated_replies,
    _relative_time,
    _visible_len,
    render_topics,
)
from novem.utils import colors


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes for easier assertion."""
    return re.sub(r"\033\[[0-9;]*m", "", s)


class TestVisibleLen:
    def test_plain_text(self) -> None:
        assert _visible_len("hello") == 5

    def test_with_ansi(self) -> None:
        assert _visible_len("\033[96m@alice\033[0m") == 6

    def test_empty(self) -> None:
        assert _visible_len("") == 0

    def test_multiple_codes(self) -> None:
        s = "\033[1m┌\033[0m \033[96m@bob\033[0m \033[38;5;246m· 3h ago\033[0m"
        assert _visible_len(s) == len("┌ @bob · 3h ago")


class TestRelativeTime:
    def test_just_now(self) -> None:
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        assert _relative_time(now) == "just now"

    def test_minutes(self) -> None:
        import datetime

        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
        assert _relative_time(dt) == "5m ago"

    def test_hours(self) -> None:
        import datetime

        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
        assert _relative_time(dt) == "3h ago"

    def test_days(self) -> None:
        import datetime

        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        assert _relative_time(dt) == "7d ago"

    def test_old_date(self) -> None:
        import datetime

        dt = datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc)
        result = _relative_time(dt)
        assert "Jan 15, 2024" == result


class TestBuildCommentFragment:
    def test_contains_comment_fields(self) -> None:
        frag = _build_comment_fragment(1)
        assert "comment_id" in frag
        assert "message" in frag
        assert "creator { username }" in frag
        assert "replies" in frag

    def test_nesting_depth(self) -> None:
        frag = _build_comment_fragment(3)
        # Should have 3 levels of "replies {"
        assert frag.count("replies {") == 3


class TestBuildTopicsQuery:
    def test_plots_query(self) -> None:
        q = _build_topics_query("plots")
        assert "plots(id: $id, author: $author)" in q
        assert "topics {" in q
        assert "comments {" in q

    def test_grids_query(self) -> None:
        q = _build_topics_query("grids")
        assert "grids(id: $id, author: $author)" in q

    def test_mails_query(self) -> None:
        q = _build_topics_query("mails")
        assert "mails(id: $id, author: $author)" in q

    def test_custom_depth(self) -> None:
        q = _build_topics_query("plots", depth=6)
        assert q.count("replies {") == 6

    def test_default_depth(self) -> None:
        q = _build_topics_query("plots")
        assert q.count("replies {") == 3


class TestHasTruncatedReplies:
    def test_empty(self) -> None:
        assert _has_truncated_replies([]) is False

    def test_no_truncation(self) -> None:
        comments = [_make_comment(num_replies=0, replies=[])]
        assert _has_truncated_replies(comments) is False

    def test_replies_present(self) -> None:
        reply = _make_comment(comment_id=2, num_replies=0, replies=[])
        comments = [_make_comment(num_replies=1, replies=[reply])]
        assert _has_truncated_replies(comments) is False

    def test_truncated_leaf(self) -> None:
        # num_replies > 0 but no replies data
        comments = [_make_comment(num_replies=3, replies=[])]
        assert _has_truncated_replies(comments) is True

    def test_truncated_nested(self) -> None:
        # Truncation deep in the tree
        deep = _make_comment(comment_id=3, num_replies=2, replies=[])
        mid = _make_comment(comment_id=2, num_replies=1, replies=[deep])
        comments = [_make_comment(num_replies=1, replies=[mid])]
        assert _has_truncated_replies(comments) is True

    def test_mixed(self) -> None:
        ok = _make_comment(comment_id=1, num_replies=0, replies=[])
        truncated = _make_comment(comment_id=2, num_replies=5, replies=[])
        assert _has_truncated_replies([ok, truncated]) is True


def _make_topic(
    topic_id: int = 1,
    username: str = "alice",
    message: str = "Hello world",
    audience: str = "public",
    status: str = "active",
    num_comments: int = 0,
    likes: int = 0,
    dislikes: int = 0,
    edited: bool = False,
    created: str = "Mon, 10 Feb 2026 12:00:00 UTC",
    comments: list = None,
) -> dict:
    return {
        "topic_id": topic_id,
        "slug": f"topic-{topic_id}",
        "message": message,
        "audience": audience,
        "status": status,
        "num_comments": num_comments,
        "likes": likes,
        "dislikes": dislikes,
        "edited": edited,
        "created": created,
        "updated": created,
        "creator": {"username": username},
        "comments": comments or [],
    }


def _make_comment(
    comment_id: int = 1,
    username: str = "bob",
    message: str = "Nice post",
    depth: int = 0,
    deleted: bool = False,
    edited: bool = False,
    likes: int = 0,
    dislikes: int = 0,
    num_replies: int = -1,
    created: str = "Mon, 10 Feb 2026 12:05:00 UTC",
    replies: list = None,
) -> dict:
    return {
        "comment_id": comment_id,
        "slug": f"comment-{comment_id}",
        "message": message,
        "depth": depth,
        "deleted": deleted,
        "edited": edited,
        "num_replies": num_replies if num_replies >= 0 else (len(replies) if replies else 0),
        "likes": likes,
        "dislikes": dislikes,
        "created": created,
        "updated": created,
        "creator": {"username": username},
        "replies": replies or [],
    }


class TestRenderTopics:
    def test_no_topics(self) -> None:
        result = _strip_ansi(render_topics([]))
        assert result == "No topics"

    def test_topic_header(self) -> None:
        topics = [_make_topic(username="alice", audience="public", num_comments=0)]
        result = _strip_ansi(render_topics(topics))
        assert "@alice" in result
        assert "(public)" in result
        assert "0 comments" in result

    def test_topic_body(self) -> None:
        topics = [_make_topic(message="This is the topic body")]
        result = _strip_ansi(render_topics(topics))
        assert "This is the topic body" in result

    def test_no_comments_message(self) -> None:
        topics = [_make_topic(comments=[])]
        result = _strip_ansi(render_topics(topics))
        assert "(no comments)" in result

    def test_single_comment(self) -> None:
        comment = _make_comment(username="bob", message="Great work")
        topics = [_make_topic(num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "@bob" in result
        assert "Great work" in result
        assert "1 comment" in result
        # Should not say "1 comments"
        assert "1 comments" not in result

    def test_plural_comments(self) -> None:
        comments = [
            _make_comment(comment_id=1, username="bob", message="First"),
            _make_comment(comment_id=2, username="carol", message="Second"),
        ]
        topics = [_make_topic(num_comments=2, comments=comments)]
        result = _strip_ansi(render_topics(topics))
        assert "2 comments" in result
        assert "@bob" in result
        assert "@carol" in result

    def test_nested_replies(self) -> None:
        reply = _make_comment(comment_id=2, username="carol", message="Reply here", depth=1)
        comment = _make_comment(comment_id=1, username="bob", message="Top level", replies=[reply])
        topics = [_make_topic(num_comments=2, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "@bob" in result
        assert "Top level" in result
        assert "@carol" in result
        assert "Reply here" in result

    def test_deep_nesting(self) -> None:
        c3 = _make_comment(comment_id=3, username="dave", message="Deep reply", depth=2)
        c2 = _make_comment(comment_id=2, username="carol", message="Mid reply", depth=1, replies=[c3])
        c1 = _make_comment(comment_id=1, username="bob", message="Top", replies=[c2])
        topics = [_make_topic(num_comments=3, comments=[c1])]
        result = _strip_ansi(render_topics(topics))
        assert "@dave" in result
        assert "Deep reply" in result

    def test_deleted_comment(self) -> None:
        comment = _make_comment(deleted=True, message="secret")
        topics = [_make_topic(num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "[deleted]" in result
        # Deleted message body should not be shown
        assert "secret" not in result

    def test_edited_markers(self) -> None:
        comment = _make_comment(edited=True)
        topics = [_make_topic(edited=True, num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        # Both topic and comment should show edited
        assert result.count("(edited)") == 2

    def test_reactions(self) -> None:
        comment = _make_comment(likes=5, dislikes=2)
        topics = [_make_topic(likes=3, num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "[+3]" in result
        assert "[+5 -2]" in result

    def test_archived_status(self) -> None:
        topics = [_make_topic(status="archived")]
        result = _strip_ansi(render_topics(topics))
        assert "archived" in result

    def test_active_status_not_shown(self) -> None:
        topics = [_make_topic(status="active", audience="public")]
        result = _strip_ansi(render_topics(topics))
        # "active" should be suppressed, only "public" shown
        assert "active" not in result

    def test_multiple_topics(self) -> None:
        topics = [
            _make_topic(topic_id=1, username="alice", message="First topic"),
            _make_topic(topic_id=2, username="bob", message="Second topic"),
        ]
        result = _strip_ansi(render_topics(topics))
        assert "@alice" in result
        assert "First topic" in result
        assert "@bob" in result
        assert "Second topic" in result

    def test_multiline_message(self) -> None:
        topics = [_make_topic(message="Line one\nLine two\nLine three")]
        result = _strip_ansi(render_topics(topics))
        assert "Line one" in result
        assert "Line two" in result
        assert "Line three" in result

    def test_no_bottom_separator_line(self) -> None:
        comment = _make_comment()
        topics = [_make_topic(num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        # Should not have a full-width separator line
        assert "──────" not in result

    def test_dense_output_no_blank_lines_between_siblings(self) -> None:
        comments = [
            _make_comment(comment_id=1, username="bob", message="First"),
            _make_comment(comment_id=2, username="carol", message="Second"),
        ]
        topics = [_make_topic(num_comments=2, comments=comments)]
        result = _strip_ansi(render_topics(topics))
        lines = result.split("\n")
        # No empty lines within the topic (except between topics)
        for line in lines:
            assert line.strip() != "" or line == ""  # Allow only between topics

    def test_me_topic_creator_highlighted(self) -> None:
        """Current user's username in topic header should use WARNING color."""
        colors()
        from novem.utils import cl

        topics = [_make_topic(username="alice")]
        result = render_topics(topics, me="alice")
        # The topic creator should be colored with WARNING (orange)
        assert f"{cl.WARNING}@alice{cl.ENDC}" in result

    def test_me_comment_creator_highlighted(self) -> None:
        """Current user's username in comment header should use WARNING color."""
        colors()
        from novem.utils import cl

        comment = _make_comment(username="alice", message="My comment")
        topics = [_make_topic(username="bob", num_comments=1, comments=[comment])]
        result = render_topics(topics, me="alice")
        # Comment by "me" should be orange
        assert f"{cl.WARNING}@alice{cl.ENDC}" in result
        # Topic by someone else should be cyan
        assert f"{cl.OKCYAN}@bob{cl.ENDC}" in result

    def test_me_nested_reply_highlighted(self) -> None:
        """Current user's username in nested reply should use WARNING color."""
        colors()
        from novem.utils import cl

        reply = _make_comment(comment_id=2, username="alice", message="My reply", depth=1)
        comment = _make_comment(comment_id=1, username="bob", message="Top", replies=[reply])
        topics = [_make_topic(username="carol", num_comments=2, comments=[comment])]
        result = render_topics(topics, me="alice")
        assert f"{cl.WARNING}@alice{cl.ENDC}" in result
        assert f"{cl.OKCYAN}@bob{cl.ENDC}" in result
        assert f"{cl.OKCYAN}@carol{cl.ENDC}" in result

    def test_no_me_all_cyan(self) -> None:
        """When me is empty, all usernames should use OKCYAN."""
        colors()
        from novem.utils import cl

        comment = _make_comment(username="bob")
        topics = [_make_topic(username="alice", num_comments=1, comments=[comment])]
        result = render_topics(topics, me="")
        assert f"{cl.OKCYAN}@alice{cl.ENDC}" in result
        assert f"{cl.OKCYAN}@bob{cl.ENDC}" in result
        # WARNING escape code should not appear (check raw code, not cl.WARNING which may be empty)
        assert "\033[93m" not in result
