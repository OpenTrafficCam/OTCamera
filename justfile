wait-rabbitmq:
    #!/usr/bin/env python3
    import subprocess
    import sys
    import time

    # `ping` only proves the Erlang VM is up, not that the AMQP listener is
    # accepting connections -- clients that connect in between get an
    # IncompatibleProtocolError. `await_startup` waits for the application to
    # finish booting, `check_port_connectivity` for the listeners to be open.
    checks = (
        ('rabbitmq-diagnostics', '-q', 'check_running'),
        ('rabbitmq-diagnostics', '-q', 'check_port_listener', '5672'),
    )
    # Output is captured: while the broker boots, the checks fail and
    # rabbitmq-diagnostics prints a long report every second. On timeout the
    # container logs are the more useful source anyway (CI dumps them).
    deadline = time.time() + 60
    while time.time() < deadline:
        if all(
            subprocess.run(
                ('docker', 'exec', 'rabbitmq') + check, capture_output=True
            ).returncode == 0
            for check in checks
        ):
            sys.exit(0)
        time.sleep(1)
    sys.exit("healthcheck for rabbitmq failed")

wait-rustfs:
    #!/usr/bin/env python3
    import os
    import urllib.request
    import sys
    import time

    host = os.getenv("OTC_TEST_S3_HOST", "127.0.0.1")
    port = os.getenv("OTC_TEST_S3_PORT", "9000")
    url = f"http://{host}:{port}/health"
    deadline = time.time() + 60
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

test-integration: start-containers wait-rabbitmq wait-rustfs
    uv run pytest -m integration

super-lint:
    act -W .github/workflows/linter.yml --container-architecture linux/amd64 --env RUN_LOCAL=true --env SHELL=/bin/bash

lint:
    uv run ruff check

fix:
    uv run ruff check --fix
