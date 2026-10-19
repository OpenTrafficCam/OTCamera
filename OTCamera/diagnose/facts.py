"""Best-effort device identity without a diagnostic verdict."""

from pathlib import Path
from socket import gethostname
from typing import Any

from OTCamera.diagnose.probes import at
from OTCamera.diagnose.report import output
from OTCamera.version import __version__


def collect(manifest: dict[str, Any]) -> dict[str, Any]:
    """Collect independent identity sources, leaving unavailable fields empty."""
    result: dict[str, Any] = {
        "device": dict.fromkeys(
            ("hostname", "model", "revision", "serial", "wlan_mac"), ""
        ),
        "storage": dict.fromkeys(
            ("name", "capacity_bytes", "cid", "manfid", "oemid", "date"), ""
        ),
        "camera": {},
        "modem": dict.fromkeys(("imei", "iccid", "firmware"), ""),
        "software": {},
        "system": dict.fromkeys(
            ("os", "architecture", "image", "kernel", "firmware"), ""
        ),
    }
    result["device"]["hostname"] = gethostname()
    software: dict[str, Any] = {"version": __version__}
    sources = {
        "device": {
            "model": "/sys/firmware/devicetree/base/model",
            "wlan_mac": "/sys/class/ieee80211/phy0/macaddress",
        },
        "storage": {
            name: f"/sys/block/mmcblk0/device/{name}"
            for name in ("cid", "name", "manfid", "oemid", "date")
        },
        "system": {"image": "/boot/firmware/issue.txt"},
    }
    for group, fields in sources.items():
        for name, path in fields.items():
            try:
                result[group][name] = Path(path).read_text().strip("\x00\n ")
            except Exception:
                result[group][name] = ""
    for group, path, mapping in (
        ("device", "/proc/cpuinfo", {"Revision": "revision", "Serial": "serial"}),
        ("system", "/etc/os-release", {"PRETTY_NAME": "os"}),
    ):
        try:
            separator = "=" if group == "system" else ":"
            values = dict(
                (key.strip(), value.strip().strip('"'))
                for line in Path(path).read_text().splitlines()
                if separator in line
                for key, value in [line.split(separator, 1)]
            )
        except Exception:
            values = {}
        result[group].update(
            {field: values.get(key, "") for key, field in mapping.items()}
        )
    checkout = str(Path(__file__).resolve().parents[2])
    commands = (
        ("storage", "capacity_bytes", ["lsblk", "-bdno", "SIZE", "/dev/mmcblk0"]),
        ("system", "architecture", ["dpkg", "--print-architecture"]),
        ("system", "kernel", ["uname", "-r"]),
        ("system", "firmware", ["vcgencmd", "version"]),
        ("software", "git_commit", ["git", "-C", checkout, "rev-parse", "HEAD"]),
        (
            "software",
            "git_describe",
            ["git", "-C", checkout, "describe", "--tags", "--always"],
        ),
    )
    for group, name, argv in commands:
        target = software if group == "software" else result[group]
        try:
            value = output(argv)
            target[name] = int(value) if name == "capacity_bytes" else value
        except Exception:
            target[name] = ""
    try:
        from picamera2 import Picamera2

        result["camera"]["model"] = Picamera2.global_camera_info()[0]["Model"]
    except Exception:
        result["camera"]["model"] = ""
    if manifest["declared"]["has_lte_module"]:
        for name, command in (
            ("imei", "AT+CGSN"),
            ("firmware", "AT+QGMR"),
            ("iccid", "AT+QCCID"),
        ):
            try:
                result["modem"][name] = at(command).removeprefix("+QCCID:").strip()
            except Exception:
                result["modem"][name] = ""
    for name in ("image", "firmware"):
        result["system"][name] = "; ".join(
            line.strip() for line in result["system"][name].splitlines() if line.strip()
        )
    result["software"] = {"otcamera": software}
    for group, field_order in (
        (
            "provisioning",
            (
                "timestamp",
                "operator",
                "inventory",
                "playbook_commit",
                "ansible_version",
            ),
        ),
        ("declared", ("hardware_revision", "has_lte_module", "otcamera_version")),
    ):
        values = manifest[group]
        ordered = {key: values[key] for key in field_order if key in values}
        result[group] = {**ordered, **values}
    result["provisioning"]["declared"] = result.pop("declared")
    return {"schema": 1, **result}
