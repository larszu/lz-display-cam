#!/bin/bash
# Installiert das Plugin nach /Library/OFX/Plugins (fragt nach dem Mac-Passwort). Danach Resolve neu starten.
set -e
cd "$(dirname "$0")"
[ -d build/LZDisplayCam.ofx.bundle ] || ./build.sh
sudo mkdir -p /Library/OFX/Plugins
sudo rm -rf /Library/OFX/Plugins/LZDisplayCam.ofx.bundle
sudo cp -R build/LZDisplayCam.ofx.bundle /Library/OFX/Plugins/
echo "Installiert. Resolve neu starten: Effekte > OpenFX > LZ Medienproduktion > LZ Display Cam"
