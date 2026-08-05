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
    act -W .github/workflows/linter.yml --container-architecture linux/amd64 --env RUN_LOCAL=true --env SHELL=/bin/bash

lint:
    uv run ruff check

fix:
    uv run ruff check --fix
