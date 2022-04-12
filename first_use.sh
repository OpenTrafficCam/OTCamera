#! /usr/bin/bash

read -p "Change accespointname? Y/N " ANSWER
case "$ANSWER" in 
        [yY] | [yY][eE][sS])
        read -p "Enter a name for the accesspoint: " HOTSPOTNAME
        sed -i 's/^ssid=.*/ssid='$HOTSPOTNAME'/g' /etc/hostapd/hostapd.conf
        sed -i 's/        <title>\w*/        <title>'$HOTSPOTNAME'/g' /home/pi/OTCamera/webfiles/index.html    
        sed -i 's/        <h1>\w*/        <h1>'$HOTSPOTNAME'/g' /home/pi/OTCamera/webfiles/index.html  
        ;;
        [nN] | [oO]) 
        ;;
esac
read -p "Change accespointpasswort? Y/N " ANSWER
case "$ANSWER" in 
        [yY] | [yY][eE][sS])
        read -p "Enter a name for the accesspointpassword: " PASSPHRASE
        sed -i 's/wpa_passphrase=.*/wpa_passphrase='$PASSPHRASE'/g' /etc/hostapd/hostapd.conf
        ;;
        [nN] | [oO]) 
        ;;
esac
read -p "Change IP of the accesspoint? Y/N " ANSWER
case "$ANSWER" in 
        [yY] | [yY][eE][sS])
        read -p "Enter a new IP-address for the accespoint (like 10.0.0.5) :" IPADRESS
        sed -i 's/    ip a add [0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*/    ip a add '$IPADRESS'/g' /usr/bin/autohotspot   
        ;;
        [nN] | [oO]) 
        ;;
esac 
read -p "Change hostname of raspberry? Y/N " ANSWER
case "$ANSWER" in 
        [yY] | [yY][eE][sS])
        read -p "Enter a new hostname (annotation of video/access in wlan-mode) :" NEWHOSTNAME
        OLDHOSTNAME=$(hostname)
        sed -i 's/'$OLDHOSTNAME'/'$NEWHOSTNAME'/g' /etc/hosts
        hostname -b $NEWHOSTNAME
        sed -i 's/.*/'$NEWHOSTNAME'/g' /etc/hostname    
        ;;
        [nN] | [oO]) 
        ;;
esac 
