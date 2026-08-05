# Development

## Setup

This project manages its dependencies with `uv`.

To setup a dev environment, make sure you have `uv` installed. Then simply run

```bash
uv sync
# optional, but recommended
pre-commit install
```

Check [dependency_management.md](./dependency_management.md) for more information.

## Container (Optional)

The test suite includes integration tests that require third-party services running on localhost. Easiest is to run them with a container engine
of your choice that supports the compose specification, e.g. Docker:

```bash
docker compose -f container/compose.yml up -d
```

## Tests

Run tests with:

```bash
uv run pytest
```

If you want to skip the integration tests that require external services, run:

```bash
uv run pytest -m "not integration"
```

## just

The repository provides a `justfile` with various recipes. It assumes `docker` CLI for managing containers, if you use a compatible
runtime like `podman` make sure you have an alias or symlink in place.
Some recipes use [act](https://github.com/nektos/act) for running Github Actions locally.
