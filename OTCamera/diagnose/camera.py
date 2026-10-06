"""Production-equivalent capture and autofocus diagnostics."""

from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep
from typing import TYPE_CHECKING, Any

from OTCamera.diagnose.report import Check

if TYPE_CHECKING:
    from OTCamera.config import Config


AE_SETTLE_S = 2.0
AF_TIMEOUT_S = 15.0
EXPOSURE_LIMIT_RATIO = 0.95
GAIN_LIMIT_RATIO = 0.99
EXPECTED_FRAME_FORMAT = "YUV420"
EXPECTED_FRAME_DTYPE = "uint8"
EXPECTED_FRAME_NDIM = 2
CAPTURE_CHECK_COUNT = 2


def present() -> Check:
    """Check camera enumeration without opening the camera."""
    try:
        from picamera2 import Picamera2

        cameras = Picamera2.global_camera_info()
        return Check(
            "camera.present",
            bool(cameras),
            str(cameras) if cameras else "No camera detected; check the ribbon cable",
        )
    except Exception as exc:
        return Check("camera.present", False, str(exc))


def frame_check(
    array: Any,
    stream: dict[str, Any],
    metadata: dict[str, Any],
    limits: dict[str, Any],
    config: Config,
    check_id: str,
) -> Check:
    """Evaluate resolution, YUV format, variation and jointly railed AE controls."""
    try:
        width, height = stream["size"]
        y = array[:height, :width]
        exposure, gain = metadata["ExposureTime"], metadata["AnalogueGain"]
        max_exposure = min(
            limits["ExposureTime"][1], int(1_000_000 / config.camera.fps)
        )
        exposure_at_limit = exposure >= EXPOSURE_LIMIT_RATIO * max_exposure
        gain_at_limit = gain >= GAIN_LIMIT_RATIO * limits["AnalogueGain"][1]
        measured = {
            "width": width,
            "height": height,
            "min": int(y.min()),
            "max": int(y.max()),
            "mean": float(y.mean()),
            "saturated_frac": float((y == 255).mean()),
            "exposure_us": exposure,
            "gain": gain,
            "exposure_at_limit": exposure_at_limit,
            "gain_at_limit": gain_at_limit,
        }
        failures = []
        if (width, height) != config.video.resolution:
            failures.append(
                f"resolution {width}x{height}, expected {config.video.resolution}"
            )
        if (
            stream["format"] != EXPECTED_FRAME_FORMAT
            or array.ndim != EXPECTED_FRAME_NDIM
            or str(array.dtype) != EXPECTED_FRAME_DTYPE
            or array.shape[0] != height * 3 // 2
            or array.shape[1] < width
        ):
            failures.append(
                f"unexpected frame format {stream['format']} "
                f"(expected {EXPECTED_FRAME_FORMAT}), "
                f"shape {array.shape} (expected {EXPECTED_FRAME_NDIM} dimensions, "
                f"{height * 3 // 2} rows, at least {width} columns), "
                f"dtype {array.dtype} (expected {EXPECTED_FRAME_DTYPE})"
            )
        if measured["min"] == measured["max"]:
            failures.append(
                f"constant image at {measured['min']} "
                "(expected varying pixel values, min < max)"
            )
        if exposure_at_limit and gain_at_limit:
            failures.append(
                f"exposure control railed at {exposure} us and gain {gain} - lens cap, bench light off or sensor not exposing"
            )
        return Check(
            check_id,
            not failures,
            "; ".join(failures)
            if failures
            else "Nonconstant frame at the configured resolution; exposure control within range",
            measured,
        )
    except Exception as exc:
        return Check(check_id, False, str(exc))


def capture(config: Config, out: Path) -> list[Check]:
    """Autofocus and save one color frame with its Y-plane measurements."""
    checks: list[Check] = []
    check_id = "camera.snap"
    camera = None
    try:
        import cv2
        from libcamera import Transform, controls
        from picamera2 import Picamera2

        from OTCamera.module.camera.picamera2 import (
            AWB_MODE_MAP,
            EXPOSURE_MODE_MAP,
            METER_MODE_MAP,
            load_tuning_with_drc,
        )

        camera = Picamera2(tuning=load_tuning_with_drc(config.camera.drc_strength))
        rotation = config.camera.rotation
        transform = Transform(
            hflip=rotation in (180, 270),
            vflip=rotation in (90, 180),
            transpose=rotation in (90, 270),
        )
        camera.configure(
            camera.create_video_configuration(
                main={
                    "size": config.video.resolution,
                    "format": EXPECTED_FRAME_FORMAT,
                },
                sensor={"output_size": config.camera.resolution},
                transform=transform,
            )
        )
        frame_duration = int(1_000_000 / config.camera.fps)
        settings = {
            "AeExposureMode": EXPOSURE_MODE_MAP.get(
                config.camera.exposure_mode, controls.AeExposureModeEnum.Normal
            ),
            "AeMeteringMode": METER_MODE_MAP.get(
                config.camera.meter_mode, controls.AeMeteringModeEnum.CentreWeighted
            ),
            "FrameDurationLimits": (frame_duration, frame_duration),
        }
        if config.camera.awb_mode == "greyworld":
            settings.update(AwbEnable=False, ColourGains=(1.5, 1.5))
        else:
            settings["AwbMode"] = AWB_MODE_MAP.get(
                config.camera.awb_mode, controls.AwbModeEnum.Auto
            )
        camera.set_controls(settings)
        camera.start()
        started = monotonic()
        state = None
        try:
            camera.set_controls(
                {
                    "AfMode": controls.AfModeEnum.Auto,
                    "AfTrigger": controls.AfTriggerEnum.Start,
                }
            )
            while monotonic() - started < AF_TIMEOUT_S:
                state = camera.capture_metadata().get("AfState")
                if state in (
                    controls.AfStateEnum.Focused,
                    controls.AfStateEnum.Failed,
                ):
                    break
                sleep(0.1)
            checks.append(
                Check(
                    "camera.focus",
                    state == controls.AfStateEnum.Focused,
                    "Autofocus focused"
                    if state == controls.AfStateEnum.Focused
                    else "Autofocus failed; check camera module, lens and test target"
                    if state == controls.AfStateEnum.Failed
                    else f"Autofocus timed out after {AF_TIMEOUT_S} s (state {state})",
                    {"af_duration_s": monotonic() - started},
                )
            )
        except Exception as exc:
            checks.append(Check("camera.focus", False, str(exc)))
        sleep(AE_SETTLE_S)
        request = camera.capture_request()
        try:
            array = request.make_array("main")
            metadata = request.get_metadata()
            stream = camera.camera_configuration()["main"]
            if checks and "LensPosition" in metadata:
                checks[0].measured["lens_position_dpt"] = metadata["LensPosition"]
            check = frame_check(
                array, stream, metadata, camera.camera_controls, config, check_id
            )
            checks.append(check)
            try:
                width, height = stream["size"]
                # Convert all Y/U/V planes before removing stride padding.
                bgr = cv2.cvtColor(array, cv2.COLOR_YUV2BGR_I420)
                if not cv2.imwrite(str(out), bgr[:height, :width]):
                    raise OSError(f"Cannot write image to {out}")
                check.detail += f"; image saved to {out}"
            except Exception as exc:
                check.ok = False
                check.detail += f"; image save failed: {exc}"
        finally:
            request.release()
    except Exception as exc:
        if not any(check.id == "camera.focus" for check in checks):
            checks.append(Check("camera.focus", False, str(exc)))
        if not any(check.id == check_id for check in checks):
            checks.append(Check(check_id, False, str(exc)))
        else:
            checks[-1].ok = False
            checks[-1].detail += f"; {exc}"
    finally:
        if camera is not None:
            try:
                camera.close()
            except Exception as exc:
                if checks:
                    checks[-1].ok = False
                    checks[-1].detail += f"; camera close failed: {exc}"
    return checks
