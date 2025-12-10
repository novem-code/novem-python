import datetime
import email.utils as eut
import json
from functools import partial

import pytest

from novem.cli.gql import _get_gql_endpoint
from novem.utils import API_ROOT, pretty_format
from tests.conftest import CliExit

from .utils import write_config

api_root = "https://api.novem.io/v1/"
gql_endpoint = _get_gql_endpoint(API_ROOT)

# we need to test the different cli aspects
auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": ('cli token created for "{hostname}" ' 'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'),
}


def missing(request, context):
    context.status_code = 404
    return


def test_plot_list(cli, requests_mock, fs):
    write_config(auth_req)

    # GraphQL format for plots (what the API returns)
    gql_plot_list = [
        {
            "id": "covid_us_state_breakdown",
            "name": "Covid19 cases by US State",
            "type": "us map",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
            "url": "https://novem.no/p/XVBzV",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "public": True,
            "shared": [],
            "tags": [],
        },
        {
            "id": "covid_us_trend",
            "name": "Covid19 cases by US State",
            "type": "line chart",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
            "url": "https://novem.no/p/Kwjdv",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "public": True,
            "shared": [],
            "tags": [],
        },
        {
            "id": "covid_us_trend_region",
            "name": "Covid19 cases by US State",
            "type": "area chart",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
            "url": "https://novem.no/p/7N2Wv",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "public": True,
            "shared": [
                {
                    "id": "group",
                    "name": "group",
                    "type": "user_group",
                    "parent": {"id": "user", "name": "user", "type": "user"},
                }
            ],
            "tags": [],
        },
        {
            "id": "en_letter_frequency",
            "name": "Letter frequency in the English language",
            "type": "bar chart",
            "summary": "Analysis of entries in the Concise Oxford dictionary"
            " as published by the compilers. The chart above represents data"
            " taken from Pavel Micka's website, which cites Robert Lewand's"
            " Cryptological Mathematics.",
            "url": "https://novem.no/p/QVgEN",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "public": True,
            "shared": [
                {
                    "id": "group",
                    "name": "group",
                    "type": "user_group",
                    "parent": {"id": "user", "name": "user", "type": "user"},
                },
                {
                    "id": "group",
                    "name": "group",
                    "type": "org_group",
                    "parent": {"id": "org", "name": "org", "type": "org"},
                },
            ],
            "tags": [],
        },
        {
            "id": "state_pop",
            "name": "Top 5 us states by population and age",
            "type": "grouped bar chart",
            "summary": "Historical unemployment rate in the Nordic countries."
            " Data from IMFs World Economic Oulook published in October 2021"
            " Chart last updated as of 25 January 2022",
            "url": "https://novem.no/p/qNGgN",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "public": True,
            "shared": [
                {
                    "id": "group",
                    "name": "group",
                    "type": "user_group",
                    "parent": {"id": "user", "name": "user", "type": "user"},
                },
                {
                    "id": "group",
                    "name": "group",
                    "type": "org_group",
                    "parent": {"id": "org", "name": "org", "type": "org"},
                },
            ],
            "tags": [{"id": "fav", "name": "Favorite", "type": "system"}],
        },
        {
            "id": "unemployment_noridc",
            "name": "Historical Unemployment rates in the Nordic" " countries",
            "type": "stacked bar chart",
            "summary": "Historical unemployment rate in the Nordic "
            "countries. Data from IMFs World Economic Oulook published in"
            " October 2021 Chart last updated as of 25 January 2022",
            "url": "https://novem.no/p/2v1rV",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "public": True,
            "shared": [
                {
                    "id": "group",
                    "name": "group",
                    "type": "user_group",
                    "parent": {"id": "user", "name": "user", "type": "user"},
                },
                {
                    "id": "group",
                    "name": "group",
                    "type": "org_group",
                    "parent": {"id": "org", "name": "org", "type": "org"},
                },
            ],
            "tags": [],
        },
    ]

    # Expected REST format after transformation (for assertion)
    user_plot_list = [
        {
            "id": "covid_us_state_breakdown",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/XVBzV",
            "name": "Covid19 cases by US State",
            "shared": ["public"],
            "fav": "",
            "type": "us map",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
        },
        {
            "id": "covid_us_trend",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/Kwjdv",
            "name": "Covid19 cases by US State",
            "shared": ["public"],
            "fav": "",
            "type": "line chart",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
        },
        {
            "id": "covid_us_trend_region",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/7N2Wv",
            "name": "Covid19 cases by US State",
            "shared": ["public", "@"],
            "fav": "",
            "type": "area chart",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
        },
        {
            "id": "en_letter_frequency",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/QVgEN",
            "shared": ["public", "@", "+"],
            "fav": "",
            "name": "Letter frequency in the English language",
            "type": "bar chart",
            "summary": "Analysis of entries in the Concise Oxford dictionary"
            " as published by the compilers. The chart above represents data"
            " taken from Pavel Micka's website, which cites Robert Lewand's"
            " Cryptological Mathematics.",
        },
        {
            "id": "state_pop",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/qNGgN",
            "name": "Top 5 us states by population and age",
            "shared": ["public", "@", "+"],
            "fav": "*",
            "type": "grouped bar chart",
            "summary": "Historical unemployment rate in the Nordic countries."
            " Data from IMFs World Economic Oulook published in October 2021"
            " Chart last updated as of 25 January 2022",
        },
        {
            "id": "unemployment_noridc",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/2v1rV",
            "shared": ["public", "@", "+"],
            "fav": "",
            "name": "Historical Unemployment rates in the Nordic" " countries",
            "type": "stacked bar chart",
            "summary": "Historical unemployment rate in the Nordic "
            "countries. Data from IMFs World Economic Oulook published in"
            " October 2021 Chart last updated as of 25 January 2022",
        },
    ]

    # Mock GraphQL endpoint
    requests_mock.register_uri(
        "post",
        gql_endpoint,
        json={"data": {"plots": gql_plot_list}},
        status_code=200,
    )

    # try to list all plots with -l flag (simple list)
    out, err = cli("-p", "-l")

    # grab names (sorted by id)
    expected = "\n".join(sorted([x["id"] for x in gql_plot_list])) + "\n"
    assert out == expected

    # try to list all plots with a nice list format
    out, err = cli("-p")

    def share_fmt(share, cl):
        sl = [x[0] for x in share]
        pub = f"{cl.FAIL}P{cl.ENDC}" if "p" in sl else "-"  # public
        chat = f"{cl.WARNING}C{cl.ENDC}" if "c" in sl else "-"  # chat claim
        ug = "@" if "@" in sl else "-"  # user group
        og = "+" if "+" in sl else "-"  # org group
        return f"{pub} {chat} {ug} {og}"

    def summary_fmt(summary, cl):
        if not summary:
            return ""

        return summary.replace("\n", "")

    def fav_fmt(fav, cl):
        if fav == "*":
            return f" {cl.OKBLUE}*{cl.ENDC} "
        return "   "

    # construct our pretty print list
    ppo = [
        {
            "key": "fav",
            "header": "   ",
            "type": "text",
            "fmt": fav_fmt,
            "overflow": "keep",
            "no_border": True,
            "no_padding": True,
        },
        {
            "key": "id",
            "header": "Plot ID",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "shared",
            "header": "Shared",
            "fmt": share_fmt,
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "truncate",
        },
        {
            "key": "uri",
            "header": "Url",
            "type": "url",
            "overflow": "keep",
        },
        {
            "key": "created",
            "header": "Created",
            "type": "date",
            "overflow": "keep",
        },
        {
            "key": "summary",
            "header": "Summary",
            "fmt": summary_fmt,
            "type": "text",
            "overflow": "truncate",
        },
    ]
    plist = user_plot_list
    for p in plist:
        nd = datetime.datetime(*eut.parsedate(p["created"])[:6])  # type: ignore
        p["created"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(plist, ppo)

    assert ppl + "\n" == out


def test_plot_delete_missing(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"

    requests_mock.register_uri(
        "delete",
        f"{api_root}vis/plots/{plot_name}",
        text='{ "message" : "Resource not found"}',
        status_code=404,
    )

    # try to delete a nonexistent plot
    with pytest.raises(CliExit) as e:
        cli("-p", "test_plot", "-D")

    assert e.value.code == 1
    out, err = e.value.args
    assert out == f"Plot {plot_name} did not exist\n"


def test_plot_share_list(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"

    shares = [
        {
            "name": "public",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
        {
            "name": "@demo_user~test",
            "created_on": "Thu, 03 Mar 2022 21:01:25 UTC",
        },
    ]

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_name}/shared",
        text=json.dumps(shares),
        status_code=200,
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    # list out shares for plot
    out, err = cli("-p", plot_name, "-s", "-l")

    expected = "\n".join([x["name"] for x in shares]) + "\n"
    assert out == expected


def test_plot_share_add(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    shares = []

    def add_share(value, request, context):
        shares.append(value)
        context.status_code = 201
        return

    def get_share(request, context):
        if len(shares) == 0:
            context.status_code = 200
            return "[]"

        context.status_code = 200
        return json.dumps([{"name": x} for x in shares])

    requests_mock.register_uri("get", f"{api_root}vis/plots/{plot_name}/shared", text=get_share)

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}/shared/public",
        text=partial(add_share, "public"),
    )
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}/shared/@demo_user~test",
        text=partial(add_share, "@demo_user~test"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    # change shares
    cli("-p", plot_name, "-s", "public", "-D")
    cli("-p", plot_name, "-s", "@demo_user~test", "-C")
    out, err = cli("-p", plot_name, "-s", "-l")

    comp = "\n".join([x for x in shares]) + "\n"
    assert out == comp


def test_plot_single_input(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    in_caption = "this is the caption"
    out_caption = ""

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        nonlocal out_caption
        out_caption = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/caption",
        text=partial(set_caption, in_caption),
    )

    # write caption
    cli("-p", plot_name, "-w", "config/caption", in_caption)

    assert in_caption == out_caption


def test_plot_input_from_file(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    content = "this is the file content"

    filename = "caption.txt"
    with open(filename, "w") as f:
        f.write(content)

    out_fc = ""

    # assert in_caption != out_caption

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        nonlocal out_fc
        out_fc = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/caption",
        text=partial(set_caption, content),
    )

    # write caption from file content
    cli("-p", plot_name, "-w", "config/caption", f"@{filename}")

    assert content == out_fc


def test_plot_input_from_file_fails(cli, requests_mock, fs, capsys):

    write_config(auth_req)

    plot_name = "test_plot"
    content = "this is the file content"
    filename = "caption.txt"
    out_fc = ""

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        nonlocal out_fc
        out_fc = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/caption",
        text=partial(set_caption, content),
    )

    # try to delete a nonexistent plot
    with pytest.raises(CliExit) as e:
        cli("-p", plot_name, "-w", "config/caption", f"@{filename}")

    assert e.value.code == 1
    out, err = e.value.args
    assert out == (f'The supplied input file "{filename}" does not exist.' " Please review your options\n")


def test_plot_input_from_stdin(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    content = "this is the stdin content"
    out_fc = ""

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        nonlocal out_fc
        out_fc = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/caption",
        text=partial(set_caption, content),
    )

    # write caption from stdin
    cli("-p", plot_name, "-w", "config/caption", stdin=content)

    assert content == out_fc


def test_plot_input_from_stdin_fail(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    content = "this is the stdin content"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    out_fc = ""

    def set_caption(value, request, context):
        global out_fc
        out_fc = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/caption",
        text=partial(set_caption, content),
    )

    # write caption, but without any data
    with pytest.raises(CliExit) as e:
        cli("-p", plot_name, "-w", "config/caption")

    assert e.value.code == 1
    out, err = e.value.args
    assert out == ('No data found on stdin, "-w /config/caption" requires data ' "to be supplied on stdin\n")
    assert content != out_fc


out_plot_type = ""


def test_plot_types(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    in_type = "sbar"
    out_plot_type = ""

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        nonlocal out_plot_type
        out_plot_type = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/type",
        text=partial(set_caption, in_type),
    )

    # set type
    cli("-p", plot_name, "--type", in_type)

    assert in_type == out_plot_type


def test_plot_x(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    plot_ansi = "one\ntwo\nthree\n"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_name}/files/plot.ansi",
        text=plot_ansi,
    )

    # display plot output
    out, err = cli("-p", plot_name, "-x")

    assert out == plot_ansi


def test_plot_o(cli, requests_mock, fs):

    write_config(auth_req)

    plot_name = "test_plot"
    plot_ansi = "one\ntwo\nthree\n"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_name}/files/plot.ansi",
        text=plot_ansi,
    )

    # display plot output
    out, err = cli("-p", plot_name, "-r", "files/plot.ansi")

    assert out == plot_ansi
