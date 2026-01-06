from functools import partial

from novem.cli.gql import _get_gql_endpoint
from novem.utils import API_ROOT, format_datetime_local, parse_api_datetime, pretty_format

from .utils import write_config

# we need to test the different cli aspects
auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": ('cli token created for "{hostname}" ' 'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'),
}

api_root = "https://api.novem.io/v1/"
gql_endpoint = _get_gql_endpoint(API_ROOT)


# Auth endpoint for our token
def missing(request, context):
    context.status_code = 404
    return


def test_grid_list(cli, requests_mock, fs):

    write_config(auth_req)

    # GraphQL format for grids (what the API returns)
    gql_grid_list = [
        {
            "id": "covid_us_state_breakdown",
            "name": "Covid19 cases by US State",
            "type": "us map",
            "summary": "This chart shows current average daily cases per"
            " capita broken down by US state. Raw data from the New York"
            " Times, calculations by Novem. Data last updated 23 November "
            "2021",
            "url": "https://novem.no/g/XVBzV",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
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
            "url": "https://novem.no/g/Kwjdv",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
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
            "url": "https://novem.no/g/7N2Wv",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
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
            "url": "https://novem.no/g/QVgEN",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
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
            "url": "https://novem.no/g/qNGgN",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
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
            "url": "https://novem.no/g/2v1rV",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
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
    # Order: favorites first, then non-favorites (same timestamp so original order preserved)
    user_grid_list = [
        {
            "id": "state_pop",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/qNGgN",
            "name": "Top 5 us states by population and age",
            "shared": ["public", "@", "+"],
            "fav": "*",
            "type": "grouped bar chart",
            "summary": "Historical unemployment rate in the Nordic countries."
            " Data from IMFs World Economic Oulook published in October 2021"
            " Chart last updated as of 25 January 2022",
        },
        {
            "id": "covid_us_state_breakdown",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/XVBzV",
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
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/Kwjdv",
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
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/7N2Wv",
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
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/QVgEN",
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
            "id": "unemployment_noridc",
            "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
            "uri": "https://novem.no/g/2v1rV",
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
        json={"data": {"grids": gql_grid_list}},
        status_code=200,
    )

    # try to list all grids with -l flag (simple list)
    out, err = cli("-g", "-l")

    # Expected order: favorites first, then non-favorites (by created desc, but all same date so original order)
    # state_pop has fav="*", rest have fav=""
    expected_order = [
        "state_pop",
        "covid_us_state_breakdown",
        "covid_us_trend",
        "covid_us_trend_region",
        "en_letter_frequency",
        "unemployment_noridc",
    ]
    expected = "\n".join(expected_order) + "\n"
    assert out == expected

    # try to list all grids with a nice list format
    out, err = cli("-g")

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

    def fav_fmt(markers, cl):
        fav_str = f"{cl.WARNING}*{cl.ENDC}" if "*" in markers else " "
        like_str = f"{cl.OKBLUE}+{cl.ENDC}" if "+" in markers else " "
        return f" {fav_str}{like_str} "

    # construct our pretty print list
    ppo = [
        {
            "key": "fav",
            "header": "    ",
            "type": "text",
            "fmt": fav_fmt,
            "overflow": "keep",
            "no_border": True,
            "no_padding": True,
        },
        {
            "key": "id",
            "header": "Grid ID",
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
            "overflow": "shrink",
        },
        {
            "key": "uri",
            "header": "Url",
            "type": "url",
            "overflow": "keep",
        },
        {
            "key": "updated",
            "header": "Updated",
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
    plist = user_grid_list
    for p in plist:
        dt = parse_api_datetime(p["updated"])
        if dt:
            p["updated"] = format_datetime_local(dt)

    expected = pretty_format(plist, ppo) + "\n"

    assert expected == out


def test_grid_x(cli, requests_mock, fs):

    write_config(auth_req)

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

    # display grid
    out, err = cli("-g", grid_name, "-x")
    assert out == grid_ansi


def test_grid_input_from_stdin(cli, requests_mock, fs):

    write_config(auth_req)

    grid_name = "test_grid"
    content = "this is the stdin content"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/grids/{grid_name}",
        status_code=201,
    )

    out_fc = ""

    def set_caption(value, request, context):
        nonlocal out_fc
        out_fc = value
        context.status_code = 200
        return

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/grids/{grid_name}/layout",
        text=partial(set_caption, content),
    )

    # set input from stdin
    out, err = cli("-g", grid_name, stdin=content)

    assert content == out_fc
