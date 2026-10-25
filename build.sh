#!/bin/bash
# Installs Delphi: builds Delphi.app, starts it at login, and (re)starts it now. Run it again after any change.
set -e; cd "$(dirname "$0")"
VERSION=$(tr -d '\n' < VERSION)
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid VERSION: $VERSION"; exit 1; }
IFS=. read -r VERSION_MAJOR VERSION_MINOR VERSION_PATCH <<< "$VERSION"
(( VERSION_MINOR < 1000 && VERSION_PATCH < 1000 )) || { echo "VERSION components must be below 1000"; exit 1; }
BUILD=$((VERSION_MAJOR * 1000000 + VERSION_MINOR * 1000 + VERSION_PATCH))
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 26 ] || { echo "Delphi needs macOS 26 or later (it uses Apple's new on-device speech)."; exit 1; }
xcode-select -p >/dev/null 2>&1 || { echo "Needs Apple's command line tools. Run: xcode-select --install   then run ./build.sh again."; exit 1; }
command -v python3 >/dev/null || { echo "Delphi needs Python 3. Install it, then run ./build.sh again."; exit 1; }
command -v claude >/dev/null || [ -x ~/.local/bin/claude ] || echo "Note: Claude Code is not installed yet. Delphi's setup window can install it, or you can pick Devin or Pi."
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
# A compiler error must leave the installed app and its resources alone.
swiftc -O -target "$(uname -m)-apple-macos26.0" Delphi.swift -o "$STAGE/Delphi"
APP=~/Applications/Delphi.app   # in Applications so System Settings can list it for permissions
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/ui"
cp delphi.py "$APP/Contents/Resources/"
cp ui/*.html ui/*.js "$APP/Contents/Resources/ui/"
cp ui/AppIcon.icns "$APP/Contents/Resources/"
cat > "$APP/Contents/Info.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.delphi.app</string>
<key>CFBundleName</key><string>Delphi</string>
<key>CFBundleExecutable</key><string>Delphi</string>
<key>CFBundleVersion</key><string>$BUILD</string>
<key>CFBundleShortVersionString</key><string>$VERSION</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
<key>DelphiSource</key><string>$(pwd)</string>
<key>LSUIElement</key><true/>
<key>NSMicrophoneUsageDescription</key><string>Delphi listens when you use its shortcut or microphone button.</string>
<key>NSAppleEventsUsageDescription</key><string>Delphi controls apps like Finder, Chrome and Music when you ask it to.</string>
<key>NSCalendarsFullAccessUsageDescription</key><string>Delphi reads your calendar, adds events you request, and asks before moving or deleting existing events. Calendar details are sent to your chosen AI model.</string>
<key>NSSpeechRecognitionUsageDescription</key><string>Delphi turns your words into text on this Mac.</string>
</dict></plist>
P
mv "$STAGE/Delphi" "$APP/Contents/MacOS/Delphi"
# With a code-signing identity named "Delphi Local Signing" in the keychain, macOS keeps permissions across
# rebuilds and auto-updates; ad hoc signing would ask for every permission again after each one. So make it once.
ID=$(security find-identity -p codesigning | awk '/Delphi Local Signing/{print $2; exit}')
if [ -z "$ID" ]; then
  K=$(mktemp -d)
  /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 7300 -subj "/CN=Delphi Local Signing" -addext "extendedKeyUsage=critical,codeSigning" \
    -addext "keyUsage=critical,digitalSignature" -keyout "$K/k.pem" -out "$K/c.pem" 2>/dev/null &&
  /usr/bin/openssl pkcs12 -export -inkey "$K/k.pem" -in "$K/c.pem" -out "$K/a.p12" -passout pass:delphi 2>/dev/null &&
  security import "$K/a.p12" -P delphi -T /usr/bin/codesign >/dev/null 2>&1 || true   # fails quietly: ad hoc still works
  rm -rf "$K"
  ID=$(security find-identity -p codesigning | awk '/Delphi Local Signing/{print $2; exit}')
fi
codesign -s "${ID:--}" --force "$APP"
# register with macOS, or System Settings can't list it for permissions
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
AGENT=~/Library/LaunchAgents/com.delphi.app.plist   # starts at login, restarts if it crashes (Quit stays quit)
# Delphi was called Atticus: keep its settings, chat, rules and history.
[ -d ~/.config/atticus ] && [ ! -e ~/.config/delphi ] && mv ~/.config/atticus ~/.config/delphi
mkdir -p ~/Library/LaunchAgents ~/.config/delphi
cat > "$AGENT" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.delphi.app</string>
<key>ProgramArguments</key><array><string>$APP/Contents/MacOS/Delphi</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
<key>StandardErrorPath</key><string>$HOME/.config/delphi/app.err</string>
</dict></plist>
P
[ -n "$DELPHI_NO_RESTART" ] && exit 0   # the app's own updater restarts it when idle
# Reload the job so launchd refreshes its executable signing requirement after a rebuild.
launchctl bootout gui/$(id -u)/com.delphi.app 2>/dev/null || true
pkill -f "$APP/Contents/MacOS/Delphi$" 2>/dev/null && sleep 1   # stop a copy opened by hand too
# bootout can return before the job has finished unloading.
launchctl bootstrap gui/$(id -u) "$AGENT" 2>/dev/null || { sleep 1; launchctl bootstrap gui/$(id -u) "$AGENT" 2>/dev/null || {
  echo "Could not add Delphi to Login Items; opening it directly instead."
  open "$APP"
}; }
# Retire the old Atticus app last: when its updater ran this script, stopping it can stop this script too.
if [ -e ~/Applications/Atticus.app ] || [ -e ~/Library/LaunchAgents/com.atticus.app.plist ]; then
  rm -rf ~/Applications/Atticus.app ~/Library/LaunchAgents/com.atticus.app.plist ~/Library/Caches/Atticus
  launchctl bootout gui/$(id -u)/com.atticus.app 2>/dev/null || true
  pkill -f "Atticus.app/Contents/MacOS/Atticus$" 2>/dev/null || true
fi
echo "Delphi is running. Hold Control+Option+Space and talk."
