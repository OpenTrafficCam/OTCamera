host_workspace := env("LOCAL_WORKSPACE_FOLDER", justfile_directory())

# List the available recipes
default:
    @just --list

wait-rabbitmq:
    #!/usr/bin/env python3
    import subprocess
    import sys
    import time

    deadline = time.time() + 10
    while time.time() < deadline:
        p = subprocess.run(('docker', 'exec', 'rabbitmq', 'rabbitmq-diagnostics', '-q', 'ping'))
        if p.returncode == 0:
            sys.exit(0)
        time.sleep(1)
    sys.exit("healthcheck for rabbitmq failed")

wait-rustfs:
    #!/usr/bin/env python3
    import urllib.request
    import sys
    import time

    url = f"http://127.0.0.1:9000/health"
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    sys.exit(0)
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    sys.exit("healthcheck for rustfs failed")


start-containers:
    docker compose -f container/compose.yml up -d

stop-containers:
    docker compose -f container/compose.yml stop

test: start-containers wait-rabbitmq wait-rustfs
    uv run pytest

test-unit:
    uv run pytest -m 'not integration'

super-lint:
    docker run --rm -i --platform linux/amd64 \
        -e RUN_LOCAL=true \
        -e SAVE_SUPER_LINTER_SUMMARY=true \
        -e SUPER_LINTER_OUTPUT_DIRECTORY_NAME=.super-linter \
        -e SUPER_LINTER_SUMMARY_FILE_NAME=SUMMARY.md \
        --env-file .github/super-linter.env \
        --env-file .github/super-linter-fix.env \
        -v {{ host_workspace }}:/tmp/lint ghcr.io/super-linter/super-linter@sha256:c95c714f746edc70e54926a69e229c834ffcdec2450bd3475f7865164d749a56 # slim-v8.7.0

lint:
    uv run ruff check

fix:
    uv run ruff check --fix

format:
    uv run ruff format

typecheck:
    uv run mypy OTCamera tests --config-file pyproject.toml
