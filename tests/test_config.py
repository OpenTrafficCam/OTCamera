import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from OTCamera.config import Config, parse_user_config


def test_parse_user_config_minimal(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            debug_mode: true
            recording:
              start_hour: 7
              end_hour: 20
              interval_length: 10
              num_intervals: 0
              min_free_space: 2
            camera:
              fps: 15
              resolution:
                width: 1920
                height: 1080
              exposure_mode: auto
              drc_strength: off
              rotation: 0
              awb_mode: auto
              meter_mode: average
            preview:
              path: ~/OTCamera/webfiles/preview.jpg
              format: jpeg
              interval: 5
              send_to_external: false
              url: http://localhost:5000
            video:
              dir: ~/videos/
              format: h264
              resolution:
                width: 640
                height: 480
              encoder:
                profile: high
                level: "4"
                bitrate: 600000
                quality: 30
            wifi:
              delay: 900
            hardware:
              pcb_version: v2
              use_leds: true
              use_buttons: true
              use_adc: true
            msteams:
              enable: false
              url: ""
            adc:
              threshold_external_power: 2.5
              threshold_low_battery: 3.3
            ftp_upload:
              enable: true
              host: example.com
              port: 21
              user: user
              password: pass
              server_source: /
            """),
        encoding="utf-8",
    )

    config = parse_user_config(str(config_file))

    assert config.debug_mode is True
    assert config.recording.start_hour == 7
    assert config.recording.end_hour == 20
    assert config.camera.fps == 15
    assert config.camera.resolution == (1920, 1080)
    assert config.video.resolution == (640, 480)
    assert config.video.encoder.profile == "high"
    assert config.video.encoder.bitrate == 600000
    assert config.hardware.pcb_version == "v2"
    assert config.hardware.use_leds is True
    assert config.hardware.use_buttons is True
    assert config.hardware.use_adc is True
    assert config.adc.threshold_low_battery == 3.3
    assert config.ftp_upload.enable is True


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    config = parse_user_config(str(tmp_path / "missing.yaml"))

    assert config.camera.fps == 20
    assert config.debug_mode is False


def test_default_config_has_sensible_values() -> None:
    config = Config()

    assert config.camera.fps == 20
    assert config.recording.start_hour == 6
    assert config.recording.end_hour == 22
    assert config.hardware.pcb_version == "v2"
    assert config.hardware.use_leds is False
    assert config.hardware.use_buttons is False
    assert config.hardware.use_adc is False
    assert config.ftp_upload.enable is False


def test_ftp_upload_requires_host_when_enabled() -> None:
    with pytest.raises(ValidationError, match="host"):
        Config.model_validate(
            {"ftp_upload": {"enable": True, "user": "u", "password": "p"}}
        )


def test_msteams_requires_url_when_enabled() -> None:
    with pytest.raises(ValidationError, match="url"):
        Config.model_validate({"msteams": {"enable": True}})
