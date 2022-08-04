#!/bin/bash

USER_HOME=$(getent passwd ${SUDO_USER:-$USER} | cut -d: -f6)
CONFIG="/boot/config.txt"
OTCAMERA=$USER_HOME/"OTCamera"
OTCSERVICE="/lib/systemd/system/otcamera.service"
RCLOCAL="/etc/rc.local"
NGINXDEFAULT="/etc/nginx/sites-available/default"
HOSTAPD="/etc/default/hostapd"
HOSTAPDCONF="/etc/hostapd/hostapd.conf"
DHCPCONF="/etc/dhcpcd.conf"
DNSMASQCONF="/etc/dnsmasq.conf"
HWCLOCK="/lib/udev/hwclock-set"

echo "$USER_HOME"
echo "OTCamera Uninstall Script"
echo "############################"
echo " "

echo "Deactivate OTCamera service"
systemctl stop otcamera.service
systemctl disable otcamera.service
rm $OTCSERVICE

echo "Disable WiFi AP"
sed $RCLOCAL -i -e "/\/bin\/bash \/usr\/local\/bin\/wifistart/d" 
apt remove hostapd dnsmasq dhcpcd -y

sed $HWCLOCK -i -e "/#if.*systemd.*then/s/#//g"
sed $HWCLOCK -i -e "/#.*exit0/s/#//g"
sed $HWCLOCK -i -e "/#fi/s/#//g"
sed $HWCLOCK -i -e "/#\/sbin\/hwclock.*--systz/s/#//g"

echo "Enable Services"
systemctl enable dhcpcd.service
systemctl enable dnsmasq.service
systemctl enable hostapd.service

echo "Mask hostapd.service"
systemctl mask hostapd.service

echo "   Uninstall services"
cp $HOSTAPD".backup" $HOSTAPD 
rm $HOSTAPD".backup" 

cp $HOSTAPDCONF".backup" $HOSTAPDCONF
rm $HOSTAPDCONF".backup"

cp $DHCPCONF".backup" $DHCPCONF
rm $DHCPCONF".backup"

cp $DNSMASQCONF".backup" $DNSMASQCONF
rm $DNSMASQCONF".backup"

echo "Uninstall nginx"
systemctl stop nginx.service
systemctl disable nginx.service
sed $NGINXDEFAULT -i -e "s?root $OTCAMERA/webfiles?root /var/www/html?g"
apt remove nginx -y

echo "Remove OTCamera directory"
cd $OTCAMERA
pip uninstall -r requirements.txt -y
cd $USER_HOME
rm -rf $OTCAMERA

echo "#### Uninstall packages"
apt remove python3-pip

echo "Undo power saving variables"
sed $RCLOCAL -i -e "/exit 0/i /usr/bin/tvservice -o"
sed $RCLOCAL -i -e "/exit 0/i /sbin/iw dev wlan0 set power_save off"

echo "Uninstalling GL Legacy Drivers"
sed $CONFIG -i -e "s/^#dtoverlay=vc4-kms-v3d/dtoverlay=vc4-kms-v3d/g"
sed $CONFIG -i -e "s/^#dtoverlay=vc4-fkms-v3d/dtoverlay=vc4-fkms-v3d/g"
apt remove gldriver-test libgl1-mesa-dri

echo "    Undo OTCamera specific config variables"
sed -i '/# OTCamera/Q' $CONFIG 
sed $CONFIG -i -e "s/^#dtparam=audio=on/dtparam=audio=on/g"
sed $CONFIG -i -e "s/^#display_auto_detect=1/display_auto_detect=1/g"

echo "Disable I2C bus for hwclock"
raspi-config nonint do_i2c 1

systemctl daemon-reload

echo "#########"
echo "Done. Please reboot to finalise uninstall."
echo "#########"
