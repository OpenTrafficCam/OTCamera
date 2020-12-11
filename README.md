# OTCamera

OTCamera is a core module of the [OpenTrafficCam framework](https://github.com/OpenTrafficCam) to record videos over multiple days with a custom camera system based on Raspberry Pi Zero W. In the recorded videos, one can detect and track objects (road users) using [OTVision](https://github.com/OpenTrafficCam/OTVision) or other tools and on the resulting trajectories, one can perform traffic analysis using [OTAnalytics](https://github.com/OpenTrafficCam/OTAnalytics).

Check out the [documentation](https://docs.opentrafficcam.org/otcamera) for detailed instructions on how to assemble and use OTCamera.

We appreciate your support in the form of both code and comments. First, please have a look at the [contribute](https://docs.opentrafficcam.org/contribute) section of the OpenTrafficCam documentation.

## Install Raspberry Pi 4 for Development

Download latest Raspberry OS and install it on a micro SD card using the [Raspberry Pi Imager](https://www.raspberrypi.org/software/).

Add a empty file named ```ssh``` to the boot partition to enable ssh on first boot.

Boot the Pi on LAN or wifi ([add your wifi first](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)).

Connect to the Pi using ssh and update the Pi by running apt and reboot.

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

### Password-less Authentication

Generate SSH-Keys for password-less connection. On your desktop computer run

```bash
ssh-keygen
```

to generate a public private key combination. Add the private key to your ssh-agent (you may need to [update OpenSSH on Windows](https://superuser.com/questions/1395962/is-it-possible-to-update-the-built-in-openssh-client-in-windows-10/1555453#1555453)).

Copy the public key to the Pi, using SSH and password authentication.

```bash
mkdir -p ~/.ssh
nano .~/ssh/authorized_keys
```

Copy the public key and save&close with Ctrl+X - Enter - Y.
You should now be able to connect to the Pi without password.

You can now add the Pi as [remote host](https://code.visualstudio.com/docs/remote/ssh#_connect-to-a-remote-host) using the [Remote-SSH](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack) extension in VScode.

Don't forget to install your extension on the remote Pi.

## License

This software is licensed under the [GPL-3.0 License](LICENSE).
