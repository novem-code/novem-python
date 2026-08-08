"""Job listing formatting: the Schedule column aligns its five cron fields
into per-position right-aligned columns across all rows, and TZ=-prefixed
schedules are recomputed into the viewer's time zone (never displayed)."""

from novem.cli.gql import _get_gql_endpoint
from novem.cli.vis import _localize_cron_fields
from novem.utils import API_ROOT

from .utils import write_config

gql_endpoint = _get_gql_endpoint(API_ROOT)

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": "cli token",
}


def _job(id, schedule):
    return {
        "id": id,
        "name": f"Job {id}",
        "type": "chains",
        "summary": "",
        "url": f"https://novem.no/j/{id}",
        "updated": "Thu, 17 Mar 2022 12:19:02 UTC",
        "public": False,
        "shared": [],
        "tags": [],
        "social": {"views": 0},
        "topics": [],
        "last_run_status": "success",
        "last_run_time": "Thu, 17 Mar 2022 12:19:02 UTC",
        "run_count": 1,
        "job_steps": 1,
        "current_step": None,
        "schedule": schedule,
        "triggers": ["schedule"],
    }


# --- cron field localisation (fixed-offset zones: DST cannot skew these) ----


def test_localize_plain_shift():
    # 14:00 at UTC+2 is 12:00 UTC
    assert _localize_cron_fields(["0", "14", "*", "*", "*"], "Etc/GMT-2", "UTC") == ["0", "12", "*", "*", "*"]


def test_localize_day_rollover_rotates_numeric_dow():
    # 20:30 at UTC-10 is 06:30 UTC the NEXT day: friday becomes saturday
    assert _localize_cron_fields(["30", "20", "*", "*", "5"], "Etc/GMT+10", "UTC") == ["30", "6", "*", "*", "6"]


def test_localize_non_numeric_fields_unchanged():
    # ranges/steps cannot be shifted safely
    fields = ["*/5", "9-17", "*", "*", "1-5"]
    assert _localize_cron_fields(fields, "Etc/GMT-2", "UTC") == fields


def test_localize_unknown_zone_unchanged():
    fields = ["0", "14", "*", "*", "*"]
    assert _localize_cron_fields(fields, "Not/AZone", "UTC") == fields


# --- through the job listing -------------------------------------------------


def test_job_schedule_column_alignment(cli, requests_mock, fs, monkeypatch):
    write_config(auth_req)

    # generous fake terminal so no column dropping/shaving interferes
    monkeypatch.setenv("COLUMNS", "300")

    # the listing query (contains the jobs field selection)
    requests_mock.register_uri(
        "post",
        gql_endpoint,
        json={
            "data": {
                "me": {
                    "username": "demouser",
                    "jobs": [
                        _job("simple", "0 12 * * *"),
                        _job("busy", "*/15 0,30 1-5 * *"),
                        _job("manual", ""),
                        _job("fixed", "TZ=Etc/GMT-2 0 14 * * *"),
                    ],
                }
            }
        },
        status_code=200,
    )
    # the viewer-timezone query (matched by its distinct body)
    requests_mock.register_uri(
        "post",
        gql_endpoint,
        additional_matcher=lambda r: "timezone" in (r.text or ""),
        json={"data": {"me": {"timezone": "UTC"}}},
        status_code=200,
    )

    out, err = cli("-j")

    # per-position widths across the rows: [4, 4, 3, 1, 1]
    assert "   0   12   * * *" in out  # simple, right-aligned per field
    assert "*/15 0,30 1-5 * *" in out  # widest row at natural width
    assert "   -    -   - - -" in out  # no schedule renders aligned dashes
    # the TZ= schedule is recomputed into the viewer's zone, tz never shown
    assert out.count("   0   12   * * *") == 2  # simple + converted fixed
    assert "TZ" not in out
    assert "GMT" not in out
