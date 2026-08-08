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


def test_first_c_becomes_computer_selector():
    assert promoted(["-c", "my-box", "-w", "status", "reboot"]) == ["--computer", "my-box", "-w", "status", "reboot"]


def test_first_i_becomes_image_selector():
    assert promoted(["-i"]) == ["--image"]


def test_only_first_of_the_four_is_promoted():
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


def test_config_path_with_resource_keeps_c():
    argv = ["-c", "./test.conf", "-p", "my-plot"]
    assert promoted(argv) == argv


def test_early_exit_commands_block_promotion():
    for blocker in (["--init"], ["--info"], ["--refresh"], ["--version"], ["--add-ssh-key"]):
        argv = blocker + ["-c", "./test.conf"]
        assert promoted(argv) == argv, blocker


def test_raw_http_blocks_promotion():
    argv = ["--get", "/vis/plots", "-c", "./test.conf"]
    assert promoted(argv) == argv


def test_gql_blocks_promotion():
    argv = ["--gql", "-c", "./test.conf"]
    assert promoted(argv) == argv


def test_org_group_bare_selector_promotes():
    # bare -s with -O/-G means "list the group's spaces"
    assert promoted(["-O", "myorg", "-G", "mygroup", "-s"]) == ["-O", "myorg", "-G", "mygroup", "--space"]
    assert promoted(["-O", "myorg", "-G", "mygroup", "-r"]) == ["-O", "myorg", "-G", "mygroup", "--repo"]
    assert promoted(["-O", "myorg", "-G", "mygroup", "-c"]) == ["-O", "myorg", "-G", "mygroup", "--computer"]
    assert promoted(["-O", "myorg", "-G", "mygroup", "-i"]) == ["-O", "myorg", "-G", "mygroup", "--image"]


def test_org_group_valued_selector_keeps_legacy():
    # a valued -c in group context is still the config file
    argv = ["-O", "myorg", "-G", "mygroup", "-c", "./test.conf", "-C"]
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
    _, args = setup(["-p", "my-plot", "-r", "url", "-c", "./test.conf"])
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
