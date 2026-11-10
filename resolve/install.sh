#!/bin/sh
# Kopiert die DCTL in den LUT-Ordner von DaVinci Resolve (macOS).
set -e
D="/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/LZ"
mkdir -p "$D"
cp "$(dirname "$0")/LZ_DisplayCam.dctl" "$D/"
echo "Installiert: $D/LZ_DisplayCam.dctl"
