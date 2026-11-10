#!/bin/bash
# Baut LZ-Display-Cam-<version>.pkg: OpenFX-Plugin nach /Library/OFX/Plugins, DCTL in den Resolve-LUT-Ordner.
#   installer/build-pkg.sh 1.1.0
set -e
cd "$(dirname "$0")/.."
V="${1:?Version angeben, z. B. 1.1.0}"
./ofx/build.sh >/dev/null
W=installer/build; rm -rf "$W"; mkdir -p "$W/root/Library/OFX/Plugins" "$W/root/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/LZ" "$W/scripts"
cp -R ofx/build/LZDisplayCam.ofx.bundle "$W/root/Library/OFX/Plugins/"
cp resolve/LZ_DisplayCam.dctl "$W/root/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/LZ/"
sed -i '' "s#<string>1.1</string>#<string>$V</string>#g" "$W/root/Library/OFX/Plugins/LZDisplayCam.ofx.bundle/Contents/Info.plist"
codesign --force --sign - "$W/root/Library/OFX/Plugins/LZDisplayCam.ofx.bundle"
cat > "$W/scripts/postinstall" <<'P'
#!/bin/sh
xattr -dr com.apple.quarantine "/Library/OFX/Plugins/LZDisplayCam.ofx.bundle" 2>/dev/null || true
exit 0
P
chmod +x "$W/scripts/postinstall"
pkgbuild --analyze --root "$W/root" "$W/comp.plist" >/dev/null
plutil -replace 0.BundleIsRelocatable -bool NO "$W/comp.plist"
pkgbuild --component-plist "$W/comp.plist" --root "$W/root" --scripts "$W/scripts" --identifier de.zumpelars.displaycam --version "$V" --install-location / "$W/component.pkg" >/dev/null
cat > "$W/distribution.xml" <<D
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>LZ Display Cam $V</title>
  <welcome file="welcome.html"/>
  <license file="LICENSE.txt"/>
  <options customize="never" require-scripts="false" hostArchitectures="arm64,x86_64"/>
  <domains enable_localSystem="true"/>
  <pkg-ref id="de.zumpelars.displaycam"/>
  <choices-outline><line choice="default"/></choices-outline>
  <choice id="default" title="LZ Display Cam"><pkg-ref id="de.zumpelars.displaycam"/></choice>
  <pkg-ref id="de.zumpelars.displaycam" version="$V" onConclusion="none">component.pkg</pkg-ref>
</installer-gui-script>
D
mkdir -p "$W/res"; cp LICENSE "$W/res/LICENSE.txt"
cat > "$W/res/welcome.html" <<H
<html><body style="font-family:-apple-system,Helvetica;font-size:13px">
<h2>LZ Display Cam $V</h2>
<p>Lässt eine Bildschirmaufnahme in DaVinci Resolve aussehen, als hätte eine Handkamera das Display abgefilmt.</p>
<p>Installiert wird:</p>
<ul><li>das OpenFX-Plugin nach <code>/Library/OFX/Plugins</code></li>
<li>die DCTL-Fassung in den LUT-Ordner von Resolve</li></ul>
<p>Danach DaVinci Resolve neu starten. Der Effekt liegt unter <b>Effekte &gt; OpenFX &gt; LZ Medienproduktion &gt; LZ Display Cam</b>.</p>
</body></html>
H
mkdir -p dist
productbuild --distribution "$W/distribution.xml" --resources "$W/res" --package-path "$W" "dist/LZ-Display-Cam-$V.pkg" >/dev/null
( cd "$W/root/Library/OFX/Plugins" && ditto -c -k --keepParent LZDisplayCam.ofx.bundle "$OLDPWD/dist/LZDisplayCam.ofx.bundle-$V.zip" )
cp resolve/LZ_DisplayCam.dctl "dist/LZ_DisplayCam-$V.dctl"
echo "dist/:"; ls -la dist
