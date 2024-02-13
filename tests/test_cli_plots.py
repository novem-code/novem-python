import datetime
import email.utils as eut
import io
import json
import sys
from functools import partial

import pytest

from novem.cli import run_cli
from novem.utils import pretty_format

from .utils import write_config

# we need to test the different cli aspects
auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": ('cli token created for "{hostname}" ' 'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'),
}


# Auth endpoint for our token
def missing(request, context):

    # return a valid auth endpoint
    context.status_code = 404

    return


def test_plot_list(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name

    plot_list = [
        {
            "name": "covid_us_state_breakdown",
            "shortname": "XVBzV",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/XVBzV",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "covid_us_trend",
            "shortname": "Kwjdv",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/Kwjdv",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "covid_us_trend_region",
            "shortname": "7N2Wv",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/7N2Wv",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "en_letter_frequency",
            "shortname": "QVgEN",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/QVgEN",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "state_pop",
            "shortname": "qNGgN",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/qNGgN",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "unemployment_noridc",
            "shortname": "2v1rV",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/2v1rV",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
    ]

    user_plot_list = [
        {
            "id": "covid_us_state_breakdown",
            "shortname": "XVBzV",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/XVBzV",
            "name": "Covid19 cases by US State",
            "type": "us map",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
        },
        {
            "id": "covid_us_trend",
            "shortname": "Kwjdv",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/Kwjdv",
            "name": "Covid19 cases by US State",
            "type": "line chart",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
        },
        {
            "id": "covid_us_trend_region",
            "shortname": "7N2Wv",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/7N2Wv",
            "name": "Covid19 cases by US State",
            "type": "area chart",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
        },
        {
            "id": "en_letter_frequency",
            "shortname": "QVgEN",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/QVgEN",
            "name": "Letter frequency in the English language",
            "type": "bar chart",
            "summary": "Analysis of entries in the Concise Oxford dictionary"
            " as published by the compilers. The chart above represents data"
            " taken from Pavel Micka's website, which cites Robert Lewand's"
            " Cryptological Mathematics.",
        },
        {
            "id": "state_pop",
            "shortname": "qNGgN",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/qNGgN",
            "name": "Top 5 us states by population and age",
            "type": "grouped bar chart",
            "summary": "Historical unemployment rate in the Nordic countries."
            " Data from IMFs World Economic Oulook published in October 2021"
            " Chart last updated as of 25 January 2022",
        },
        {
            "id": "unemployment_noridc",
            "shortname": "2v1rV",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/p/2v1rV",
            "name": "Historical Unemployment rates in the Nordic" " countries",
            "type": "stacked bar chart",
            "summary": "Historical unemployment rate in the Nordic "
            "countries. Data from IMFs World Economic Oulook published in"
            " October 2021 Chart last updated as of 25 January 2022",
        },
    ]

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/",
        text=json.dumps(plot_list),
        status_code=200,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}u/demouser/p/",
        text=json.dumps(user_plot_list),
        status_code=200,
    )

    # try to list all plots
    params = ["-p", "-l"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    # grab names
    comp = "\n".join([x["name"] for x in plot_list]) + "\n"
    assert out == comp

    # try to list all plots with a nice list format
    params = ["-p"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    # construct our pretty print list
    ppo = [
        {
            "key": "id",
            "header": "Plot ID",
            "type": "text",
            "overflow": "keep",
        },
        # {
        #    "key": "id",
        #    "header": "ID",
        #    "type": "text",
        #    "overflow": "keep",
        # },
        {
            "key": "type",
            "header": "Type",
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
            "fmt": lambda x: x.replace("\n", ""),
            "type": "text",
            "overflow": "truncate",
        },
    ]
    plist = user_plot_list
    for p in plist:
        nd = datetime.datetime(*eut.parsedate(p["created"])[:6])
        p["created"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(plist, ppo)

    assert ppl + "\n" == out

    # print(out)


def test_plot_delete_missing(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    requests_mock.register_uri(
        "delete",
        f"{api_root}vis/plots/{plot_name}",
        text='{ "message" : "Resource not found"}',
        status_code=404,
    )

    # try to delete a no existant plot
    params = ["-p", "test_plot", "-D"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        run_cli()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert out == f"Plot {plot_name} did not exist\n"


def test_plot_share_list(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-s", "-l"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    comp = "\n".join([x["name"] for x in shares]) + "\n"
    assert out == comp


def test_plot_share_add(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    shares = []

    def add_share(value, request, context):
        shares.append(value)
        context.status_code = 201
        return

    def get_share(request, context):
        if len(shares) == 0:
            context.status_code = 404
            return

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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-s", "public", "-D"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()

    params = ["-p", plot_name, "-s", "@demo_user~test", "-C"]
    sys.argv = ["novem"] + params
    run_cli()

    params = ["-p", plot_name, "-s", "-l"]
    sys.argv = ["novem"] + params
    run_cli()
    out, err = capsys.readouterr()

    comp = "\n".join([x for x in shares]) + "\n"
    assert out == comp


out_caption = ""


def test_plot_single_input(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    in_caption = "this is the caption"
    global out_caption
    out_caption = ""

    # assert in_caption != out_caption

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        global out_caption
        out_caption = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/caption",
        text=partial(set_caption, in_caption),
    )

    # try to delete a no existant plot
    params = ["-p", plot_name, "-w", "config/caption", in_caption]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()

    assert in_caption == out_caption


out_fc = ""


def test_plot_input_from_file(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    content = "this is the file content"

    filename = "caption.txt"
    with open(filename, "w") as f:
        f.write(content)

    global out_fc
    out_fc = ""

    # assert in_caption != out_caption

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-w", "config/caption", f"@{filename}"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()

    assert content == out_fc


def test_plot_input_from_file_fails(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    content = "this is the file content"

    filename = "caption.txt"

    global out_fc
    out_fc = ""

    # assert in_caption != out_caption

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-w", "config/caption", f"@{filename}"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        run_cli()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert out == (f'The supplied input file "{filename}" does not exist.' " Please review your options\n")


out_stdin = ""


def test_plot_input_from_stdin(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    content = "this is the stdin content"

    global out_stdin
    out_stdin = ""

    # assert in_caption != out_caption

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-w", "config/caption"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    monkeypatch.setattr("sys.stdin", io.StringIO(content))
    run_cli()

    assert content == out_fc


def test_plot_input_from_stdin_fail(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    content = "this is the stdin content"

    global out_stdin
    out_stdin = ""

    # assert in_caption != out_caption

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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-w", "config/caption"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        run_cli()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1

    out, err = capsys.readouterr()
    assert out == ('No data found on stdin, "-w /config/caption" requires data ' "to be supplied on stdin\n")

    assert content != out_fc


out_plot_type = ""


def test_plot_types(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    plot_name = "test_plot"

    in_type = "sbar"
    global out_plot_type
    out_plot_type = ""

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        global out_plot_type
        out_plot_type = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_name}/config/type",
        text=partial(set_caption, in_type),
    )

    # try to delete a no existant plot
    params = ["-p", plot_name, "-t", in_type]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()

    assert in_type == out_plot_type


def test_plot_x(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-x"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    assert out == plot_ansi


def test_plot_o(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
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

    # try to delete a no existant plot
    params = ["-p", plot_name, "-r", "files/plot.ansi"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    assert out == plot_ansi
