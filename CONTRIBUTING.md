# Contribution and development
the novem python library and platform is under active development, contributions
or issues are most welcome.

## Guidelines
To mitigate supplychain risks as well as keep the scope of the library small
we try to have as few runtime dependencies as possible.

If you've included new run-time dependencies, please consider the neccessity
of the entire library, or if the feature you need can be safely included as a
file in the repository.


## Getting started
As we target python 3.8 or newer it's advisable to use python 3.8 for
development. To get started simply clone the repository and run the below
commands.

```bash
poetry install
poetry shell
pre-commit run --all-files
```

## Before commiting
Please make sure that all files confirm to the style guidelines

```bash
pre-commit run --all-files
```

## Pull requests
Please feel free to send over pull requests, but do make sure that the
post-commit hooks are all green.
