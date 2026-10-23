#!/bin/bash
# Installs the AdGuard VPN GUI for the current user:
#   venv + PyQt5, application menu entry, icons, optional autostart entry.
# Requires: python3 (with venv), adguardvpn-cli already installed and logged in.
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

if ! command -v adguardvpn-cli >/dev/null 2>&1; then
    echo "adguardvpn-cli not found in PATH. Install AdGuard VPN CLI first:"
    echo "  https://github.com/AdguardTeam/AdGuardVPNCLI"
    exit 1
fi

echo "Creating virtual environment..."
python3 -m venv venv

echo "Installing requirements..."
venv/bin/pip install --upgrade pip >/dev/null
venv/bin/pip install -r requirements.txt

echo "Installing icons..."
venv/bin/python tools/install_icons.py || echo "Icon install skipped (optional)."

echo "Creating application menu entry..."
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"
cat <<DESKTOP > "$APP_DIR/adguard.desktop"
[Desktop Entry]
Type=Application
Name=AdGuard
GenericName=AdGuard VPN
Comment=AdGuard VPN Client
Exec=$DIR/venv/bin/python $DIR/AdGuard.py
Icon=$DIR/assets/app_icon.png
Terminal=false
Categories=Network;VPN;Internet;Security;
Keywords=adguard;vpn;network;proxy;internet;
StartupNotify=true
StartupWMClass=AdGuard.py
X-GNOME-UsesNotifications=true
DESKTOP
update-desktop-database "$APP_DIR" 2>/dev/null || true

# Autostart is a single desktop entry managed by the "Autostart" checkbox in
# the window. The installer enables it once; the checkbox can turn it off.
echo "Enabling autostart (can be disabled from the window)..."
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat <<DESKTOP > "$AUTOSTART_DIR/adguard.desktop"
[Desktop Entry]
Type=Application
Name=AdGuard
Comment=AdGuard VPN Client
Exec=$DIR/venv/bin/python $DIR/AdGuard.py --minimized
Icon=$DIR/assets/app_icon.png
Terminal=false
Categories=Network;
X-GNOME-Autostart-enabled=true
Hidden=false
DESKTOP

# Older versions of this installer also created a systemd user service that
# started a second copy of the GUI regardless of the checkbox. Remove it.
if systemctl --user list-unit-files adguard.service >/dev/null 2>&1; then
    systemctl --user disable --now adguard.service 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/adguard.service"
    systemctl --user daemon-reload 2>/dev/null || true
fi

echo
echo "Installation complete."
echo "Run now:  $DIR/venv/bin/python $DIR/AdGuard.py"
echo "GNOME users: the tray icon needs the AppIndicator extension"
echo "  (package gnome-shell-extension-appindicator on Ubuntu/Debian/Fedora)."
