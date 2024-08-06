import sys

from novem.cli import run_cli

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


out_test = ""


def test_mail_test(requests_mock, fs, capsys, monkeypatch):
    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    mail_name = "test_mail"

    global out_test
    out_test = ""

    requests_mock.register_uri(
        "PUT",
        f"{api_root}vis/plots/{mail_name}",
        status_code=201,
    )

    def capture_content(request, context):
        global out_test
        out_test = request.body.decode("utf-8")
        context.status_code = 200
        return "OK"

    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/content", text=capture_content)

    def set_status(request, context):
        global out_test
        out_test = request.body.decode("utf-8")
        context.status_code = 200
        return "OK"

    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/status", text=set_status)

    # try to delete a non-existent plot
    params = ["-m", mail_name, "-w", "content", "hi", "-T"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()

    expected = "testing"

    assert expected == out_test


def test_mail_send(requests_mock, fs, capsys, monkeypatch):
    api_root = "https://api.novem.no/v1/"

    # create a config
    write_config(auth_req)

    # plot name
    mail_name = "test_mail"

    global out_test
    out_test = ""

    requests_mock.register_uri(
        "PUT",
        f"{api_root}vis/plots/{mail_name}",
        status_code=201,
    )

    def capture_content(request, context):
        global out_test
        out_test = request.body.decode("utf-8")
        context.status_code = 200
        return "OK"

    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/content", text=capture_content)

    def set_status(request, context):
        global out_test
        out_test = request.body.decode("utf-8")
        context.status_code = 200
        return "OK"

    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/status", text=set_status)

    # try to delete a non-existent plot
    params = ["-m", mail_name, "-w", "content", "hi", "-S"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()

    expected = "sending"

    assert expected == out_test
