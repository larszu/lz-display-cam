#!/bin/bash
# Baut LZDisplayCam.ofx.bundle (macOS, universal). Braucht Xcode-Kommandozeilenwerkzeuge und ein installiertes Resolve (OpenFX-SDK).
set -e
cd "$(dirname "$0")"
SDK="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/OpenFX"
python3 gen.py
B=build; rm -rf "$B"; mkdir -p "$B"
FL=(-std=c++17 -O2 -fvisibility=hidden -arch arm64 -arch x86_64 -mmacosx-version-min=11.0 -I"$SDK/OpenFX-1.4/include" -I"$SDK/Support/include" -I. -Wno-deprecated-declarations)
for f in ofxsCore ofxsImageEffect ofxsInteract ofxsLog ofxsMultiThread ofxsParams ofxsProperty ofxsPropertyValidation; do
  clang++ "${FL[@]}" -c "$SDK/Support/Library/$f.cpp" -o "$B/$f.o" &
done
clang++ "${FL[@]}" -c LZDisplayCam.cpp -o "$B/LZDisplayCam.o" &
clang++ "${FL[@]}" -c CpuKernel.cpp -o "$B/CpuKernel.o" &
clang++ "${FL[@]}" -c MetalKernel.mm -o "$B/MetalKernel.o" &
wait
OUT="$B/LZDisplayCam.ofx.bundle/Contents"
mkdir -p "$OUT/MacOS"
clang++ "$B"/*.o -o "$OUT/MacOS/LZDisplayCam.ofx" -bundle -fvisibility=hidden -arch arm64 -arch x86_64 -mmacosx-version-min=11.0 -framework Metal -framework AppKit
cat > "$OUT/Info.plist" <<'P'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>LZDisplayCam.ofx</string>
<key>CFBundleIdentifier</key><string>de.zumpelars.DisplayCam</string>
<key>CFBundleName</key><string>LZ Display Cam</string>
<key>CFBundlePackageType</key><string>BNDL</string>
<key>CFBundleShortVersionString</key><string>1.1</string>
<key>CFBundleVersion</key><string>1.1</string>
</dict></plist>
P
codesign --force --sign - "$B/LZDisplayCam.ofx.bundle" 2>/dev/null || true
echo "Gebaut: $PWD/$B/LZDisplayCam.ofx.bundle"
