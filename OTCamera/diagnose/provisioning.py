"""Read Ansible's declared hardware and provisioning provenance."""

import json
from pathlib import Path
from typing import Any

import yaml

from OTCamera.diagnose.hardware import SWITCHES
from OTCamera.diagnose.report import ToolError

PROVISIONING_PATH = Path("/boot/firmware/otcamera-provisioning.yml")


def load_provisioning() -> dict[str, Any]:
    """Read once, validate required declarations and retain both manifest blocks."""
    try:
        data = yaml.safe_load(PROVISIONING_PATH.read_text())
        if not isinstance(data, dict):
            raise ValueError("Expected a YAML mapping")
        declared = data.get("declared")
        provenance = data.get("provisioning")
        if not isinstance(declared, dict) or not isinstance(provenance, dict):
            raise ValueError("Expected declared and provisioning mappings")
        revision = declared.get("hardware_revision")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError("declared.hardware_revision must be a nonempty string")
        if not isinstance(declared.get("has_lte_module"), bool):
            raise ValueError("declared.has_lte_module must be a boolean")
        switches = declared.get("fitted_switches", [])
        if (
            not isinstance(switches, list)
            or any(
                not isinstance(name, str) or name not in SWITCHES for name in switches
            )
            or len(switches) != len(set(switches))
        ):
            raise ValueError(
                "declared.fitted_switches must be a list of unique names: PWR, WIFI, REC, LIGHT"
            )
        # YAML timestamps are represented as strings in the JSON manifest.
        return json.loads(
            json.dumps({"provisioning": provenance, "declared": declared}, default=str)
        )
    except Exception as exc:
        raise ToolError(f"Cannot load provisioning {PROVISIONING_PATH}: {exc}") from exc
