"""End-to-end CLI tests for the coding resources: spaces (-s), repos (-r),
computers (-c) and images (-i).

Listing goes through GraphQL (mocked at the /gql endpoint); everything else
is REST against code/{collection}/{id} (mocked with requests_mock).
"""

import sys
from functools import partial

from novem.cli.gql import _get_gql_endpoint
from novem.utils import API_ROOT
from tests.conftest import CliExit

from .utils import write_config

api_root = API_ROOT
gql_endpoint = _get_gql_endpoint(API_ROOT)

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": "cli token",
}


def _vde(id, **extra):
    return {
        "id": id,
        "name": f"Name of {id}",
        "type": "",
        "summary": f"Summary of {id}",
        "url": f"https://novem.no/x/{id}",
        "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
        "public": False,
        "shared": [],
        "tags": [],
        "social": {"views": 0},
        "topics": [],
        **extra,
    }


def _mock_me_list(requests_mock, field, items):
    requests_mock.register_uri(
        "post",
        gql_endpoint,
        json={"data": {"me": {"username": "demouser", field: items}}},
        status_code=200,
    )


# --- listing ----------------------------------------------------------------


def test_space_list(cli, requests_mock, fs):
    write_config(auth_req)
    _mock_me_list(requests_mock, "spaces", [_vde("alpha"), _vde("beta")])

    out, err = cli("-s", "-l")
    assert out.split() == ["alpha", "beta"]


def test_repo_list(cli, requests_mock, fs):
    write_config(auth_req)
    _mock_me_list(requests_mock, "repos", [_vde("tools", type="job")])

    out, err = cli("-r", "-l")
    assert out.split() == ["tools"]


def test_computer_list(cli, requests_mock, fs):
    write_config(auth_req)
    _mock_me_list(
        requests_mock,
        "computers",
        [
            _vde(
                "my-box",
                computer_type="permanent",
                status="online",
                running=True,
                dirty=False,
                image_ref="@novem/base:latest",
                cpu=2,
                memory="2Gi",
                disk="10Gi",
            )
        ],
    )

    out, err = cli("-c", "-l")
    assert out.split() == ["my-box"]

    # pretty listing carries the computer-specific columns, with
    # cpu/mem/disk as separate right-aligned columns
    out, err = cli("-c")
    assert "my-box" in out
    assert "online" in out
    assert "@novem/base:latest" in out
    header = out.split("\n")[0]
    assert "Cpu" in header and "Mem" in header and "Disk" in header
    assert "2Gi" in out and "10Gi" in out


def test_image_list(cli, requests_mock, fs):
    write_config(auth_req)
    _mock_me_list(
        requests_mock,
        "images",
        [_vde("tools", repo="@demouser/tools", status="ready", labels=["latest", "v1"])],
    )

    out, err = cli("-i", "-l")
    assert out.split() == ["tools"]

    out, err = cli("-i")
    assert "@demouser/tools" in out
    assert "ready" in out
    assert "latest, v1" in out


# --- create / write / read ---------------------------------------------------


def test_space_create_and_write(cli, requests_mock, fs):
    write_config(auth_req)

    created = {}
    written = {}

    def on_create(request, context):
        created["yes"] = True
        context.status_code = 201
        return ""

    def on_write(key, request, context):
        written[key] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("put", f"{api_root}code/spaces/my-space", text=on_create)
    requests_mock.register_uri("post", f"{api_root}code/spaces/my-space/name", text=partial(on_write, "name"))

    out, err = cli("-s", "my-space", "-C", "-w", "name", "My Space")
    assert created.get("yes")
    assert written["name"] == "My Space"


def test_repo_read_url(cli, requests_mock, fs):
    write_config(auth_req)

    requests_mock.register_uri("put", f"{api_root}code/repos/my-repo", status_code=201)
    requests_mock.register_uri(
        "get",
        f"{api_root}code/repos/my-repo/url",
        text="git@novem.no:demouser/my-repo",
        status_code=200,
    )

    out, err = cli("-r", "my-repo", "-r", "url")
    assert out == "git@novem.no:demouser/my-repo"


def test_computer_status_write(cli, requests_mock, fs):
    write_config(auth_req)

    written = {}

    def on_write(request, context):
        written["status"] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("post", f"{api_root}code/computers/my-box/status", text=on_write)

    out, err = cli("-c", "my-box", "-w", "status", "reboot")
    assert written["status"] == "reboot"


def test_computer_type_shorthand(cli, requests_mock, fs):
    write_config(auth_req)

    written = {}

    def on_write(request, context):
        written["type"] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("post", f"{api_root}code/computers/my-box/config/type", text=on_write)

    out, err = cli("-c", "my-box", "--type", "ephemeral")
    assert written["type"] == "ephemeral"


def test_image_read_status(cli, requests_mock, fs):
    write_config(auth_req)

    # images are never created: no PUT is registered, so an attempted create
    # would fail the test with a requests_mock NoMockAddress error
    requests_mock.register_uri(
        "get",
        f"{api_root}code/images/tools/status",
        text="ready\n",
        status_code=200,
    )

    out, err = cli("-i", "tools", "-r", "status")
    assert out == "ready\n"


# --- delete -------------------------------------------------------------------


def test_space_delete(cli, requests_mock, fs):
    write_config(auth_req)

    deleted = {}

    def on_delete(request, context):
        deleted["yes"] = True
        context.status_code = 200
        return ""

    requests_mock.register_uri("delete", f"{api_root}code/spaces/my-space", text=on_delete)

    out, err = cli("-s", "my-space", "-D")
    assert deleted.get("yes")


def test_repo_delete_missing(cli, requests_mock, fs):
    write_config(auth_req)

    requests_mock.register_uri("delete", f"{api_root}code/repos/nope", status_code=404)

    try:
        cli("-r", "nope", "-D")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "Repo nope did not exist" in out


def test_image_create_delete_rejected(cli, requests_mock, fs):
    write_config(auth_req)

    try:
        cli("-i", "tools", "-D")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "derived from their source repo" in out

    try:
        cli("-i", "tools", "-C")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "derived from their source repo" in out


# --- shares and tags ----------------------------------------------------------


def test_space_share_public(cli, requests_mock, fs):
    write_config(auth_req)

    shared = {}

    def on_share(request, context):
        shared["yes"] = True
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{api_root}code/spaces/my-space", status_code=201)
    requests_mock.register_uri("get", f"{api_root}code/spaces/my-space/shared", json=[], status_code=200)
    requests_mock.register_uri("put", f"{api_root}code/spaces/my-space/shared/public", text=on_share)

    # exactly the flow from the design doc: novem -s space_id -s public -C
    out, err = cli("-s", "my-space", "-s", "public", "-C")
    assert shared.get("yes")


def test_repo_share_list(cli, requests_mock, fs):
    write_config(auth_req)

    requests_mock.register_uri("put", f"{api_root}code/repos/my-repo", status_code=201)
    requests_mock.register_uri(
        "get",
        f"{api_root}code/repos/my-repo/shared",
        json=[{"name": "@demouser~devs", "created_on": "Thu, 17 Mar 2022 12:19:02 UTC"}],
        status_code=200,
    )

    out, err = cli("-r", "my-repo", "-s", "-l")
    assert out.strip() == "@demouser~devs"


def test_computer_tag_fav(cli, requests_mock, fs):
    write_config(auth_req)

    tagged = {}

    def on_tag(request, context):
        tagged["yes"] = True
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("get", f"{api_root}code/computers/my-box/tags", json=[], status_code=200)
    requests_mock.register_uri("put", f"{api_root}code/computers/my-box/tags/fav", text=on_tag)

    out, err = cli("-c", "my-box", "-t", "fav", "-C")
    assert tagged.get("yes")


def test_share_check_without_an_op(cli, requests_mock, fs):
    """`-s TARGET` with neither -C nor -D asks whether the share is already
    there and answers with the exit code."""
    write_config(auth_req)

    requests_mock.register_uri("get", f"{api_root}code/spaces/my-space/shared", json=[{"name": "public"}])

    try:
        cli("-s", "my-space", "-s", "public")
        assert False, "check always exits"
    except CliExit as e:
        out, err = e.args
        assert e.code == 0
        assert out == ""

    try:
        cli("-s", "my-space", "-s", "@someone")
        assert False, "check always exits"
    except CliExit as e:
        out, err = e.args
        assert e.code == 1
        assert "does not have the share @someone" in err

    # a check never creates the resource: no PUT is registered, so an
    # attempted create would fail with a requests_mock NoMockAddress error


def test_tag_check_without_an_op(cli, requests_mock, fs):
    """`-t TAG` likewise, and every tag in a comma-separated list must be
    present for the check to succeed."""
    write_config(auth_req)

    requests_mock.register_uri("get", f"{api_root}code/computers/my-box/tags", json=[{"name": "fav"}])

    try:
        cli("-c", "my-box", "-t", "fav")
        assert False, "check always exits"
    except CliExit as e:
        assert e.code == 0

    try:
        cli("-c", "my-box", "-t", "fav,+demo")
        assert False, "check always exits"
    except CliExit as e:
        out, err = e.args
        assert e.code == 1
        assert "does not have the tag +demo" in err


def test_share_check_on_a_plot(cli, requests_mock, fs):
    """The check reaches the vis resources under vis/ too."""
    write_config(auth_req)

    # no PUT registered: a check must not create the plot, or requests_mock
    # fails the test with a NoMockAddress error
    requests_mock.register_uri("get", f"{api_root}vis/plots/my-plot/shared", json=[{"name": "public"}])

    try:
        cli("-p", "my-plot", "-s", "public")
        assert False, "check always exits"
    except CliExit as e:
        assert e.code == 0


# --- for_user scoping -----------------------------------------------------------


def test_space_read_for_user(cli, requests_mock, fs):
    write_config(auth_req)

    requests_mock.register_uri(
        "get",
        f"{api_root}users/other/code/spaces/team/name",
        text="Team space",
        status_code=200,
    )

    out, err = cli("-s", "team", "-u", "other", "-r", "name")
    assert out == "Team space"


def test_space_create_and_share_one_line(cli, requests_mock, fs):
    """Each -C covers one action: create the space AND add the share."""
    write_config(auth_req)

    hits = {}

    def on(key, request, context):
        hits[key] = True
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{api_root}code/spaces/my-space", text=partial(on, "create"))
    requests_mock.register_uri("get", f"{api_root}code/spaces/my-space/shared", json=[], status_code=200)
    requests_mock.register_uri("put", f"{api_root}code/spaces/my-space/shared/public", text=partial(on, "share"))

    out, err = cli("-s", "my-space", "-C", "-s", "public", "-C")
    assert hits.get("create")
    assert hits.get("share")


def test_computer_multiple_writes_one_line(cli, requests_mock, fs):
    """Several -w PATH VALUE pairs in a single invocation."""
    write_config(auth_req)

    written = {}

    def on_write(key, request, context):
        written[key] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    for leaf in ("config/cpu", "config/memory", "config/disk", "status"):
        requests_mock.register_uri("post", f"{api_root}code/computers/my-box/{leaf}", text=partial(on_write, leaf))

    out, err = cli(
        "-c",
        "my-box",
        "-C",
        "-w",
        "config/cpu",
        "4",
        "-w",
        "config/memory",
        "4Gi",
        "-w",
        "config/disk",
        "20Gi",
        "-w",
        "status",
        "online",
    )
    assert written == {"config/cpu": "4", "config/memory": "4Gi", "config/disk": "20Gi", "status": "online"}


# --- org group listings -----------------------------------------------------------


def _mock_org_group(requests_mock, org, group, field, items):
    requests_mock.register_uri(
        "post",
        gql_endpoint,
        json={"data": {"groups": [{"id": org, "groups": [{"id": group, field: items}]}]}},
        status_code=200,
    )


def test_org_group_spaces_list(cli, requests_mock, fs):
    write_config(auth_req)
    _mock_org_group(
        requests_mock,
        "myorg",
        "crew",
        "spaces",
        [_vde("shared-space", author={"username": "alice"})],
    )

    out, err = cli("-O", "myorg", "-G", "crew", "-s", "-l")
    assert out.split() == ["alice/shared-space"]


def test_org_group_computers_list(cli, requests_mock, fs):
    write_config(auth_req)
    _mock_org_group(
        requests_mock,
        "myorg",
        "crew",
        "computers",
        [_vde("crew-box", author={"username": "alice"})],
    )

    out, err = cli("-O", "myorg", "-G", "crew", "-c", "-l")
    assert out.split() == ["alice/crew-box"]


def test_org_group_docs_list(cli, requests_mock, fs):
    write_config(auth_req)
    _mock_org_group(
        requests_mock,
        "myorg",
        "crew",
        "docs",
        [_vde("handbook", author={"username": "alice"})],
    )

    out, err = cli("-O", "myorg", "-G", "crew", "-d", "-l")
    assert out.split() == ["alice/handbook"]


def test_org_group_invite_with_config_path(cli, requests_mock, fs):
    """-c stays the config file when valued in group context."""
    write_config(auth_req)

    invited = {}

    def on_invite(request, context):
        invited["yes"] = True
        context.status_code = 201
        return ""

    # group.py builds these paths with a leading slash, hence v1//admin
    requests_mock.register_uri(
        "put",
        f"{api_root}/admin/orgs/myorg/groups/analysts/roles/members/bob",
        text=on_invite,
    )

    out, err = cli("-O", "myorg", "-G", "analysts", "--invite", "bob")
    assert invited.get("yes")


# --- invitations -------------------------------------------------------------------


def test_invites_lists_every_pending_shape(cli, requests_mock, fs):
    """/admin/invites is the whole pending picture: group and org invitations,
    inbound connection requests, your own pending personal invites and your
    active invite URLs (see gaia db/functions/api_get_invites.sql)."""
    write_config(auth_req)

    on = "Thu, 17 Mar 2022 12:19:02 UTC"
    requests_mock.register_uri(
        "get",
        f"{api_root}/admin/invites/",
        json=[
            {"name": "+acme~crew", "created_on": on},
            {"name": "@friend", "created_on": on},
            {"name": "@someone~devs", "created_on": on},
            {"name": "+acme", "created_on": on},
            {"name": "I-new@example.com", "created_on": on},
            {"name": "myhandle", "created_on": on},
        ],
        status_code=200,
    )

    out, err = cli("--invites", "-l")
    assert out.split() == [
        "+acme",
        "+acme~crew",
        "@friend",
        "@someone~devs",
        "I-new@example.com",
        "myhandle",
    ]

    out, err = cli("--invites")
    for expected in (
        "organisation group",
        "connection",
        "user group",
        "organisation",
        "personal invite",
        "invite url",
    ):
        assert expected in out, expected
    # every shape is classified: nothing falls through
    assert "unkown" not in out


def test_accept_uses_the_one_invites_endpoint(cli, requests_mock, fs):
    """Every pending invite is answered on /admin/invites/{name}/accept -
    api_accept_invite recognises a bare "@user" as a connection request."""
    write_config(auth_req)

    answered = {}

    def on_accept(key, request, context):
        answered[key] = request.body
        return ""

    requests_mock.register_uri(
        "post", f"{api_root}/admin/invites/@friend/accept", text=partial(on_accept, "connection")
    )
    requests_mock.register_uri("post", f"{api_root}/admin/invites/+acme~crew/accept", text=partial(on_accept, "group"))

    cli("--invites", "@friend", "--accept")
    assert answered["connection"] == b"yes"

    cli("--invites", "@friend", "--reject")
    assert answered["connection"] == b"no"

    cli("--invites", "+acme~crew", "--accept")
    assert answered["group"] == b"yes"


def test_invite_without_group_errors(cli, requests_mock, fs):
    write_config(auth_req)

    try:
        cli("--invite", "bob")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "--invite requires a group" in err


# --- legacy meanings stay intact -------------------------------------------------


def test_plot_share_and_read_untouched(cli, requests_mock, fs):
    """-p claims the invocation: -s stays share, -r stays read."""
    write_config(auth_req)

    shared = {}

    def on_share(request, context):
        shared["yes"] = True
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{api_root}vis/plots/my-plot", status_code=201)
    requests_mock.register_uri("get", f"{api_root}vis/plots/my-plot/shared", json=[], status_code=200)
    requests_mock.register_uri("put", f"{api_root}vis/plots/my-plot/shared/public", text=on_share)
    requests_mock.register_uri("get", f"{api_root}vis/plots/my-plot/url", text="https://novem.no/p/x")

    out, err = cli("-p", "my-plot", "-s", "public", "-C", "-r", "url")
    assert shared.get("yes")
    assert out == "https://novem.no/p/x"


# --- computer sessions: -R and -A -----------------------------------------------


def test_computer_image_shorthand(cli, requests_mock, fs):
    """--image on a selected computer writes config/image."""
    write_config(auth_req)

    written = {}

    def on_write(request, context):
        written["image"] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("post", f"{api_root}code/computers/my-box/config/image", text=on_write)

    out, err = cli("-c", "my-box", "-C", "--image", "@novem/base")
    assert written["image"] == "@novem/base"


def test_computer_image_bare_reads_it_back(cli, requests_mock, fs):
    write_config(auth_req)

    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("get", f"{api_root}code/computers/my-box/config/image", text="@novem/base\n")

    out, err = cli("-c", "my-box", "--image")
    assert out == "@novem/base\n"


def test_computer_run_streams_and_exits_with_the_command_code(cli, requests_mock, fs, monkeypatch):
    write_config(auth_req)
    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("get", f"{api_root}whoami", text="demouser")

    seen = {}

    def fake_stream(self, argv, **kwargs):
        seen["argv"] = argv
        seen["stdin"] = kwargs.get("stdin")
        sys.stdout.write("hello\n")
        return (7, None)

    monkeypatch.setattr("novem.code.Computer.stream", fake_stream)

    try:
        cli("-c", "my-box", "-R", "--", "ls", "-la")
        assert False, "should exit with the command's code"
    except CliExit as e:
        out, err = e.args
        assert e.code == 7
        assert "hello" in out

    assert seen["argv"] == ["ls", "-la"]


def test_computer_run_reports_signals_shell_style(cli, requests_mock, fs, monkeypatch):
    write_config(auth_req)
    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("get", f"{api_root}whoami", text="demouser")

    monkeypatch.setattr("novem.code.Computer.stream", lambda self, argv, **kw: (-1, "TERM"))

    try:
        cli("-c", "my-box", "-R", "--", "sleep", "100")
        assert False, "should exit"
    except CliExit as e:
        assert e.code == 143  # 128 + SIGTERM


def test_computer_run_without_argv_explains_itself(cli, requests_mock, fs):
    write_config(auth_req)
    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)

    try:
        cli("-c", "my-box", "-R")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "needs a command" in err
        assert "-R -- ls -la" in err


def test_computer_attach_calls_shell(cli, requests_mock, fs, monkeypatch):
    write_config(auth_req)
    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)
    requests_mock.register_uri("get", f"{api_root}whoami", text="demouser")

    called = {}

    def fake_shell(self, **kwargs):
        called["yes"] = True
        return (0, None)

    monkeypatch.setattr("novem.code.Computer.shell", fake_shell)

    try:
        cli("-c", "my-box", "-A")
        assert False, "should exit"
    except CliExit as e:
        assert e.code == 0
    assert called.get("yes")


def test_attach_and_run_are_mutually_exclusive(cli, requests_mock, fs):
    write_config(auth_req)
    requests_mock.register_uri("put", f"{api_root}code/computers/my-box", status_code=201)

    try:
        cli("-c", "my-box", "-A", "-R", "--", "ls")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "cannot be combined" in err


def test_session_verbs_are_computer_only(cli, requests_mock, fs):
    write_config(auth_req)
    requests_mock.register_uri("put", f"{api_root}code/spaces/my-space", status_code=201)

    try:
        cli("-s", "my-space", "-A")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "only available for computers" in err


def test_job_run_rejects_an_argv_tail_for_now(cli, requests_mock, fs):
    write_config(auth_req)
    requests_mock.register_uri("put", f"{api_root}code/jobs/my-job", status_code=201)

    try:
        cli("-j", "my-job", "-R", "--", "python", "main.py")
        assert False, "should exit"
    except CliExit as e:
        out, err = e.args
        assert "not supported for jobs yet" in err
