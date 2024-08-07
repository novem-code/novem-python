from typing import Any, Union

from .utils import write_config

# we need to test the different cli aspects
auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": ('cli token created for "{hostname}" ' 'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'),
}

api_root = "https://api.novem.no/v1/"


class Capture:
    out: Any = None


def mk_responder(resp: str, code, capture: Union[Capture, None] = None):
    def inner(res, context):
        if capture:
            capture.out = res.body.decode("utf-8")
        context.status_code = code
        return resp

    return inner


def mk_missing():
    return mk_responder("", 404)


def test_status_set_when_sending_test_mail(requests_mock, cli):
    write_config(auth_req)
    mail_name = "test_mail"

    capture = Capture()
    requests_mock.register_uri("PUT", f"{api_root}vis/plots/{mail_name}", status_code=201)
    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/content", text=mk_responder("OK", 200))
    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/status", text=mk_responder("OK", 200, capture))

    # send a test mail
    cli("-m", mail_name, "-w", "content", "hi", "-T")
    assert capture.out == "testing"


def test_status_set_when_sending_mail(requests_mock, cli):
    write_config(auth_req)
    mail_name = "test_mail"

    capture = Capture()
    requests_mock.register_uri("PUT", f"{api_root}vis/plots/{mail_name}", status_code=201)
    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/content", text=mk_responder("OK", 200))
    requests_mock.register_uri("POST", f"{api_root}vis/mails/{mail_name}/status", text=mk_responder("OK", 200, capture))

    # send the mail
    cli("-m", mail_name, "-w", "content", "hi", "-S")
    assert capture.out == "sending"
