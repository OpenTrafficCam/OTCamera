## Dependency Management

OTCamera's dependencies are managed via `uv`.
The handling is different for the development environment and target environment (Raspberry Pi Zero 2 W).

- Top-level dependencies are managed in `pyproject.toml`. Raspberry Pi-specific dependencies are managed in the `pi` dependency group (`[project.optional-dependencies]`) as they do not need to be installed in the dev environment.
- The locked versions are kept both
    - in `uv.lock` for repoducible dev environments
    - in `requirements.txt` for reproducible target environments, i. e. on the Raspberry Pi.

## Development Environment

To set up the development environment, simply run

```sh
uv sync --dev
```

This will install the base and development requirements into a new virtual environment.

## Target Environment (on Raspberry Pi Zero 2 W)

Make sure that the `picamera2` package is installed as a system package (the recommended approach via [the official repo](https://github.com/raspberrypi/picamera2)).

```sh
apt list --installed | grep picamera2
```

Create a new venv with access to system-site Python packages (including picamera2):

```sh
python3 -m venv --system-site-packages .venv
```

Then install the remaining requirements with pip:

```sh
pip install -r requirements.txt
```

## Adding or updating new requirements

Follow the usual process of adding or updating dependencies with uv, e.g.:

```sh
uv add <mypackage>
```

For updating packages:

```sh
# update all packages
uv lock --upgrade

# update a specific package
uv lock --upgrade-package <mypackage>
```

After any update to `uv.lock`, the `requirements.txt` will be updated automatically by a pre-commit hook.

If pre-commit is not used, this can be done manually via:

```sh
uv export --no-hashes --extra pi --format requirements-txt > requirements.txt
```
