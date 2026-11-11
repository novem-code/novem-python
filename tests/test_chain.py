import configparser
import os
from datetime import timedelta

import pytest

from novem import Chain, Job, Repo, Step
from novem.exceptions import NovemChainError
from novem.job.chain import RepoRef

base = os.path.dirname(os.path.abspath(__file__))
config_file = f"{base}/test.conf"
_cfg = configparser.ConfigParser()
_cfg.read(config_file)
api_root = _cfg["general"]["api_root"]

PIPELINE = """gen <- @demo/gen:latest
bundle <- @demo/bundle:latest
extract <- @demo/extract:latest
render <- @demo/render:latest,mem=1G
publish <- @demo/publish:latest

gen! -> bundle -> .extract -> .render -> publish"""


# -- references ----------------------------------------------------------------


@pytest.mark.parametrize(
    "given,written",
    [
        ("report_builder", "report_builder"),
        ("report_builder:prod", "report_builder:prod"),
        ("@bob/tool", "@bob/tool:latest"),
        ("@bob/tool:tag:v1.0.0", "@bob/tool:tag:v1.0.0"),
        ("/r/tool", "tool"),
        ("/u/bob/r/tool:v2", "@bob/tool:v2"),
        ("/j/nightly", "/j/nightly"),
        ("/u/bob/j/nightly", "/u/bob/j/nightly"),
        ("/bob/tool:prod", "@bob/tool:prod"),
        ("bob/tool:tag:v1", "@bob/tool:tag:v1"),
        ("  tool:dev \n", "tool:dev"),
        ("tool,cpu=4,mem=4g,disk=2048M,timeout=120s", "tool,cpu=4,mem=4G,disk=2G,timeout=2m"),
        (RepoRef("bob", "tool", "prod"), "@bob/tool:prod"),
    ],
)
def test_single_reference(given, written):
    assert str(Chain(given)) == written


@pytest.mark.parametrize(
    "bad", ["@bob", "@/tool", "a/b/c", "tool:", "/j/nightly:prod", "/x/", "tool,mem", "tool,gpu=1"]
)
def test_invalid_reference(bad):
    with pytest.raises(NovemChainError):
        Chain(bad)


def test_repo_ref_is_the_legacy_string():
    ref = RepoRef("bob", "tool", "tag:v1")
    assert ref == "/bob/tool:tag:v1"
    assert isinstance(ref, str)
    assert (ref.user, ref.repo, ref.label) == ("bob", "tool", "tag:v1")
    assert ref.get_chain_ref() == "@bob/tool:tag:v1"


def test_none_is_not_a_reference():
    with pytest.raises(NovemChainError):
        Chain({"extract": "a", "render": None})


# -- building --------------------------------------------------------------------


def test_dict_keys_are_edge_tokens():
    chain = Chain(
        {
            "gen!": "@demo/gen",
            "bundle": "@demo/bundle",
            ".extract": "@demo/extract",
            ".render": Step("@demo/render", mem="1G"),
            "publish": "@demo/publish",
        }
    )
    assert str(chain.validate()) == PIPELINE


def test_fluent_builder():
    chain = (
        Chain()
        .step("gen", "@demo/gen")
        .hold()
        .step("bundle", "@demo/bundle")
        .fan("extract", "@demo/extract")
        .fan("render", "@demo/render", mem="1G")
        .step("publish", "@demo/publish")
    )
    assert str(chain.validate()) == PIPELINE
    assert repr(chain) == "Chain('gen! -> bundle -> .extract -> .render -> publish')"
    assert chain.edges[0] == ("gen", "bundle")
    assert chain.refs[0] == "@demo/gen:latest"


def test_list_names_steps_after_their_repo():
    chain = Chain(["data_fetcher", "@bob/chart_builder:prod"])
    assert (
        str(chain)
        == "data_fetcher <- data_fetcher\nchart_builder <- @bob/chart_builder:prod\n\ndata_fetcher -> chart_builder"
    )
    with pytest.raises(NovemChainError):
        Chain(["tool", "tool"])


def test_holds():
    assert str(Chain().hold().step("main", "rb")) == "main <- rb\n\n!main"
    assert str(Chain({"a": "x", "b": Step("y", hold="before")})) == "a <- x\nb <- y\n\na -> !b"
    assert str(Chain({"a": "x", "b": Step("y", hold=True)})) == "a <- x\nb <- y\n\na -> b!"
    assert str(Chain({"!a!": "x", "b": "y"})) == "a <- x\nb <- y\n\n!a! -> b"
    audit = Chain().step("extract", "x").hold("audit").step("render", "y")
    assert str(audit.validate()) == "extract <- x\naudit <- _\nrender <- y\n\nextract -> !audit -> render"
    assert Chain({"a": "x", "audit!": "_", "b": "y"}) == Chain({"a": "x", "!audit": "_", "b": "y"})


def test_single_named_step_keeps_its_name():
    assert str(Chain({"extract": "a"})) == "extract <- a"
    assert str(Chain("a")) == "a"


def test_resources():
    step = Step("tool", cpu=2, mem="512m", disk="10GiB", timeout=timedelta(minutes=90))
    assert step.target == "tool,cpu=2,mem=512M,disk=10G,timeout=90m"
    assert Step("tool", timeout=30).resources == "timeout=30s"
    for bad in ({"cpu": 0.5}, {"cpu": 0}, {"mem": 4}, {"mem": "4"}, {"disk": "0G"}, {"timeout": "5"}, {"timeout": 0}):
        with pytest.raises(NovemChainError):
            Step("tool", **bad)


def test_editing():
    chain = Chain({"extract": "a,mem=2G", "render!": "b"})
    chain["extract"] = "@bob/a:prod"
    assert chain["extract"].target == "@bob/a:prod,mem=2G"
    chain["render"] = "c"
    assert chain["render"].hold == "after"
    chain += {"publish": "p"}
    assert [s.name for s in chain] == ["extract", "render", "publish"]
    del chain["render"]
    assert "render" not in chain and len(chain) == 2
    chain["extract"] = Step("z")
    assert str(chain) == "extract <- z\npublish <- p\n\nextract -> publish"


def test_equality():
    assert Chain("a") == "a:latest"
    assert Chain({"x": "a", "y": "b"}) == "x <- a\ny <- b\n\nx -> y"
    assert Chain("a") != Chain("@me/a")
    assert Chain("a", owner="me") == Chain("@me/a")


# -- validation ------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        None,
        {".a": "x", "b": "y"},
        {"a": "x", ".b": "y"},
        {"a": "x", ".b": "y", "c": "z", ".d": "w", "e": "v"},
        {"a!": "x", ".b": "y", "c": "z"},
        {"a": "x", "!h": "_", ".b": "y", "c": "z"},
        {"a": "x", ".b": Step("y", hold="after"), "c": "z"},
        {"a": "x", ".b": "/j/other", "c": "z"},
        {"a": "x", "audit": "_"},
        {"a": "/j/other,mem=4G"},
    ],
)
def test_invalid_shapes(source):
    with pytest.raises(NovemChainError):
        Chain(source).validate()


@pytest.mark.parametrize("name", ["my step", "a.b", "a,b", "a|b", "a:b", ".a.", "_", "", "README", "a!b"])
def test_invalid_step_names(name):
    with pytest.raises(NovemChainError):
        Chain({name: "x"})


def test_hold_on_a_fan_out():
    with pytest.raises(NovemChainError, match="fan-out and cannot hold"):
        Chain().step("a", "x").fan("b", "y").hold()


# -- parsing ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        PIPELINE,
        "split <- @demo/splitter:latest\njoin <- @demo/concat:latest\n\nsplit! -> join",
        "main <- report_builder\n\n!main",
        "fetch <- data_fetcher\nrollup <- /j/nightly_rollup\n\nfetch -> rollup",
        "a <- x\nb <- _\nc <- y\n\na -> !b -> c",
    ],
)
def test_round_trip(text):
    chain = Chain.parse(text)
    assert str(chain) == text
    assert Chain.parse(str(chain)) == chain


def test_parse_is_order_and_layout_independent():
    text = "render <- b\n\nfetch   <- a\nfetch. -> .mid\nmid <- m\n.mid -> render\n"
    assert [s.token for s in Chain.parse(text)] == ["fetch", ".mid", "render"]
    assert Chain.parse("a <- x\nb <- y") == Chain({"a": "x", "b": "y"})


@pytest.mark.parametrize(
    "text",
    [
        "a <- x\nb <- y\nc <- z\n\na -> b\na -> c",
        "a <- x\nb <- y\nc <- z\n\na -> c\nb -> c",
        "a <- x\nb <- y\nc <- z\n\na -> b",
        "a <- x\nb <- y\n\na -> b -> a",
        "a <- x\n\na -> b",
        "a <- x\na <- y",
        "a <- x\nnonsense",
        "a <- x\nb <- y\n\na, b -> a",
        "a <- x\nb <- y\n\na -> b | a",
        "a <- x\nb <- y\n\na -> .b.",
        "a <- /j/other,cpu=2",
    ],
)
def test_parse_rejects(text):
    with pytest.raises(NovemChainError):
        Chain.parse(text).validate()


# -- jobs ------------------------------------------------------------------------


class Api:
    """Record writes to a mocked job and serve them back."""

    def __init__(self, requests_mock, job="test_job", user="test_user"):
        self.calls = []
        self.files = {}
        root = f"{api_root}code/jobs/{job}"
        requests_mock.register_uri("put", root, text="")
        requests_mock.register_uri("get", f"{api_root}whoami", text=user)
        for leaf in ("config/type", "config/chains", "config/extract", "config/render"):
            requests_mock.register_uri("post", f"{root}/{leaf}", text=lambda r, c, leaf=leaf: self._post(leaf, r, c))
            requests_mock.register_uri("get", f"{root}/{leaf}", text=lambda r, c, leaf=leaf: self._get(leaf, c))

    def _post(self, leaf, request, context):
        self.calls.append(f"POST {leaf}")
        self.files[leaf] = request.text
        return ""

    def _get(self, leaf, context):
        self.calls.append(f"GET {leaf}")
        return self.files.get(leaf, "")


def test_job_chains_kwarg(requests_mock):
    api = Api(requests_mock)
    j = Job("test_job", chains={"extract": "a:prod", "render": "@bob/b"}, config_path=config_file)
    assert api.calls == ["POST config/type", "POST config/chains"]
    assert api.files["config/type"] == "chains"
    assert api.files["config/chains"] == "extract <- a:prod\nrender <- @bob/b:latest\n\nextract -> render"
    assert str(j.chains) == api.files["config/chains"]
    assert j.chains == {"extract": "@test_user/a:prod", "render": "@bob/b"}
    assert [s.name for s in j.chains] == ["extract", "render"]


def test_job_type_is_written_once_and_first(requests_mock):
    api = Api(requests_mock)
    j = Job("test_job", chains="tool", type="chains", config_path=config_file)
    j.chains = "other"
    assert api.calls == ["POST config/type", "POST config/chains", "POST config/chains"]


def test_job_chains_edits(requests_mock):
    api = Api(requests_mock)
    j = Job("test_job", config_path=config_file)
    j.chains = "tool"
    j.chains += {"render": "b"}
    assert api.files["config/chains"] == "tool <- tool\nrender <- b\n\ntool -> render"
    j.chains["render"] = "b:prod"
    j.w("chains", j.chains.get().step("publish", "p"))
    del j.chains["tool"]
    assert api.files["config/chains"] == "render <- b:prod\npublish <- p\n\nrender -> publish"


def test_invalid_chain_is_not_written(requests_mock):
    api = Api(requests_mock)
    j = Job("test_job", config_path=config_file)
    with pytest.raises(NovemChainError):
        j.chains = {"a": "x", ".b": "y"}
    assert api.calls == []


def test_objects_as_references(requests_mock):
    api = Api(requests_mock)
    requests_mock.register_uri("put", f"{api_root}code/repos/tool", text="")
    requests_mock.register_uri("put", f"{api_root}code/jobs/nightly", text="")
    repo = Repo("tool", config_path=config_file)
    other = Repo("shared", user="bob", create=False, config_path=config_file)
    nightly = Job("nightly", config_path=config_file)

    assert repo.ref("prod") == "/test_user/tool:prod"
    assert other.ref("tag:v1") == "/bob/shared:tag:v1"

    Job("test_job", chains={"a": repo, "b": other.ref("tag:v1"), "c": nightly}, config_path=config_file)
    assert api.files["config/chains"] == (
        "a <- @test_user/tool:latest\nb <- @bob/shared:tag:v1\nc <- /u/test_user/j/nightly\n\na -> b -> c"
    )
    assert requests_mock.request_history.count  # whoami is fetched once per token
    assert sum(1 for r in requests_mock.request_history if r.url.endswith("/whoami")) == 1


def test_job_of_another_type_moves_to_chains(requests_mock):
    api = Api(requests_mock)
    api.files["config/type"] = "pdf"
    j = Job("test_job", config_path=config_file)
    assert str(j.chains) == ""
    assert api.files["config/type"] == "pdf"  # reading changes nothing
    j.chains = "tool"
    assert api.files["config/type"] == "chains"
    assert api.files["config/chains"] == "tool"


def test_extract_and_render_are_chain_steps(requests_mock):
    api = Api(requests_mock)
    j = Job("test_job", type="chains", config={"extract": RepoRef("me", "x", "prod")}, config_path=config_file)
    assert api.files["config/chains"] == "extract <- @me/x:prod"
    j.config.render = RepoRef("me", "y", "prod")
    assert api.files["config/chains"] == "extract <- @me/x:prod\nrender <- @me/y:prod\n\nextract -> render"
    assert j.config.extract == "@me/x:prod"
    assert j.config.render == "@me/y:prod"
    assert "POST config/extract" not in api.calls and "POST config/render" not in api.calls

    api.calls.clear()
    j.config = {"render": "r2", "extract": "e2"}
    assert api.calls == ["GET config/chains", "POST config/chains"]
    assert api.files["config/chains"] == "extract <- e2\nrender <- r2\n\nextract -> render"

    j.chains = "tool"
    j.config.extract = "e3"
    assert api.files["config/chains"] == "extract <- e3\ntool <- tool\n\nextract -> tool"


def test_explicit_legacy_type_keeps_single_image_keys(requests_mock):
    api = Api(requests_mock)
    j = Job(
        "test_job",
        type="pdf",
        config={"extract": RepoRef("me", "x", "prod"), "render": "/me/y:dev"},
        config_path=config_file,
    )
    assert api.calls == ["POST config/type", "POST config/extract", "POST config/render"]
    assert api.files["config/extract"] == "/me/x:prod"
    assert j.config.render == "/me/y:dev"
    with pytest.raises(NovemChainError):
        j.chains = "tool"
    with pytest.raises(NovemChainError):
        Job("test_job", type="data", chains="tool", config_path=config_file)
    with pytest.raises(NovemChainError):
        j.config = {"chains": "tool", "extract": "x"}
