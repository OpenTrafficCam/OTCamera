#! /usr/bin/bash

echo Hello World

read -p "Enter a name for the accesspoint: " HOTSPOTNAME
read -p "Enter a new passphrase for the accesspoint: " PASSPHRASE
read -p "Enter a new IP-address for the accespoint (like 10.0.0.5) :" IPADRESS

sed -i 's/^ssid=.*/ssid='$HOTSPOTNAME'/g' /etc/hostapd/hostapd.conf
sed -i 's/wpa_passphrase=.*/wpa_passphrase='$PASSPHRASE'/g' /etc/hostapd/hostapd.conf
sed -i 's/    ip a add [0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*/    ip a add '$IPADRESS'/g' /usr/bin/autohotspot    
sed -i 's/        <title>\w*/        <title>'$HOTSPOTNAME'/g' /home/admin/OTCamera/webfiles/index.html    
sed -i 's/        <h1>\w*/        <h1>'$HOTSPOTNAME'/g' /home/admin/OTCamera/webfiles/index.html  

