import datetime
import email.utils as eut
import io
import json
import sys
from functools import partial

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

api_root = "https://api.novem.io/v1/"


# Auth endpoint for our token
def missing(request, context):

    # return a valid auth endpoint
    context.status_code = 404

    return


def test_grid_list(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.io/v1/"

    # create a config
    write_config(auth_req)

    # grid name

    grid_list = [
        {
            "name": "covid_us_state_breakdown",
            "shortname": "XVBzV",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/XVBzV",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "covid_us_trend",
            "shortname": "Kwjdv",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/Kwjdv",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "covid_us_trend_region",
            "shortname": "7N2Wv",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/7N2Wv",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "en_letter_frequency",
            "shortname": "QVgEN",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/QVgEN",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "state_pop",
            "shortname": "qNGgN",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/qNGgN",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
        {
            "name": "unemployment_noridc",
            "shortname": "2v1rV",
            "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/2v1rV",
            "last_modified": "Thu, 17 Mar 2022 12:19:02 UTC",
            "type": "dir",
        },
    ]

    user_grid_list = [
        {
            "id": "covid_us_state_breakdown",
            "shortname": "XVBzV",
            "created": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/XVBzV",
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
            "uri": "https://novem.no/g/Kwjdv",
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
            "uri": "https://novem.no/g/7N2Wv",
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
            "uri": "https://novem.no/g/QVgEN",
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
            "uri": "https://novem.no/g/qNGgN",
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
            "uri": "https://novem.no/g/2v1rV",
            "name": "Historical Unemployment rates in the Nordic" " countries",
            "type": "stacked bar chart",
            "summary": "Historical unemployment rate in the Nordic "
            "countries. Data from IMFs World Economic Oulook published in"
            " October 2021 Chart last updated as of 25 January 2022",
        },
    ]

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/grids/",
        text=json.dumps(grid_list),
        status_code=200,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}u/demouser/g/",
        text=json.dumps(user_grid_list),
        status_code=200,
    )

    # try to list all grids
    params = ["-g", "-l"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    # grab names
    comp = "\n".join([x["name"] for x in grid_list]) + "\n"
    assert out == comp

    # try to list all grids with a nice list format
    params = ["-g"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    # construct our pretty print list
    ppo = [
        {
            "key": "id",
            "header": "Grid ID",
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
    plist = user_grid_list
    for p in plist:
        nd = datetime.datetime(*eut.parsedate(p["created"])[:6])
        p["created"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(plist, ppo)

    assert ppl + "\n" == out

    # print(out)


def test_grid_x(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.io/v1/"

    # create a config
    write_config(auth_req)

    # grid name
    grid_name = "test_grid"

    grid_ansi = "one\ntwo\nthree\n"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/grids/{grid_name}",
        status_code=201,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/grids/{grid_name}/files/grid.ansi",
        text=grid_ansi,
    )

    # try to delete a no existant grid
    params = ["-g", grid_name, "-x"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    assert out == grid_ansi


def test_grid_input_from_stdin(requests_mock, fs, capsys, monkeypatch):

    api_root = "https://api.novem.io/v1/"

    # create a config
    write_config(auth_req)

    # grid name
    grid_name = "test_grid"

    content = "this is the stdin content"

    global out_stdin
    out_stdin = ""

    # assert in_caption != out_caption

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/grids/{grid_name}",
        status_code=201,
    )

    def set_caption(value, request, context):
        global out_fc
        out_fc = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/grids/{grid_name}/layout",
        text=partial(set_caption, content),
    )

    # try to delete a no existant grid
    params = ["-g", grid_name]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    monkeypatch.setattr("sys.stdin", io.StringIO(content))
    run_cli()

    assert content == out_fc
