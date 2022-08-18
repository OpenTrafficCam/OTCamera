#!/bin/bash

echo "OTCamera Installation Script"
echo "############################"
echo " "

read -r -e -p "Wifi SSID: " -i "OTCamera" APNAME
read -r -e -p "Wifi password: " -i "onetwothree4" APPASSWORD
read -r -e -p "Wifi channel: " -i 11 APCHANNEL
read -r -e -p "Wifi ip range: " -i 10.10.50 IPRANGE
read -r -e -p "Version to install [latest or tag]: " -i "latest" OTC_VERSION
read -r -e -p "Use DS3231 RTC? [y/n]: " -i "y" USE_RTC
read -r -e -p "Use Buttons? [y/n]: " -i "y" USE_BUTTONS
read -r -e -p "Use LEDs? [y/n]: " -i "y" USE_LEDS
read -r -e -p "Activate DEBUG mode? [y/n]: " -i "n" USE_DEBUG
read -r -e -p "Use relay server? [y/n]: " -i "n" USE_RELAY




echo "#### Configure Rasperry Pi"
echo "Configure legacy camera mode using raspi-config"
raspi-config nonint do_legacy 0
case $USE_RTC in 
    [yY] | [yY][eE][sS])
        echo "Enable I2C bus for hwclock"
        raspi-config nonint do_i2c 0
        ;;
esac

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
    echo "gpio=17,22,16,27,26=ip"
    echo "gpio=22,16,27=pu"
    echo "gpio=17,26=pd"
    echo "gpio=6,12,13=op"
    echo "gpio=6,12=dl"
    echo "gpio=13=dh"
} >> $CONFIG
sed $CONFIG -i -e "s/^dtparam=audio=on/#dtparam=audio=on/g"
sed $CONFIG -i -e "s/^display_auto_detect=1/#display_auto_detect=1/g"

echo "    Installing GL Legacy Drivers"
apt install gldriver-test libgl1-mesa-dri -y
sed $CONFIG -i -e "s/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/g"
sed $CONFIG -i -e "s/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/g"

echo "    Setting power safing variables"
RCLOCAL="/etc/rc.local"
sed $RCLOCAL -i -e "/^exit 0/i /usr/bin/tvservice -o"

echo "#### Setting up OTCamera"

echo "    Installing packages"
apt install python3-pip -y

if [ "$OTC_VERSION" = "latest" ]
then
    latest_tag=$(curl -s https://api.github.com/repos/OpenTrafficCam/OTCamera/releases/latest | sed -Ene '/^ *"tag_name": *"(v.+)",$/s//\1/p')
else
    latest_tag=$OTC_VERSION
fi
PWD=$(pwd)

echo "     Downloading OTCamera version $latest_tag"
curl -JL https://github.com/OpenTrafficCam/OTCamera/archive/"$latest_tag".tar.gz --output "$PWD"/otcamera.tar.gz
runuser -l "$SUDO_USER" -c "mkdir $PWD/OTCamera"
runuser -l "$SUDO_USER" -c "tar -xvzf $PWD/otcamera.tar.gz -C $PWD/OTCamera/ --strip-components=1"
rm "$PWD"/otcamera.tar.gz

cd OTCamera || { echo "Error: Cannot find OTCamera directory"; exit 1; }
pip install -r requirements.txt --upgrade

echo "    Installing nginx"
apt install nginx -y
PWD=$(pwd)
NGINXDEFAULT="/etc/nginx/sites-available/default"
sed $NGINXDEFAULT -i -e "s?root /var/www/html?root $PWD/webfiles?g"
systemctl restart nginx.service

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

echo "Unmask hostapd.service"
systemctl unmask hostapd.service

echo "Disabling Services"
systemctl disable hostapd.service
systemctl disable dhcpcd.service
systemctl disable dnsmasq.service


echo "    Enable Wifi AP at boot"
RCLOCAL="/etc/rc.local"
cp ./raspi-files/usr/local/bin/wifistart /usr/local/bin/wifistart
sed $RCLOCAL -i -e "/^exit 0/i /bin/bash /usr/local/bin/wifistart"

case $USE_RTC in 
    [yY] | [yY][eE][sS])
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
        ;;
esac


OTCONFIG="$PWD/OTCamera/config.py"

case $USE_BUTTONS in
    [yY] | [yY][eE][sS])
        echo "Enableing buttons"
        sed "$OTCONFIG" -i -e "s?^USE_BUTTONS.*?USE_BUTTONS = True?g"
        ;;
    [nN] | [nN][oO])
        echo "Disableing buttons"
        sed "$OTCONFIG" -i -e "s?^USE_BUTTONS.*?USE_BUTTONS = False?g"
        ;;
esac

case $USE_LEDS in
    [yY] | [yY][eE][sS])
        echo "Enableing LEDs"
        sed "$OTCONFIG" -i -e "s?^USE_LED.*?USE_LED = True?g"
        ;;
    [nN] | [nN][oO])
        echo "Disableing LEDs"
        sed "$OTCONFIG" -i -e "s?^USE_LED.*?USE_LED = False?g"
        ;;
esac

case $USE_DEBUG in
    [yY] | [yY][eE][sS])
        echo "Enableing debug mode"
        sed "$OTCONFIG" -i -e "s?^DEBUG_MODE_ON.*?DEBUG_MODE_ON = True?g"
        ;;
    [nN] | [nN][oO])
        echo "Disableing debug mode"
        sed "$OTCONFIG" -i -e "s?^DEBUG_MODE_ON.*?DEBUG_MODE_ON = False?g"
        ;;
esac

case $USE_RELAY in
    [yY] | [yY][eE][sS])
        echo "Enableing relay mode"
        sed "$OTCONFIG" -i -e "s?^USE_RELAY.*?USE_RELAY = True?g"
        bash ./raspi-files/install_sshrelay.sh
        ;;
    [nN] | [nN][oO])
        echo "Disableing debug mode"
        sed "$OTCONFIG" -i -e "s?^USE_RELAY.*?USE_RELAY = False?g"
        ;;
esac


echo "    Activate OTCamera service"
OTCSERVICE="./raspi-files/otcamera.service"
cp $OTCSERVICE /lib/systemd/system
OTCSERVICE="/lib/systemd/system/otcamera.service"
PWD=$(pwd)
sed $OTCSERVICE -i -e "s?^WorkingDirectory=/path/to/otcamera?WorkingDirectory=$PWD?g"
sed $OTCSERVICE -i -e "s?^User=username?User=$SUDO_USER?g"

systemctl daemon-reload
systemctl enable otcamera.service

echo "#########"
echo "Done. You need to reboot now and should see the new wifi $APNAME"
echo "#########"
