# Releasing

Two packages are published from this repo:

- **`novem`**: the Python library and the `novem` command.
- **`novem-cli`**: the native novem binary from
  [novem-code/cli](https://github.com/novem-code/cli/releases), packaged as
  platform wheels. `pip install 'novem[cli]'` pulls it in, and the `novem`
  command runs it when it's installed.

Both publish to PyPI through trusted publishing from the `release` environment.

## novem

Publish a GitHub release on this repo with a tag like `v0.6.4`.
`python-publish.yml` then:

1. sets the version from the tag (`scripts/bump_version.py`),
2. runs the tests and builds,
3. commits the version bump to `main`,
4. publishes to PyPI.

## novem-cli

Do this after a novem-code/cli release:

```bash
gh workflow run cli-publish.yml -R novem-code/novem-python -f tag=v0.2.3
```

Or use Actions → **CLI Publish** → Run workflow. The workflow:

1. downloads the release binaries and checks them against `SHA256SUMS`,
2. builds a wheel per platform (`novem-cli/hatch_build.py`) and smoke tests one,
3. publishes them to PyPI,
4. opens a PR that moves the `novem-cli==` pin in the `cli` extra.

New binaries only reach users through that pin, because `pipx upgrade novem`
won't upgrade a dependency the current pin still satisfies. So:

1. merge the bump PR,
2. release novem as above.

The workflow also starts on a `repository_dispatch` of type `cli-release`
with `{"tag": "v0.2.3"}`, so a novem-code/cli release can start it.

### Supported platforms

Wheels are built for the release targets in `PLATFORM_TAGS` in
`novem-cli/hatch_build.py`. A new target needs updates in four places:

- `PLATFORM_TAGS`,
- the target loop in `cli-publish.yml`,
- the platform marker on the `cli` extra in `pyproject.toml`,
- `_NATIVE_PLATFORMS` in `novem_launcher.py`, which decides where the
  deprecation notice suggests installing the extra.

On other platforms the extra installs nothing, and `novem` stays the Python CLI.
