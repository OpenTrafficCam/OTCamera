#!/bin/bash

USER_HOME=$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)
CONFIG="/boot/config.txt"
OTCAMERA=$USER_HOME/"OTCamera"
OTCSERVICE="/lib/systemd/system/otcamera.service"
RCLOCAL="/etc/rc.local"
NGINXDEFAULT="/etc/nginx/sites-available/default"
HOSTAPD_DIR="/etc/hostapd" 
DHCPCDCONF="/etc/dhcpcd.conf"
HWCLOCK="/lib/udev/hwclock-set"

echo "$USER_HOME"
echo "OTCamera Uninstall Script"
echo "############################"
echo " "

echo "Deactivate OTCamera service"
systemctl stop otcamera.service
systemctl disable otcamera.service
rm $OTCSERVICE

echo "Restore boot/config.txt"
rm $CONFIG
mv $CONFIG.backup $CONFIG

echo "Restore rc.local"
rm $RCLOCAL
mv $RCLOCAL.backup $RCLOCAL

echo "Revert to fake-hwclock"
apt purge i2c-tools -y
update-rc.d fake-hwclock defaults
systemctl enable fake-hwclock

rm $HWCLOCK
mv $HWCLOCK.backup $HWCLOCK

echo "Stop and disable services"
systemctl stop dhcpcd.service
systemctl stop dnsmasq.service
systemctl stop hostapd.service
systemctl disable dhcpcd.service
systemctl disable dnsmasq.service
systemctl disable hostapd.service

echo "Mask hostapd.service"
systemctl mask hostapd.service

echo "   Uninstall services"
apt purge hostapd -y
apt purge dhcpcd -y
apt purge dnsmasq -y

rm -rf $HOSTAPD_DIR

rm $DHCPCDCONF
cp $DHCPCDCONF.backup $DHCPCDCONF

echo "Uninstall nginx"
systemctl stop nginx.service
systemctl disable nginx.service
sed $NGINXDEFAULT -i -e "s?root $OTCAMERA/webfiles?root /var/www/html?g"
apt remove nginx -y

echo "Remove OTCamera directory"
cd "$OTCAMERA" || { echo "Error: Cannot find OTCamera directory"; exit 1; }
pip uninstall -r requirements.txt -y
cd "$USER_HOME" || { echo "Error: Cannot find HOME directory"; exit 1; }
rm -rf "$OTCAMERA"

echo "#### Uninstall packages"
apt remove python3-pip
apt remove python3-venv

echo "Uninstalling GL Legacy Drivers"
apt remove gldriver-test libgl1-mesa-dri

echo "Disable I2C bus for hwclock"
raspi-config nonint do_i2c 1
raspi-config nonint do_legacy 1 

systemctl reset-failed
systemctl daemon-reload

echo "#########"
echo "Done. Please reboot to finalise uninstall."
echo "#########"
