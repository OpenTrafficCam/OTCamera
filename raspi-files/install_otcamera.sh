#!/bin/bash


APNAME="OTCamera"
APPASSWORD="onetwothree4"
APCHANNEL="11"
IPRANGE="10.10.10"
BRANCH="first-version"

read -p "Press any key to continue...\n" key
echo "#### Configure Rasperry Pi"
echo "Configure legacy camera mode using raspi-config"
raspi-config nonint do_legacy 0

read -p "Press any key to continue...\n" key
echo "    Setting $CONFIG variables"
CONFIG="/boot/config.txt"
echo "# OTCamera" >> $CONFIG
echo "dtoverlay=disable-bt" >> $CONFIG
echo "disable_camera_led=1" >> $CONFIG
echo "dtparam=act_led_trigger=none" >> $CONFIG
echo "dtparam=act_led_activelow=on" >> $CONFIG
sed $CONFIG -i -e "s/^dtparam=audio=on/#dtparam=audio=on/g"
echo "dtparam=audio=off" >> $CONFIG
sed $CONFIG -i -e "s/^display_auto_detect=1/#display_auto_detect=1/g"
echo "display_auto_detect=0" >> $CONFIG

read -p "Press any key to continue...\n" key
echo "    Installing GL Legacy Drivers"
apt install gldriver-test libgl1-mesa-dri -y
sed $CONFIG -i -e "s/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/g"
sed $CONFIG -i -e "s/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/g"

read -p "Press any key to continue...\n" key
echo "    Setting power safing variables"
RCLOCAL="/etc/rc.local"
sed $RCLOCAL -i -e "/exit 0/i /usr/bin/tvservice -o"
sed $RCLOCAL -i -e "/exit 0/i /sbin/iw dev wlan0 set power_save off"


read -p "Press any key to continue...\n" key
echo "#### Setting up OTCamera"

echo "    Installing packages"
apt install python3-pip git -y

read -p "Press any key to continue...\n" key
echo "    Cloning OTCamera"
git clone --branch $BRANCH https://github.com/OpenTrafficCam/OTCamera.git
cd OTCamera
pip install -r requirements.txt --upgrade

read -p "Press any key to continue...\n" key
echo "    Installing nginx"
apt install nginx -y
PWD=$(pwd)
NGINXDEFAULT="/etc/nginx/sites-available/default"
sed $NGINXDEFAULT -i -e "s?root /var/www/html?root $PWD/webfiles?g"


read -p "Press any key to continue...\n" key
echo "     Configure wifi access-point"

echo "     Installing servies"
sudo apt install hostapd dnsmasq dhcpcd -y

echo "Configure hostapd"
HOSTAPD="/etc/default/hostapd"
HOSTAPDCONF="/etc/hostapd/hostapd.conf"
cp $HOSTAPD $HOSTAPD".backup"
echo "    Current hostapd config moved to $HOSTAPD.backup"
echo "DAEMON_CONF=\""$HOSTAPDCONF"\"" >> $HOSTAPD

cp $HOSTAPDCONF $HOSTAPDCONF".backup"
echo "    Current hostapd config moved to $HOSTAPDCONF.backup"
echo "country_code=DE" >> $HOSTAPDCONF
echo "interface=uap0" >> $HOSTAPDCONF
echo "ctrl_interface=/var/run/hostapd" >> $HOSTAPDCONF
echo "ctrl_interface_group=0" >> $HOSTAPDCONF
echo "ssid=$APNAME" >> $HOSTAPDCONF
echo "hw_mode=g" >> $HOSTAPDCONF
echo "channel=$APCHANNEL" >> $HOSTAPDCONF
echo "ieee80211d=1" >> $HOSTAPDCONF
echo "auth_algs=1" >> $HOSTAPDCONF
echo "wpa=2" >> $HOSTAPDCONF
echo "wpa_key_mgmt=WPA-PSK" >> $HOSTAPDCONF
echo "wpa_pairwise=TKIP" >> $HOSTAPDCONF
echo "rsn_pairwise=CCMP" >> $HOSTAPDCONF
echo "wpa_passphrase=$APPASSWORD" >> $HOSTAPDCONF
echo "beacon_int=100" >> $HOSTAPDCONF

read -p "Press any key to continue...\n" key
echo "    Configure DHCPCD"
DHCPDCONF="/etc/dhcpcd.conf"
cp $DHCPDCONF $DHCPDCONF".backup"
echo "Current DHCPCD config moved to $DHCPDCONF.backup"
echo "interface uap0" >> $DHCPDCONF
echo "    static ip_address=$IPRANGE.1/24" >> $DHCPDCONF
echo "    nohook wpa_supplicant" >> $DHCPDCONF
echo "done"

read -p "Press any key to continue...\n" key
echo "    Configure DNSMASQ"
DNSMASQCONF="/etc/dnsmasq.conf"
mv $DNSMASQCONF $DNSMASQCONF".backup"
echo "    Current DNSMASQ config moved to $DNSMASQCONF.backup"
echo "interface=lo,uap0" >> $DNSMASQCONF
echo "no-dhcp-interface=lo,wlan0" >> $DNSMASQCONF
echo "bind-interfaces" >> $DNSMASQCONF
echo "server=$IPRANGE.1" >> $DNSMASQCONF
echo "domain-needed" >> $DNSMASQCONF
echo "bogus-priv" >> $DNSMASQCONF
echo "dhcp-range=$IPRANGE.10,$IPRANGE.250,255.255.255.0,2h" >> $DNSMASQCONF
echo "done"

read -p "Press any key to continue...\n" key
echo "Unmask hostapd.service"
systemctl unmask hostapd.service

read -p "Press any key to continue...\n" key
echo "Disabling Services"
systemctl disable hostapd.service
systemctl disable dhcpcd.service
systemctl disable dnsmasq.service


read -p "Press any key to continue...\n" key
echo "    Enable Wifi AP at boot"
RCLOCAL="/etc/rc.local"
sed $RCLOCAL -i -e "/exit 0/i iw dev uap0 del"
sed $RCLOCAL -i -e "/exit 0/i iw dev wlan0 interface add uap0 type __ap"
sed $RCLOCAL -i -e "/exit 0/i ifconfig uap0 up"
sed $RCLOCAL -i -e "/exit 0/i systemctl start hostapd.service"
sed $RCLOCAL -i -e "/exit 0/i sleep 10"
sed $RCLOCAL -i -e "/exit 0/i systemctl start dhcpcd.service"
sed $RCLOCAL -i -e "/exit 0/i sleep 5"
sed $RCLOCAL -i -e "/exit 0/i systemctl start dnsmasq.service"


echo "#### Done ####"
read -p "Press any key to continue...\n" key
sleep 10
echo "rebooting..."
sleep 2
read -p "Press any key to continue...\n" key
sudo reboot


# echo 'Setting Time"
# sudo hwclock -w
# sudo hwclock -r

# sleep 1


# echo 'Change Wifi name"
# sudo nano /etc/hostapd/hostapd.conf

# sleep 1

# echo 'Change hostname"
# sudo raspi-config
# # sudo raspi-config nonint do_hostname QuerCam

# sleep 1



# read -p "Dateien aktualisieren [Enter]" val

# echo 'Dienst aktivieren"
# sudo systemctl enable QuerCam.service

# echo 'neustart"

# sleep 2

# sudo reboot
