# OTCamera

OTCamera is a core module of the [OpenTrafficCam framework](https://github.com/OpenTrafficCam) to record videos over multiple days with a custom camera system based on Raspberry Pi Zero W. In the recorded videos, one can detect and track objects (road users) using [OTVision](https://github.com/OpenTrafficCam/OTVision) or other tools and on the resulting trajectories, one can perform traffic analysis using [OTAnalytics](https://github.com/OpenTrafficCam/OTAnalytics).

Check out the [documentation](https://docs.opentrafficcam.org/otcamera) for detailed instructions on how to assemble and use OTCamera.

We appreciate your support in the form of both code and comments. First, please have a look at the [contribute](https://docs.opentrafficcam.org/contribute) section of the OpenTrafficCam documentation.

## Setup a Raspberry Pi 4 for Development

You will need a Raspberry Pi 2B/3B(+)/4 (the 2 GB works well), and a camera module (no USB webcam).

Download and install latest Raspberry Pi OS **Lite** (32-bit) on a micro SD card using the [Raspberry Pi Imager](https://www.raspberrypi.org/software/).

Add a empty file named ```ssh``` to the boot partition to [enable ssh on first boot](https://www.raspberrypi.org/documentation/remote-access/ssh/README.md).

Boot the Pi on LAN or wifi ([add your wifi first](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)).

### Password-less Authentication

Generate SSH-Keys for password-less connection. On your desktop computer run

```bash
ssh-keygen
```

to generate a public private key combination. Add the private key to your ssh-agent (you may need to [update OpenSSH on Windows](https://superuser.com/questions/1395962/is-it-possible-to-update-the-built-in-openssh-client-in-windows-10/1555453#1555453)).

Connect to the pi using ssh (```ssh pi@raspberry```)to the Pi using password authentication.

Create and edit the needed ```authorized_keys``` file.

```bash
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
```

Copy your public key on the host and paste it on the pi, save&close using Ctrl+X - Enter - Y.
You should now be able to connect to the Pi without password.

### Setup the Raspberry

 and update the pi by running apt and reboot.

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

Reconnect to your pi and run the raspberry configuration tool.

```bash
sudo raspi-config
```

Change the following settings to appropriate values:

- System Options
  - Password
  - Hostname
- Interface Options
  - Camera (enable)
- Localization Options
  - Locale (for example de_DE.UTF-8 UTF-8 as default)
  - Timezone (Europe/Berlin)
  - WLAN Country (DE)

Reboot the Pi afterwards.

### Setup VS Code Remote Development Extension

Install the [Remote-SSH](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack) extension on your desktop using the marketplace.

Add the Pi as [remote host](https://code.visualstudio.com/docs/remote/ssh#_connect-to-a-remote-host). 
Connect to the Pi using the Remote-SSH extension (rightclick on the ne host - "Connect to Host in New Window"). When asked for the operating system of the host, choose "Linux". VS code will download and install the necessary dependencies on the Pi.

Open the extension manager in the new windows an install all nessacery extensions.

### Setup Git and GitHub

Install git using apt.

```bash
sudo apt install git
```

To setup your git commit name and email, login to your github account and copy your [private commit email](https://docs.github.com/en/free-pro-team@latest/github/setting-up-and-managing-your-github-user-account/setting-your-commit-email-address).

On the pi run

```bash
git config --global user.name "Your Name"
git config --global user.email "123456+username@users.noreply.github.com"
```

The easiest way to setup your GitHub credentials is to use vs code. In the file explorer panel click "Clone Repository" and choose "Clone from GitHub". Depending on your desktop computer settings, a browser tab will open to login into your GitHub account. Afterwards, you can search for "OpenTrafficCam/OTCamera" inside the vs code command prompt and select a folder to pull (choose /home/pi by default).

### Setup Python and Dependencies

By default, Raspberry OS light doesn't come with PIP installed. We will need it, to install required packages.

```bash
sudo apt-get install python3-pip
```

Raspberry OS ships with python 2 and python 3. By default python 2 is used. You may want to change that to python 3 by adding two single lines to ```.bashrc```.

```bash
nano ~/.bashrc

# add the following two lines at the end of the file (without #)

# alias python='/usr/bin/python3'
# alias pip=pip3

# save & exit (Ctrl+X - Y)

source ~/.bashrc

python --version
pip --version
```

Both commands should state, that they are (using) python 3.7.

## License

This software is licensed under the [GPL-3.0 License](LICENSE).
