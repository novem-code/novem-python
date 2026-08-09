"""Tests for the code-resource selector promotion (-s/-r/-c/-i).

The overloaded short flags double as resource selectors when nothing else
claims the invocation; see promote_code_selectors in novem/cli/setup.py.
"""

from novem.cli.setup import promote_code_selectors, setup


def promoted(argv):
    return promote_code_selectors(argv)


# --- token rewriting -------------------------------------------------------


def test_first_r_becomes_repo_selector():
    assert promoted(["-r", "my-repo", "-r", "url"]) == ["--repo", "my-repo", "-r", "url"]


def test_first_s_becomes_space_selector():
    assert promoted(["-s", "my-space", "-s", "public", "-C"]) == ["--space", "my-space", "-s", "public", "-C"]


def test_c_needs_no_promotion():
    # -c belongs to --computer outright, so promotion leaves it alone and
    # it also claims the invocation for the later shorts
    argv = ["-c", "my-box", "-w", "status", "reboot"]
    assert promoted(argv) == argv
    argv = ["-c", "my-box", "-r", "log"]
    assert promoted(argv) == argv


def test_first_i_becomes_image_selector():
    assert promoted(["-i"]) == ["--image"]


def test_only_the_first_selector_is_promoted():
    # -s claims the invocation; the later -r keeps its read meaning
    assert promoted(["-s", "sp", "-r", "url"]) == ["--space", "sp", "-r", "url"]


def test_global_flags_before_selector_do_not_block():
    assert promoted(["--profile", "work", "-r", "my-repo", "-r", "url"]) == [
        "--profile",
        "work",
        "--repo",
        "my-repo",
        "-r",
        "url",
    ]


# --- legacy meanings preserved ---------------------------------------------


def test_plot_selector_keeps_share_and_read_flags():
    argv = ["-p", "my-plot", "-s", "public", "-C", "-r", "url"]
    assert promoted(argv) == argv


def test_selector_later_in_argv_still_blocks_promotion():
    # order independence: -p anywhere keeps -s/-r legacy
    argv = ["-s", "public", "-C", "-p", "my-plot"]
    assert promoted(argv) == argv


def test_job_upload_dir_keeps_i():
    argv = ["-j", "my-job", "-R", "-i", "data/"]
    assert promoted(argv) == argv


def test_config_path_is_long_form_only():
    argv = ["--config", "./test.conf", "-p", "my-plot"]
    assert promoted(argv) == argv
    argv = ["--config-path", "./test.conf", "-s", "public", "-C", "-p", "my-plot"]
    assert promoted(argv) == argv


def test_early_exit_commands_block_promotion():
    for blocker in (["--init"], ["--info"], ["--refresh"], ["--version"], ["--add-ssh-key"]):
        argv = blocker + ["-i", "data/"]
        assert promoted(argv) == argv, blocker


def test_raw_http_blocks_promotion():
    argv = ["--get", "/vis/plots", "-i", "data/"]
    assert promoted(argv) == argv


def test_gql_bare_only_promotion():
    # bare --gql + bare selector: promote (debug the listing)
    assert promoted(["--gql", "-s"]) == ["--gql", "--space"]
    # bare --gql + valued short: legacy meaning holds (stdin query + input dir)
    argv = ["--gql", "-i", "data/"]
    assert promoted(argv) == argv


def test_org_group_bare_selector_promotes():
    # bare -s with -O/-G means "list the group's spaces"
    assert promoted(["-O", "myorg", "-G", "mygroup", "-s"]) == ["-O", "myorg", "-G", "mygroup", "--space"]
    assert promoted(["-O", "myorg", "-G", "mygroup", "-r"]) == ["-O", "myorg", "-G", "mygroup", "--repo"]
    assert promoted(["-O", "myorg", "-G", "mygroup", "-i"]) == ["-O", "myorg", "-G", "mygroup", "--image"]


def test_org_group_valued_selector_keeps_legacy():
    # a valued -i in group context is still the input directory
    argv = ["-O", "myorg", "-G", "mygroup", "-i", "data/", "-C"]
    assert promoted(argv) == argv


def test_org_invite_flow_untouched():
    argv = ["-O", "myorg", "-G", "analysts", "--invite", "bob"]
    assert promoted(argv) == argv
    argv = ["--invite", "bob", "-G", "analysts", "-C"]
    assert promoted(argv) == argv


def test_long_selector_blocks_short_promotion():
    # --space claims the invocation, the -s keeps its share meaning
    argv = ["--space", "sp", "-s", "public", "-C"]
    assert promoted(argv) == argv


def test_double_dash_ends_scan():
    argv = ["--", "-r", "x"]
    assert promoted(argv) == argv


def test_attached_short_values():
    # attached selector value promotes into the long= form
    assert promoted(["-smy-space"]) == ["--space=my-space"]
    assert promoted(["-rmy-repo", "-r", "url"]) == ["--repo=my-repo", "-r", "url"]
    # attached values on other selectors block promotion like separated ones
    argv = ["-pmy-plot", "-s", "public", "-C"]
    assert promoted(argv) == argv
    argv = ["-umeuser", "-s", "team"]  # attached -u value scopes, doesn't block
    assert promoted(argv) == ["-umeuser", "--space", "team"]


def test_gql_valued_blocks_promotion():
    # valued --gql runs a standalone query: legacy meanings hold
    argv = ["--gql", "@query.gql", "-c", "./test.conf"]
    assert promoted(argv) == argv
    argv = ["--gql", "query { me }", "-s"]
    assert promoted(argv) == argv


def test_empty_argv():
    assert promoted([]) == []


# --- through argparse ------------------------------------------------------


def test_setup_repo_selector_and_read():
    _, args = setup(["-r", "my-repo", "-r", "url"])
    assert args["repo"] == "my-repo"
    assert args["out"] == "url"


def test_setup_space_share_create():
    from novem.cli.setup import Share

    _, args = setup(["-s", "my-space", "-s", "public", "-C"])
    assert args["space"] == "my-space"
    assert args["share"] == (Share.CREATE, "public")
    assert args["create"] is False  # consumed by the share op


def test_setup_bare_selectors_list():
    _, args = setup(["-s"])
    assert args["space"] is None
    _, args = setup(["-r"])
    assert args["repo"] is None
    _, args = setup(["-c"])
    assert args["computer"] is None
    _, args = setup(["-i"])
    assert args["image"] is None


def test_setup_plot_keeps_legacy_flags():
    _, args = setup(["-p", "my-plot", "-r", "url", "--config", "./test.conf"])
    assert args["plot"] == "my-plot"
    assert args["out"] == "url"
    assert args["config_path"] == "./test.conf"
    assert args["repo"] == ""
    assert args["computer"] == ""


def test_setup_computer_create_with_config_write():
    _, args = setup(["-c", "my-box", "-C", "-w", "config/cpu", "4"])
    assert args["computer"] == "my-box"
    assert args["create"] is True
    assert args["input"] == [["config/cpu", "4"]]


def test_setup_counted_create_covers_resource_and_share():
    from novem.cli.setup import Share

    # one -C per action: create the space AND add the share
    _, args = setup(["-s", "my-space", "-C", "-s", "public", "-C"])
    assert args["space"] == "my-space"
    assert args["share"] == (Share.CREATE, "public")
    assert args["create"] is True

    # a single -C is consumed by the share op, like before
    _, args = setup(["-s", "my-space", "-s", "public", "-C"])
    assert args["share"] == (Share.CREATE, "public")
    assert args["create"] is False


def test_setup_counted_create_share_and_tag():
    from novem.cli.setup import Share, Tag

    _, args = setup(["-p", "my-plot", "-C", "-s", "public", "-C", "-t", "fav", "-C"])
    assert args["share"] == (Share.CREATE, "public")
    assert args["tag"] == (Tag.CREATE, ["fav"])
    assert args["create"] is True


def test_setup_counted_delete():
    from novem.cli.setup import Share

    # one -D removes only the share, two remove share and resource
    _, args = setup(["-s", "my-space", "-s", "public", "-D"])
    assert args["share"] == (Share.DELETE, "public")
    assert args["delete"] is False

    _, args = setup(["-s", "my-space", "-s", "public", "-D", "-D"])
    assert args["share"] == (Share.DELETE, "public")
    assert args["delete"] is True


def test_valued_share_and_tag_without_an_op_are_checks():
    from novem.cli.setup import Share, Tag

    # bare -s/-t still list
    _, args = setup(["-p", "my-plot", "-s"])
    assert args["share"] == (Share.LIST, None)
    _, args = setup(["-p", "my-plot", "-t"])
    assert args["tag"] == (Tag.LIST, None)

    # with a value and no -C/-D they ask whether it is already there
    _, args = setup(["-p", "my-plot", "-s", "public"])
    assert args["share"] == (Share.CHECK, "public")
    _, args = setup(["-p", "my-plot", "-t", "fav"])
    assert args["tag"] == (Tag.CHECK, ["fav"])

    # a comma-separated list checks every tag
    _, args = setup(["-p", "my-plot", "-t", "fav,+demo"])
    assert args["tag"] == (Tag.CHECK, ["fav", "+demo"])

    # -C/-D still create and delete
    _, args = setup(["-p", "my-plot", "-s", "public", "-C"])
    assert args["share"] == (Share.CREATE, "public")
    _, args = setup(["-p", "my-plot", "-t", "fav", "-D"])
    assert args["tag"] == (Tag.DELETE, ["fav"])


def test_every_long_flag_is_classified():
    """Promotion is driven by deny-lists, which rot silently as flags are
    added. Every long option the parser knows about must be classified, so a
    new flag forces the author to decide whether it claims the invocation."""
    from novem.cli.setup import _PRIMARY_SELECTOR_FLAGS, _PROMOTION_BLOCKERS, _PROMOTION_NEUTRAL

    parser, _ = setup([])
    longs = {o for a in parser._actions for o in a.option_strings if o.startswith("--")}

    # --gql is special-cased in promote_code_selectors: bare toggles debug
    # output, valued runs a standalone query
    classified = _PRIMARY_SELECTOR_FLAGS | _PROMOTION_BLOCKERS | _PROMOTION_NEUTRAL | {"--gql"}

    unclassified = sorted(longs - classified)
    assert not unclassified, (
        f"unclassified long flags: {unclassified}. Add each to _PROMOTION_BLOCKERS (it claims the "
        f"invocation for something other than a coding resource) or _PROMOTION_NEUTRAL (it does not)."
    )

    stale = sorted(f for f in classified - longs if f.startswith("--"))
    assert not stale, f"classified flags the parser no longer has: {stale}"


def test_inbox_blocks_promotion():
    # --inbox is a standalone listing; -c keeps its config-path meaning
    assert promoted(["--inbox", "-i", "data/"]) == ["--inbox", "-i", "data/"]


def test_config_alias_and_c_is_computer_only():
    """-c belongs to --computer outright; the config file needs the long form."""
    # --config is an alias for --config-path
    _, args = setup(["--config", "./test.conf", "-p", "my-plot"])
    assert args["config_path"] == "./test.conf"
    _, args = setup(["--config-path", "./test.conf", "-p", "my-plot"])
    assert args["config_path"] == "./test.conf"

    # -c selects a computer, and never touches config_path
    _, args = setup(["-c", "my-box"])
    assert args["computer"] == "my-box"
    assert args["config_path"] is None

    # the attached form comes for free now that argparse owns -c
    _, args = setup(["-cmy-box"])
    assert args["computer"] == "my-box"

    # -c claims the invocation, so the later shorts keep their legacy meaning
    _, args = setup(["-c", "my-box", "-r", "log"])
    assert args["computer"] == "my-box"
    assert args["out"] == "log"


def test_path_shaped_computer_name_is_rejected():
    """The old `-c ~/my.conf` muscle memory must not silently run against the
    default profile's credentials."""
    for bad in ("./test.conf", "~/my.conf", "/etc/novem/conf"):
        try:
            setup(["-c", bad])
            assert False, f"should have errored on {bad}"
        except SystemExit as e:
            assert e.code == 2

    # a plain computer name is untouched
    _, args = setup(["-c", "my-box"])
    assert args["computer"] == "my-box"
