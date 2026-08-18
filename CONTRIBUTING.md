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
As we target python 3.10 or newer it's advisable to use python 3.10 for
development. To get started simply clone the repository and run the below
commands.

```bash
uv sync
make lint
```

## Before commiting
Please make sure that all files confirm to the style guidelines

```bash
make format   # apply formatting and autofixes
make lint     # check formatting, lint and types
```

## Pull requests
Please feel free to send over pull requests, but do make sure that CI is
green.
