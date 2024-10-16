import configparser
import io
import os
import uuid
from contextlib import redirect_stdout
from functools import partial
from unittest.mock import patch

from novem import Mail, Plot
from novem.mail import AuthorSection, ParagraphSection, PreviewSection, VisSection
from novem.utils import API_ROOT


def test_mail_sections(requests_mock):
    # mock a plot

    plot_id = "test_plot"
    plot_shortname = "ABCDEF"

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def verify_plot_put(key, val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_plot_put, "create", "ignore"),
    )

    requests_mock.register_uri("get", f"{api_root}vis/plots/{plot_id}/shortname", text=plot_shortname)

    # email mock
    mail_id = "test_mail"
    mail_shortname = "VWXYZ"

    def verify_mail_put(key, val, request, context):
        assert request.url == f"{api_root}vis/mails/{mail_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/mails/{mail_id}",
        text=partial(verify_mail_put, "create", "ignore"),
    )

    requests_mock.register_uri("get", f"{api_root}vis/mails/{mail_id}/shortname", text=mail_shortname)

    # grab a reference to a plot
    plt = Plot(
        plot_id,
        config_path=config_file,  # config location
    )

    # create an e-mail
    m = Mail(
        mail_id,
        config_path=config_file,  # config location
    )

    # add a selection of sections

    # Add preview
    ps = PreviewSection(
        """
    This is our novem mail preview section
    """
    )
    m.add_section(ps)

    # preview should have been added to special preview location
    assert m._preview == ps

    # Verify that we can update the section
    nps = PreviewSection(
        """
    This is our new novem mail preview section
    """
    )
    m.add_section(nps)

    # confirm that previews are different and correctly updated
    assert nps != ps
    assert m._preview == nps

    # verify sections are empty
    assert len(m._sections) == 0

    # create some sample sections
    ss = []

    # add a small title
    ss.append(
        ParagraphSection(
            """
    ## Novem dail summary e-mail
    """,
            p="a0",
            b="b1 inverse",
            m="b2",
        )
    )

    ss.append(AuthorSection("novem_demo"))

    ss.append(VisSection(plt))

    ss.append(
        ParagraphSection(
            """
### Disclaimer
This e-mail is created as a demo e-mail only, please read more at
[novem.no](https://novem.no).
    """,
            font_size="s",
            font_style="i",
            p="a0",
            b="a0",
            m="b2",
        )
    )

    # add sectoins to e-mail
    for s in ss:
        m.add_section(s)

    # construct our markdown using the same approach as the mail class
    mdr = "\n\n".join([x.get_markdown() for x in ss])

    # add preview
    mdr = nps.get_markdown() + "\n\n" + mdr

    ctnt = m._produce_content()

    assert ctnt == mdr


def test_mail_attribs(requests_mock):
    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # email mock
    mail_id = "test_mail"
    mail_shortname = "VWXYZ"

    def verify_mail_put(key, val, request, context):
        assert request.url == f"{api_root}vis/mails/{mail_id}"

    # create mock
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/mails/{mail_id}",
        text=partial(verify_mail_put, "create", "ignore"),
    )

    # shortname mocks
    requests_mock.register_uri("get", f"{api_root}vis/mails/{mail_id}/shortname", text=mail_shortname)

    # let's verify that shortname works
    # create an e-mail
    m = Mail(
        mail_id,
        config_path=config_file,  # config location
    )

    assert m.shortname == mail_shortname


def setup_mail_mock(requests_mock, conf):
    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # email mock
    mail_id = conf["mail_id"]

    def verify_mail_put(key, val, request, context):
        assert request.url == f"{api_root}vis/mails/{mail_id}"

    # create mock
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/mails/{mail_id}",
        text=partial(verify_mail_put, "create", "ignore"),
    )

    for r in conf["reqs"]:
        if r[0] == "post":

            def verify_post(key, val, request, context):
                assert request.url == f"{api_root}vis/mails/{mail_id}{r[1]}"
                assert request.text == r[2]

            requests_mock.register_uri(
                "post",
                f"{api_root}vis/mails/{mail_id}{r[1]}",
                text=partial(verify_post, "create", "ignore"),
            )
        elif r[0] == "get":
            requests_mock.register_uri("get", f"{api_root}vis/mails/{mail_id}{r[1]}", text=r[2])

    m = Mail(
        mail_id,
        config_path=config_file,  # config location
    )

    return m


def test_mail_attrib_subject(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/config/subject", "subject test value out"],
            ["post", "/config/subject", "subject test value in"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.subject = "subject test value in"
    assert m.subject == "subject test value out"


def test_mail_attrib_theme(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/config/theme", "subject test value out"],
            ["post", "/config/theme", "subject test value in"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.theme = "subject test value in"
    assert m.theme == "subject test value out"


def test_mail_attrib_template(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/config/template", "subject test value out"],
            ["post", "/config/template", "subject test value in"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.template = "subject test value in"
    assert m.template == "subject test value out"


def test_mail_attrib_size(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/config/size", "subject test value out"],
            ["post", "/config/size", "subject test value in"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.size = "subject test value in"
    assert m.size == "subject test value out"


def test_mail_attrib_content(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/content", "subject test value out"],
            ["post", "/content", "subject test value in"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.content = "subject test value in"
    assert m.content == "subject test value out"


def test_mail_attrib_status(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/status", "subject test value out"],
            ["post", "/status", "subject test value in"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.status = "subject test value in"
    assert m.status == "subject test value out"


def test_mail_attrib_shortname(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/shortname", "subject test value out"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    assert m.shortname == "subject test value out"


def test_mail_attrib_url(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/url", "subject test value out"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    assert m.url == "subject test value out"


def test_mail_attrib_name(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/name", "subject test value out"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.name == "subject test value in"
    assert m.name == "subject test value out"


def test_mail_attrib_desc(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/description", "subject test value out"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.description == "subject test value in"
    assert m.description == "subject test value out"


def test_mail_attrib_summary(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/summary", "subject test value out"],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.summary == "subject test value in"
    assert m.summary == "subject test value out"


###
#
# recipients are "special" in that they will always return a string but
# supports setting of lists
#
###


def test_mail_recipients_to(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            [
                "get",
                "/recipients/to",
                "@novem_demo\n@test",
            ],
            [
                "post",
                "/recipients/to",
                "@novem_demo\n@test",
            ],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.to = ["@novem_demo", "@test"]
    assert m.to == "@novem_demo\n@test"
    m.to = "@novem_demo\n@test"


def test_mail_recipients_cc(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            [
                "get",
                "/recipients/cc",
                "@novem_demo\n@test",
            ],
            [
                "post",
                "/recipients/cc",
                "@novem_demo\n@test",
            ],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.cc = ["@novem_demo", "@test"]
    assert m.cc == "@novem_demo\n@test"
    m.cc = "@novem_demo\n@test"


def test_mail_recipients_bcc(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            [
                "get",
                "/recipients/bcc",
                "@novem_demo\n@test",
            ],
            [
                "post",
                "/recipients/bcc",
                "@novem_demo\n@test",
            ],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.bcc = ["@novem_demo", "@test"]
    assert m.bcc == "@novem_demo\n@test"
    m.bcc = "@novem_demo\n@test"


###
#
# Verify that we can set all attributes in constructor
#
###
def test_all_mail_attribs(requests_mock):
    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # email mock
    mail_id = f"mail_{str(uuid.uuid4())[:8]}"

    theme_val = "theme test value"
    subject_val = "subject test value"
    template_val = "template test value"
    size_val = "size test value"
    content_val = "content test value"
    status_val = "status test value"
    name_val = "name test value"
    description_val = "description test value"
    summary_val = "summary test value"

    gcheck = {
        "create": False,
        "theme": False,
        "subject": False,
        "template": False,
        "size": False,
        "content": False,
        "status": False,
        "name": False,
        "description": False,
        "summary": False,
    }

    def verify(key, val, request, context):
        gcheck[key] = True
        assert request.text == val

    def verify_put(key, val, request, context):
        gcheck[key] = True
        assert request.url == f"{api_root}vis/mails/{mail_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/mails/{mail_id}",
        text=partial(verify_put, "create", None),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/config/theme",
        text=partial(verify, "theme", theme_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/config/size",
        text=partial(verify, "size", size_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/config/template",
        text=partial(verify, "template", template_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/config/subject",
        text=partial(verify, "subject", subject_val),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/name",
        text=partial(verify, "name", name_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/description",
        text=partial(verify, "description", description_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/summary",
        text=partial(verify, "summary", summary_val),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/status",
        text=partial(verify, "status", status_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{mail_id}/content",
        text=partial(verify, "content", content_val),
    )

    # let's verify that shortname works
    # create an e-mail
    Mail(
        mail_id,
        config_path=config_file,  # config location
        theme=theme_val,
        size=size_val,
        template=template_val,
        subject=subject_val,
        name=name_val,
        summary=summary_val,
        description=description_val,
        content=content_val,
        status=status_val,
    )

    # verify that all checks went through
    for k in gcheck.keys():
        assert gcheck[k]

    # print()
    # print(gcheck)


####
#
# Verify that class functions behave as expected
#
####


# send should not send without recipients
def test_mail_send_norec(requests_mock):
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/recipients/to", ""],
            ["get", "/recipients/cc", ""],
            ["get", "/recipients/bcc", ""],
        ],
    }
    m = setup_mail_mock(requests_mock, conf)
    m.send()


# test should send without recipients
def test_mail_test_norec(requests_mock):
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            ["get", "/recipients/to", ""],
            ["get", "/recipients/cc", ""],
            ["get", "/recipients/bcc", ""],
        ],
    }
    gcheck = {"status": False}
    status_val = "testing"

    def verify(key, val, request, context):
        gcheck[key] = True
        assert request.text == val

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{conf['mail_id']}/status",
        text=partial(verify, "status", status_val),
    )

    m = setup_mail_mock(requests_mock, conf)
    m.test()

    assert gcheck["status"]


# send should send if recipients present
def test_mail_send_wrec(requests_mock):
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            [
                "get",
                "/recipients/to",
                "Demo User<novem_demo@novem.no>;Test User<test@novem.no>",
            ],
            ["get", "/recipients/cc", ""],
            ["get", "/recipients/bcc", ""],
        ],
    }
    gcheck = {"status": False}
    status_val = "sending"

    def verify(key, val, request, context):
        gcheck[key] = True
        assert request.text == val

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{conf['mail_id']}/status",
        text=partial(verify, "status", status_val),
    )

    m = setup_mail_mock(requests_mock, conf)
    m.send()

    assert gcheck["status"]


# send should write content, if present, before sending
def test_mail_send_wrec_and_ctnt(requests_mock):
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            [
                "get",
                "/recipients/to",
                "Demo User<novem_demo@novem.no>;Test User<test@novem.no>",
            ],
            ["get", "/recipients/cc", ""],
            ["get", "/recipients/bcc", ""],
        ],
    }
    gcheck = {
        "status": False,
        "content": False,
    }

    status_val = "sending"
    ps = PreviewSection(
        """
    This is our novem mail preview section
    """
    )
    content_val = ps.get_markdown()

    def verify(key, val, request, context):
        gcheck[key] = True
        assert request.text == val

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{conf['mail_id']}/status",
        text=partial(verify, "status", status_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{conf['mail_id']}/content",
        text=partial(verify, "content", content_val),
    )

    m = setup_mail_mock(requests_mock, conf)
    m.add_section(ps)
    m.send()

    assert gcheck["status"]
    assert gcheck["content"]


# test should write content, if present, before sending
def test_mail_test_wrec_and_ctnt(requests_mock):
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]
    conf = {
        "mail_id": "test_mail",
        "reqs": [
            [
                "get",
                "/recipients/to",
                "Demo User<novem_demo@novem.no>;Test User<test@novem.no>",
            ],
            ["get", "/recipients/cc", ""],
            ["get", "/recipients/bcc", ""],
        ],
    }
    gcheck = {
        "status": False,
        "content": False,
    }

    status_val = "testing"
    ps = PreviewSection(
        """
    This is our novem mail preview section
    """
    )
    content_val = ps.get_markdown()

    def verify(key, val, request, context):
        gcheck[key] = True
        assert request.text == val

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{conf['mail_id']}/status",
        text=partial(verify, "status", status_val),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{conf['mail_id']}/content",
        text=partial(verify, "content", content_val),
    )

    m = setup_mail_mock(requests_mock, conf)
    m.add_section(ps)
    m.test()

    assert gcheck["status"]
    assert gcheck["content"]


# verify that calling the function with data invokes content
def test_mail_content_call(requests_mock):
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]
    conf = {
        "mail_id": "test_mail",
        "reqs": [],
    }
    gcheck = {
        "content": False,
    }

    content_val = "long complex test string"

    def verify(key, val, request, context):
        gcheck[key] = True
        assert request.text == val

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/mails/{conf['mail_id']}/content",
        text=partial(verify, "content", content_val),
    )

    m = setup_mail_mock(requests_mock, conf)
    m(content_val)

    assert gcheck["content"]


@patch.dict(os.environ, {"NOVEM_TOKEN": "test_token"})
def test_mail_log(requests_mock, fs):
    requests_mock.register_uri("get", f"{API_ROOT}vis/mails/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}vis/mails/foo/log", text="log_test_mail", status_code=200)

    m = Mail(id="foo", create=False)

    # Redirect stdout to a StringIO object
    f = io.StringIO()
    with redirect_stdout(f):
        m.log

    # Get the printed output
    output = f.getvalue().strip()

    # Assert that the output matches the expected string
    assert output == "log_test_mail"
