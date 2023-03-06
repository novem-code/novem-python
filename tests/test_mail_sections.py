import configparser
import os
from functools import partial

from novem import Plot
from novem.mail import (
    AttachmentSection,
    AuthorSection,
    CalloutSection,
    CodeSection,
    MarkdownSection,
    ParagraphSection,
    PreviewSection,
    VisSection,
)


def test_mail_section_visualisation(requests_mock):
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

    def verify_put(key, val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, "create", "ignore"),
    )

    requests_mock.register_uri(
        "get", f"{api_root}vis/plots/{plot_id}/shortname", text=plot_shortname
    )

    # grab a reference to a plot
    plt = Plot(
        plot_id,
        config_path=config_file,  # config location
    )

    # construct visualisation section
    vss = VisSection(
        plt,  # a reference to the plot to include
        width="100%",
        align="center",
        include_title=False,
        include_caption=False,
        include_link=True,
        override_title="New title",
        override_caption=None,
        b=["l2 gray-300 purple", "r1 red"],
        bg="gray-300 purple",
    )

    # get markdown
    vssmd = vss.get_markdown()

    assert (
        vssmd
        == f"""{{{{ vis
  ref: {plot_shortname}
  width: 100%
  align: center
  include link: true
  override title: New title
  b: [l2 gray-300 purple, r1 red]
  bg: gray-300 purple
}}}}

{{{{ /vis }}}}"""
    )


def test_mail_section_preview(requests_mock):
    # add preview section
    # construct visualisation section
    txt = "This is our example preview text"
    pvs = PreviewSection(txt)
    pvsm = pvs.get_markdown()

    assert pvsm == f"{{{{ preview }}}}\n{txt}\n{{{{ /preview }}}}"


def test_mail_section_callout(requests_mock):
    # add preview section
    # construct visualisation section
    cs = CalloutSection("""This is our example callout text""")

    rest = """{{ callout
  type: info
}}
This is our example callout text
{{ /callout }}"""

    assert cs.get_markdown() == rest


def test_mail_section_author(requests_mock):
    aas = AuthorSection("demo")

    rest = """{{ author
  username: demo
  include bio: true
  include pciture: true
}}

{{ /author }}"""

    assert aas.get_markdown() == rest


def test_mail_section_paragraph(requests_mock):
    pgs = ParagraphSection(
        "This is a simple markdown text for our section",
        m=["t3", "b3"],  # margin top and bottom
        font_size="s",  # small font size
        font_style="i",  # italic
        fg="gray-500",  # in soft gray
    )

    rest = """{{ paragraph
  font size: s
  font style: i
  m: [t3, b3]
  fg: gray-500
}}
This is a simple markdown text for our section
{{ /paragraph }}"""

    assert pgs.get_markdown() == rest


def test_mail_section_attachment(requests_mock):
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

    def verify_put(key, val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, "create", "ignore"),
    )

    requests_mock.register_uri(
        "get", f"{api_root}vis/plots/{plot_id}/shortname", text=plot_shortname
    )

    # grab a reference to a plot
    plt = Plot(
        plot_id,
        config_path=config_file,  # config location
    )

    aas = AttachmentSection(plt)
    rest = f"""{{{{ attachment
  ref: {plt.shortname}
  format: pdf
}}}}

{{{{ /attachment }}}}"""

    assert aas.get_markdown() == rest


def test_mail_section_markdown(requests_mock):
    mss = """
# A title

Followed by a paragraph

 * And
 * a
 * list

"""
    ms = MarkdownSection(mss)

    assert ms.get_markdown() == mss


def test_mail_section_code(requests_mock):
    css = """
# comment
print("Hello, Wordl!\\n")
"""
    cs = CodeSection(css, lang="python")

    cans = f"""```python
{css}
```"""

    assert cs.get_markdown() == cans
