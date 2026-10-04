"""Diagnostic results and bounded command execution."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from socket import gethostname
from subprocess import CompletedProcess
from subprocess import run as subprocess_run
from typing import Any


class ToolError(Exception):
    """An error that prevents a meaningful result."""


@dataclass
class Check:
    """One independently evaluated measurement."""

    id: str
    ok: bool
    detail: str
    measured: dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    """A report whose verdict is derived from its checks."""

    checks: list[Check] = field(default_factory=list)
    error: str | None = None
    host: str = field(default_factory=gethostname)
    started: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def ok(self) -> bool:
        """Return whether every check passed without a tool error."""
        return self.error is None and all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        """Serialize without empty optional fields."""
        result = asdict(self)
        result.update(schema=1, ok=self.ok)
        if self.error is None:
            del result["error"]
        for check in result["checks"]:
            if not check["measured"]:
                del check["measured"]
        return result


def run(argv: list[str], timeout: float = 10) -> CompletedProcess[str]:
    """Run an argv without a shell, retaining failure output."""
    return subprocess_run(
        argv, capture_output=True, text=True, timeout=timeout, check=False
    )


def output(argv: list[str], timeout: float = 10) -> str:
    """Read command output or raise with the command's failure reason."""
    result = run(argv, timeout)
    if result.returncode:
        raise RuntimeError(
            f"{argv[0]}: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()
