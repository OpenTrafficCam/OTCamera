#!/bin/bash

echo "OTCamera Installation Script"
echo "############################"
echo " "

read -r -e -p "Wifi SSID: " -i "OTCamera" APNAME
read -r -e -p "Wifi password: " -i "onetwothree4" APPASSWORD
read -r -e -p "Wifi channel: " -i 11 APCHANNEL
read -r -e -p "Wifi ip range: " -i 10.10.50 IPRANGE
read -r -e -p "OTCamera branch: " -i "master" BRANCH

# APNAME="OTCamera"
# APPASSWORD="onetwothree4"
# APCHANNEL="11"
# IPRANGE="10.10.50"
# BRANCH="raspi-files"

# read -p "Press enter to continue..." key
echo "#### Configure Rasperry Pi"
echo "Configure legacy camera mode using raspi-config"
raspi-config nonint do_legacy 0
echo "Enable I2C bus for hwclock"
raspi-config nonint do_i2c 0

# read -p "Press enter to continue..." key
echo "    Setting config variables"
CONFIG="/boot/config.txt"
{
    echo "# OTCamera"
    echo "dtoverlay=disable-bt"
    echo "disable_camera_led=1"
    echo "dtparam=act_led_trigger=none"
    echo "dtparam=act_led_activelow=on"
    echo "dtparam=audio=off"
    echo "display_auto_detect=0"
    echo "gpio=6,16,18,19=ip"
    echo "gpio=16,18,19=pu"
    echo "gpio=6=pd"
    echo "gpio=5,12,13=op"
    echo "gpio=5,12=dl"
    echo "gpio=13=dh"
} >> $CONFIG
sed $CONFIG -i -e "s/^dtparam=audio=on/#dtparam=audio=on/g"
sed $CONFIG -i -e "s/^display_auto_detect=1/#display_auto_detect=1/g"

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
runuser -l $SUDO_USER -c "git clone --depth 1 --branch $BRANCH https://github.com/OpenTrafficCam/OTCamera.git"
cd OTCamera || { echo "Error: Cannot find OTCamera directory"; exit 1; }
runuser -l $SUDO_USER -c "git config pull.rebase false"
pip install -r requirements.txt --upgrade

# read -p "Press enter to continue..." key
echo "    Installing nginx"
apt install nginx -y
PWD=$(pwd)
NGINXDEFAULT="/etc/nginx/sites-available/default"
sed $NGINXDEFAULT -i -e "s?root /var/www/html?root $PWD/webfiles?g"
systemctl restart nginx.service

# read -p "Press enter to continue..." key
echo "     Configure wifi access-point"

echo "     Installing servies"
apt install hostapd dnsmasq dhcpcd -y

echo "Configure hostapd"
HOSTAPD="/etc/default/hostapd"
HOSTAPDCONF="/etc/hostapd/hostapd.conf"
cp $HOSTAPD $HOSTAPD".backup"
echo "    Current hostapd config moved to $HOSTAPD.backup"
echo "DAEMON_CONF=\"$HOSTAPDCONF\"" >> $HOSTAPD

cp $HOSTAPDCONF $HOSTAPDCONF".backup"
echo "    Current hostapd config moved to $HOSTAPDCONF.backup"
{
    echo "channel=$APCHANNEL"
    echo "ssid=$APNAME"
    echo "wpa_passphrase=$APPASSWORD"
    echo "interface=uap0"
    echo "hw_mode=g"
    echo "macaddr_acl=0"
    echo "auth_algs=1"
    echo "wpa=2"
    echo "wpa_key_mgmt=WPA-PSK"
    echo "wpa_pairwise=TKIP"
    echo "rsn_pairwise=CCMP"
    echo "country_code=DE"
} >> $HOSTAPDCONF
# echo "ctrl_interface=/var/run/hostapd" >> $HOSTAPDCONF
# echo "ctrl_interface_group=0" >> $HOSTAPDCONF
# echo "ieee80211d=1" >> $HOSTAPDCONF
# echo "beacon_int=100" >> $HOSTAPDCONF

# read -p "Press enter to continue..." key
echo "    Configure DHCPCD"
DHCPDCONF="/etc/dhcpcd.conf"
cp $DHCPDCONF $DHCPDCONF".backup"
echo "Current DHCPCD config moved to $DHCPDCONF.backup"
{
    echo "interface uap0"
    echo "	static ip_address=$IPRANGE.1/24"
    echo "	nohook wpa_supplicant"
} >> $DHCPDCONF
echo "done"

# read -p "Press enter to continue..." key
echo "    Configure DNSMASQ"
DNSMASQCONF="/etc/dnsmasq.conf"
mv $DNSMASQCONF $DNSMASQCONF".backup"
echo "    Current DNSMASQ config moved to $DNSMASQCONF.backup"
{
    echo "interface=lo,uap0"
    echo "no-dhcp-interface=lo,wlan0"
    echo "bind-interfaces"
    echo "server=$IPRANGE.1"
    echo "domain-needed"
    echo "bogus-priv"
    echo "dhcp-range=$IPRANGE.10,$IPRANGE.250,2h"
} >> $DNSMASQCONF
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


echo "    Setting up RTC"
HWCLOCK="/lib/udev/hwclock-set"
apt install i2c-tools -y
echo "dtoverlay=i2c-rtc,ds3231" >> $CONFIG
apt remove fake-hwclock -y
update-rc.d -f fake-hwclock remove
systemctl disable fake-hwclock
sed $HWCLOCK -i -e "/if.*systemd/ s/^#*/#/"
sed $HWCLOCK -i -e "s?^    exit 0?#    exit 0?g"
sed $HWCLOCK -i -e "s?^fi?#fi?g"
sed $HWCLOCK -i -e "/--systz/ s/^#*/#/"


echo "    Activate OTCamera service"
OTCSERVICE="./raspi-files/otcamera.service"
PWD=$(pwd)
sed $OTCSERVICE -i -e "s?^WorkingDirectory=/path/to/otcamera?WorkingDirectory=$PWD?g"
sed $OTCSERVICE -i -e "s?^User=username?User=$SUDO_USER?g"
cp $OTCSERVICE /lib/systemd/system

systemctl enable otcamera.service

echo "#########"
echo "Done. You need to reboot now and should see the new wifi $APNAME"
echo "#########"
