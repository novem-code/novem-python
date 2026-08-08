"""Job listing formatting: the Schedule column aligns its five cron fields
into per-position right-aligned columns across all rows."""

from novem.cli.gql import _get_gql_endpoint
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


def test_job_schedule_column_alignment(cli, requests_mock, fs, monkeypatch):
    write_config(auth_req)

    # generous fake terminal so no column shaving interferes
    monkeypatch.setenv("COLUMNS", "300")

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
                        _job("oslo", "TZ=Europe/Oslo 5 4 * * 1"),
                    ],
                }
            }
        },
        status_code=200,
    )

    out, err = cli("-j")

    # per-position widths across the rows: [4, 4, 3, 1, 1]
    assert "   0 0,30" not in out  # fields must not bleed into each other
    assert "   0   12   * * *" in out  # simple, right-aligned per field
    assert "*/15 0,30 1-5 * *" in out  # widest row at natural width
    assert "   -    -   - - -" in out  # no schedule renders aligned dashes
    assert "   5    4   * * 1 Europe/Oslo" in out  # TZ prefix becomes a suffix