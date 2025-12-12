import json
from functools import partial

from novem.utils import API_ROOT

from .utils import write_config

api_root = API_ROOT

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": ('cli token created for "{hostname}" ' 'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'),
}


def test_plot_tag_list(cli, requests_mock, fs):
    """Test listing tags for a plot via -t flag"""

    write_config(auth_req)

    plot_name = "test_plot"

    tags = [
        {
            "name": "fav",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
        {
            "name": "+myproject",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
    ]

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_name}/tags",
        text=json.dumps(tags),
        status_code=200,
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    # list out tags for plot
    out, err = cli("-p", plot_name, "-t", "-l")

    expected = "\n".join([x["name"] for x in tags]) + "\n"
    assert out == expected


def test_plot_tag_add(cli, requests_mock, fs):
    """Test adding tags to a plot via -t -C"""

    write_config(auth_req)

    plot_name = "test_plot"
    tags = []

    def add_tag(value, request, context):
        tags.append(value)
        context.status_code = 201
        return

    def get_tags(request, context):
        if len(tags) == 0:
            context.status_code = 200
            return "[]"

        context.status_code = 200
        return json.dumps([{"name": x} for x in tags])

    requests_mock.register_uri("get", f"{api_root}vis/plots/{plot_name}/tags", text=get_tags)

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}/tags/fav",
        text=partial(add_tag, "fav"),
    )
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}/tags/wip",
        text=partial(add_tag, "wip"),
    )
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}/tags/+myproject",
        text=partial(add_tag, "+myproject"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    # add tags
    cli("-p", plot_name, "-t", "fav", "-C")
    cli("-p", plot_name, "-t", "wip", "-C")
    cli("-p", plot_name, "-t", "+myproject", "-C")
    out, err = cli("-p", plot_name, "-t", "-l")

    comp = "\n".join([x for x in tags]) + "\n"
    assert out == comp


def test_plot_tag_delete(cli, requests_mock, fs):
    """Test deleting tags from a plot via -t -D"""

    write_config(auth_req)

    plot_name = "test_plot"
    tags = ["fav", "wip"]

    def del_tag(value, request, context):
        if value in tags:
            tags.remove(value)
        context.status_code = 200
        return

    def get_tags(request, context):
        context.status_code = 200
        return json.dumps([{"name": x} for x in tags])

    requests_mock.register_uri("get", f"{api_root}vis/plots/{plot_name}/tags", text=get_tags)

    requests_mock.register_uri(
        "delete",
        f"{api_root}vis/plots/{plot_name}/tags/fav",
        text=partial(del_tag, "fav"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    # delete tag
    cli("-p", plot_name, "-t", "fav", "-D")
    out, err = cli("-p", plot_name, "-t", "-l")

    assert "fav" not in out
    assert "wip" in out


def test_grid_tag_list(cli, requests_mock, fs):
    """Test listing tags for a grid via -t flag"""

    write_config(auth_req)

    grid_name = "test_grid"

    tags = [
        {
            "name": "like",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
        {
            "name": "archived",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
    ]

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/grids/{grid_name}/tags",
        text=json.dumps(tags),
        status_code=200,
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/grids/{grid_name}",
        status_code=201,
    )

    # list out tags for grid
    out, err = cli("-g", grid_name, "-t", "-l")

    expected = "\n".join([x["name"] for x in tags]) + "\n"
    assert out == expected


def test_mail_tag_add(cli, requests_mock, fs):
    """Test adding tags to a mail via -t -C"""

    write_config(auth_req)

    mail_name = "test_mail"
    tags = []

    def add_tag(value, request, context):
        tags.append(value)
        context.status_code = 201
        return

    def get_tags(request, context):
        context.status_code = 200
        return json.dumps([{"name": x} for x in tags])

    requests_mock.register_uri("get", f"{api_root}vis/mails/{mail_name}/tags", text=get_tags)

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/mails/{mail_name}/tags/ignore",
        text=partial(add_tag, "ignore"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/mails/{mail_name}",
        status_code=201,
    )

    # add tag
    cli("-m", mail_name, "-t", "ignore", "-C")
    out, err = cli("-m", mail_name, "-t", "-l")

    assert "ignore" in out


def test_job_tag_list(cli, requests_mock, fs):
    """Test listing tags for a job via -t flag"""

    write_config(auth_req)

    job_name = "test_job"

    tags = [
        {
            "name": "fav",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
        {
            "name": "+automation",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
    ]

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_name}/tags",
        text=json.dumps(tags),
        status_code=200,
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_name}",
        status_code=201,
    )

    # list out tags for job
    out, err = cli("-j", job_name, "-t", "-l")

    expected = "\n".join([x["name"] for x in tags]) + "\n"
    assert out == expected


def test_job_tag_add(cli, requests_mock, fs):
    """Test adding tags to a job via -t -C"""

    write_config(auth_req)

    job_name = "test_job"
    tags = []

    def add_tag(value, request, context):
        tags.append(value)
        context.status_code = 201
        return

    def get_tags(request, context):
        context.status_code = 200
        return json.dumps([{"name": x} for x in tags])

    requests_mock.register_uri("get", f"{api_root}jobs/{job_name}/tags", text=get_tags)

    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_name}/tags/fav",
        text=partial(add_tag, "fav"),
    )
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_name}/tags/wip",
        text=partial(add_tag, "wip"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_name}",
        status_code=201,
    )

    # add tags
    cli("-j", job_name, "-t", "fav", "-C")
    cli("-j", job_name, "-t", "wip", "-C")
    out, err = cli("-j", job_name, "-t", "-l")

    comp = "\n".join([x for x in tags]) + "\n"
    assert out == comp


def test_job_tag_delete(cli, requests_mock, fs):
    """Test deleting tags from a job via -t -D"""

    write_config(auth_req)

    job_name = "test_job"
    tags = ["fav", "wip", "+project"]

    def del_tag(value, request, context):
        if value in tags:
            tags.remove(value)
        context.status_code = 200
        return

    def get_tags(request, context):
        context.status_code = 200
        return json.dumps([{"name": x} for x in tags])

    requests_mock.register_uri("get", f"{api_root}jobs/{job_name}/tags", text=get_tags)

    requests_mock.register_uri(
        "delete",
        f"{api_root}jobs/{job_name}/tags/wip",
        text=partial(del_tag, "wip"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_name}",
        status_code=201,
    )

    # delete tag
    cli("-j", job_name, "-t", "wip", "-D")
    out, err = cli("-j", job_name, "-t", "-l")

    assert "wip" not in out
    assert "fav" in out
    assert "+project" in out


def test_plot_multiple_tags_add(cli, requests_mock, fs):
    """Test adding multiple comma-separated tags via -t fav,+demo,+test -C"""

    write_config(auth_req)

    plot_name = "test_plot"
    tags = []

    def add_tag(value, request, context):
        if value not in tags:
            tags.append(value)
        context.status_code = 201
        return

    def get_tags(request, context):
        context.status_code = 200
        return json.dumps([{"name": x} for x in tags])

    requests_mock.register_uri("get", f"{api_root}vis/plots/{plot_name}/tags", text=get_tags)

    for tag in ["fav", "+demo", "+test", "wip"]:
        requests_mock.register_uri(
            "put",
            f"{api_root}vis/plots/{plot_name}/tags/{tag}",
            text=partial(add_tag, tag),
        )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    # add multiple tags at once
    cli("-p", plot_name, "-t", "fav,+demo,+test", "-C")
    out, err = cli("-p", plot_name, "-t", "-l")

    assert "fav" in out
    assert "+demo" in out
    assert "+test" in out
    assert len(tags) == 3


def test_job_multiple_tags_delete(cli, requests_mock, fs):
    """Test deleting multiple comma-separated tags via -t fav,wip -D"""

    write_config(auth_req)

    job_name = "test_job"
    tags = ["fav", "wip", "+project", "like"]

    def del_tag(value, request, context):
        if value in tags:
            tags.remove(value)
        context.status_code = 200
        return

    def get_tags(request, context):
        context.status_code = 200
        return json.dumps([{"name": x} for x in tags])

    requests_mock.register_uri("get", f"{api_root}jobs/{job_name}/tags", text=get_tags)

    for tag in ["fav", "wip"]:
        requests_mock.register_uri(
            "delete",
            f"{api_root}jobs/{job_name}/tags/{tag}",
            text=partial(del_tag, tag),
        )

    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_name}",
        status_code=201,
    )

    # delete multiple tags at once
    cli("-j", job_name, "-t", "fav,wip", "-D")
    out, err = cli("-j", job_name, "-t", "-l")

    assert "fav" not in out
    assert "wip" not in out
    assert "+project" in out
    assert "like" in out
    assert len(tags) == 2
