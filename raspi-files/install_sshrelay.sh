#!/bin/bash

echo "OTCamera SSH relay server setup"
echo "############################"
echo " "

read -r -e -p "server address: " -i "relay.opentrafficcam.org" SERVER
read -r -e -p "server port: " -i "22" PORT
read -r -e -p "public key: " PUBKEY


echo "### Generating new SSH key"
HOME="/home/$SUDO_USER"
runuser -l "$SUDO_USER" -c "ssh-keygen -t ed25519 -q -f '$HOME/.ssh/id_ed25519' -N ''"

echo "### Adding remote server public key as authorized key"
echo "" >> "$HOME"/.ssh/authorized_keys
echo "$PUBKEY" >> "$HOME"/.ssh/authorized_keys

echo ""
echo ""
cat "$HOME/.ssh/id_ed25519.pub"
echo ""
echo ""

read -r -e -p "Copy public key above to relay server (username: $HOSTNAME)"

echo "### Configuring service"
RELAYSERVICE="./raspi-files/sshrelay.service"
cp $RELAYSERVICE /lib/systemd/system
RELAYSERVICE="/lib/systemd/system/sshrelay.service"

SSHCMD="/bin/ssh -NT -R 0:localhost:22 $HOSTNAME@$SERVER -p $PORT"

sed $RELAYSERVICE -i -e "s?^User=username?User=$SUDO_USER?g"
sed $RELAYSERVICE -i -e "s?^ExecStart=/bin/ssh -NT -R 0:localhost:22 hostname@server -p port?ExecStart=$SSHCMD?g"

echo "    ServerAliveInterval 240" >> /etc/ssh/ssh_config

systemctl daemon-reload
systemctl disable sshrelay.service

echo "### please connect once to add host key using the following command:"
echo "$SSHCMD"

