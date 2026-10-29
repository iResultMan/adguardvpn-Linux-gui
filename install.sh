#!/bin/bash
# Installs AdGuard VPN GUI for the current user:
#   - the tray daemon (built with cargo when available, otherwise downloaded
#     from the GitHub release for this architecture and checked by SHA256)
#   - a venv with PyQt5 for the settings window
#   - application menu entry (opens the window) and autostart (runs the daemon)
# Requires: python3 with venv, adguardvpn-cli installed and signed in.
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"
REPO="iResultMan/adguardvpn-Linux-gui"

if ! command -v adguardvpn-cli >/dev/null 2>&1 && [ ! -x /opt/adguardvpn_cli/adguardvpn-cli ]; then
    echo "adguardvpn-cli not found. Install AdGuard VPN CLI first:"
    echo "  https://github.com/AdguardTeam/AdGuardVPNCLI"
    echo "(the window can also do it for you: run venv/bin/python AdGuard.py after this script)"
fi

echo "== Tray daemon"
mkdir -p bin
if command -v cargo >/dev/null 2>&1; then
    echo "Building daemon with cargo..."
    cargo build --release --manifest-path daemon/Cargo.toml
    cp daemon/target/release/adguardvpn-tray bin/adguardvpn-tray
else
    ARCH="$(uname -m)"
    case "$ARCH" in
        x86_64|aarch64) ;;
        *) echo "No prebuilt daemon for $ARCH; install cargo and rerun."; exit 1 ;;
    esac
    TAG="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)"
    [ -n "$TAG" ] || { echo "Cannot find the latest release; install cargo and rerun."; exit 1; }
    BASE="https://github.com/$REPO/releases/download/$TAG"
    echo "Downloading adguardvpn-tray $TAG for $ARCH..."
    curl -fsSL -o bin/adguardvpn-tray "$BASE/adguardvpn-tray-$ARCH"
    curl -fsSL -o bin/SHA256SUMS "$BASE/SHA256SUMS"
    EXPECTED="$(grep "adguardvpn-tray-$ARCH\$" bin/SHA256SUMS | cut -d' ' -f1)"
    ACTUAL="$(sha256sum bin/adguardvpn-tray | cut -d' ' -f1)"
    if [ -z "$EXPECTED" ] || [ "$EXPECTED" != "$ACTUAL" ]; then
        echo "Checksum mismatch for the downloaded daemon; refusing to install it."
        rm -f bin/adguardvpn-tray
        exit 1
    fi
    echo "Checksum OK."
fi
chmod +x bin/adguardvpn-tray
bin/adguardvpn-tray --version

echo "== Settings window"
python3 -m venv venv
venv/bin/pip install --upgrade pip >/dev/null
venv/bin/pip install -r requirements.txt
venv/bin/python tools/install_icons.py || echo "Icon install skipped (optional)."

echo "== Menu entry and autostart"
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"
cat <<DESKTOP > "$APP_DIR/adguard.desktop"
[Desktop Entry]
Type=Application
Name=AdGuard VPN
GenericName=VPN
Comment=AdGuard VPN settings window
Exec=$DIR/venv/bin/python $DIR/AdGuard.py
Icon=$DIR/assets/app_icon.png
Terminal=false
Categories=Network;VPN;Internet;Security;
Keywords=adguard;vpn;network;proxy;internet;
StartupNotify=true
StartupWMClass=AdGuard.py
DESKTOP
update-desktop-database "$APP_DIR" 2>/dev/null || true

# Autostart runs the daemon; the checkbox in the window can turn it off.
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat <<DESKTOP > "$AUTOSTART_DIR/adguard.desktop"
[Desktop Entry]
Type=Application
Name=AdGuard VPN
Comment=AdGuard VPN tray
Exec=$DIR/bin/adguardvpn-tray
Icon=$DIR/assets/app_icon.png
Terminal=false
Categories=Network;
X-GNOME-Autostart-enabled=true
Hidden=false
DESKTOP

# Older versions created a systemd user service for the window. Remove it.
if systemctl --user list-unit-files adguard.service >/dev/null 2>&1; then
    systemctl --user disable --now adguard.service 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/adguard.service"
    systemctl --user daemon-reload 2>/dev/null || true
fi

echo
echo "Installation complete."
echo "Start the tray now:   $DIR/bin/adguardvpn-tray &"
echo "Open the window:      $DIR/venv/bin/python $DIR/AdGuard.py"
echo "GNOME users: the tray icon needs the AppIndicator extension"
echo "  (package gnome-shell-extension-appindicator on Ubuntu/Debian/Fedora)."
