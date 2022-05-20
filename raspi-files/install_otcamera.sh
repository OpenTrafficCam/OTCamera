#!/bin/bash


APNAME="OTCamera"
APPASSWORD="onetwothree4"
APCHANNEL="11"
IPRANGE="10.10.50"
BRANCH="raspi-files"

# read -p "Press enter to continue..." key
echo "#### Configure Rasperry Pi"
echo "Configure legacy camera mode using raspi-config"
raspi-config nonint do_legacy 0

# read -p "Press enter to continue..." key
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

# read -p "Press enter to continue..." key
echo "    Installing GL Legacy Drivers"
apt install gldriver-test libgl1-mesa-dri -y
sed $CONFIG -i -e "s/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/g"
sed $CONFIG -i -e "s/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/g"

# read -p "Press enter to continue..." key
echo "    Setting power safing variables"
RCLOCAL="/etc/rc.local"
sed $RCLOCAL -i -e "/exit 0/i /usr/bin/tvservice -o"
sed $RCLOCAL -i -e "/exit 0/i /sbin/iw dev wlan0 set power_save off"


# read -p "Press enter to continue..." key
echo "#### Setting up OTCamera"

echo "    Installing packages"
apt install python3-pip git -y

# read -p "Press enter to continue..." key
echo "    Cloning OTCamera"
git clone --depth 1 --branch $BRANCH https://github.com/OpenTrafficCam/OTCamera.git
cd OTCamera
pip install -r requirements.txt --upgrade

# read -p "Press enter to continue..." key
echo "    Installing nginx"
apt install nginx -y
PWD=$(pwd)
NGINXDEFAULT="/etc/nginx/sites-available/default"
sed $NGINXDEFAULT -i -e "s?root /var/www/html?root $PWD/webfiles?g"
sudo systemctl restart nginx.service

# read -p "Press enter to continue..." key
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
echo "channel=$APCHANNEL" >> $HOSTAPDCONF
echo "ssid=$APNAME" >> $HOSTAPDCONF
echo "wpa_passphrase=$APPASSWORD" >> $HOSTAPDCONF
echo "interface=uap0" >> $HOSTAPDCONF
echo "hw_mode=g" >> $HOSTAPDCONF
echo "macaddr_acl=0" >> $HOSTAPDCONF
echo "auth_algs=1" >> $HOSTAPDCONF
echo "wpa=2" >> $HOSTAPDCONF
echo "wpa_key_mgmt=WPA-PSK" >> $HOSTAPDCONF
echo "wpa_pairwise=TKIP" >> $HOSTAPDCONF
echo "rsn_pairwise=CCMP" >> $HOSTAPDCONF
echo "country_code=DE" >> $HOSTAPDCONF
# echo "ctrl_interface=/var/run/hostapd" >> $HOSTAPDCONF
# echo "ctrl_interface_group=0" >> $HOSTAPDCONF
# echo "ieee80211d=1" >> $HOSTAPDCONF
# echo "beacon_int=100" >> $HOSTAPDCONF

# read -p "Press enter to continue..." key
echo "    Configure DHCPCD"
DHCPDCONF="/etc/dhcpcd.conf"
cp $DHCPDCONF $DHCPDCONF".backup"
echo "Current DHCPCD config moved to $DHCPDCONF.backup"
echo "interface uap0" >> $DHCPDCONF
echo "	static ip_address=$IPRANGE.1/24" >> $DHCPDCONF
echo "	nohook wpa_supplicant" >> $DHCPDCONF
echo "done"

# read -p "Press enter to continue..." key
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
echo "dhcp-range=$IPRANGE.10,$IPRANGE.250,2h" >> $DNSMASQCONF
echo "done"

# read -p "Press enter to continue..." key
echo "Unmask hostapd.service"
systemctl unmask hostapd.service

# read -p "Press enter to continue..." key
echo "Disabling Services"
systemctl disable hostapd.service
systemctl disable dhcpcd.service
systemctl disable dnsmasq.service


# read -p "Press enter to continue..." key
echo "    Enable Wifi AP at boot"
RCLOCAL="/etc/rc.local"
cp ./raspi-files/usr/local/bin/wifistart /usr/local/bin/wifistart
sed $RCLOCAL -i -e "/exit 0/i /bin/bash /usr/local/bin/wifistart"


echo "    Activate OTCamera service"
OTCSERVICE="./raspi-files/otcamera.service"
PWD=$(pwd)
sed $OTCSERVICE -i -e "s?^WorkingDirectory=/path/to/otcamera?WorkingDirectory=$PWD?g"
sed $OTCSERVICE -i -e "s?^User=username?User=$USER?g"
cp $OTCSERVICE /lib/systemd/system

systemctl enable otcamera.service

# TODO

# echo 'Setting Time"
# sudo hwclock -w
# sudo hwclock -r

# echo "#########"
# echo "Done. You need to reboot now and should see the new wifi $APNAME"
# echo "#########"
