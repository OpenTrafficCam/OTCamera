# Device diagnostics

Run as `otc` using `otcamera-diagnose` or `python -m OTCamera.diagnose`.
Without a subcommand, help is shown.

```sh
otcamera-diagnose facts
otcamera-diagnose auto
otcamera-diagnose snap --out /tmp/target.jpg
otcamera-diagnose guided --out-dir /tmp/qa-001
```

## Configuration

`/boot/firmware/otcamera-provisioning.yml` declares the board revision and LTE
population. Automatic and guided checks support v20d. Application settings come
from `~/user_config.yaml`; use `-c PATH` before the subcommand to override it.
`facts` does not read application settings.

## Commands

- `facts`: device and software identity, including provisioning data.
- `auto`: automatic hardware, power, storage, service and connectivity checks.
  Requires `LoadState=loaded` for `otcamera.service`, regardless of whether
  autostart is enabled. The check does not start the service.
  No image capture or interactive tasks.
- `snap`: autofocus and color JPEG capture using the configured rotation.
- `guided`: automatic checks, switch/LED tasks, supply switching and camera capture.

Stop `otcamera.service` before standalone commands. `guided` manages the service
and requires a terminal, a new output directory with an existing parent, a charged
battery and a camera aimed at the test target. Service control requires passwordless
`sudo`. Tasks allow 30 seconds; `X` fails the current area, Ctrl-C aborts.
A UI failure skips remaining UI tasks. Other checks continue independently.
The service stays stopped after the inspection; the Pi remains running for result retrieval. After GPIO release, `pinctrl` explicitly sets LED enable and the PWR LED output HIGH.

## Results

Standalone commands emit JSON. Guided inspection writes:

- `protocol.json`: check results, run ID, start/finish times and overall verdict.
- `manifest.json`: device facts without a `qa` block.
- `testpattern.jpg`: captured image, if available.

Exit codes: `0` PASS, `1` FAIL, `2` tool error, `130` guided interruption.
Partial results are retained; copy files from `/tmp` before reboot.

The separate `otcamera-qa` downloads results, requests visual image acceptance and
publishes successful runs to the device registry. It adds `qa.timestamp` and
`qa.operator` to the registry manifest. See otcamera-qa README for usage.
