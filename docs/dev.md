# Development

## Setup

Although the software is designed to run on a Raspberry Pi, no Pi-specific (or for that matter, Linux-specific) dependencies
need to be installed. Architecture-specific dependencies are guarded by tags.

To set up the development environment, run:

```bash
python3 -m venv venv
source venv/bin/activate
# installs both dev and regular requirements.
pip install -r requirements-dev.txt
# optional, but recommended
pre-commit install
```

## Docker (Optional)

The test suite includes integration tests that require third-party services running on localhost. Easiest is to run them with Docker using the
provided docker-compose.yml file:

```bash
docker compose -f docker/docker-compose.yml up -d
```

## Tests

Run tests with:

```bash
pytest
```

If you want to skip the integration tests that require external services, run:

```bash
pytest -m "not integration"
```
