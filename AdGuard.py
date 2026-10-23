import sys
import os
import subprocess
import time
import json
import re
import queue
import shutil
import tempfile
import webbrowser
from urllib.request import Request, urlopen
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QListWidget, QSystemTrayIcon, QMenu, QAction, 
                             QFrame, QListWidgetItem, QSizePolicy, 
                             QLineEdit, QStackedWidget, QDialog, QMessageBox, QCheckBox,
                             QStyleOptionButton, QStyle)
from PyQt5.QtGui import QIcon, QFont, QColor, QPainter, QCursor, QDesktopServices, QFontMetrics
from PyQt5.QtCore import Qt, QTimer, QSize, QPoint, QThread, pyqtSignal, QUrl, QEvent, QRectF, QRect
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

# Resolve paths relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
APP_ICON_PATH = os.path.join(ASSETS_DIR, "app_icon.png")
CONNECTED_ICON_PATH = os.path.join(ASSETS_DIR, "connected.png")
DISCONNECTED_ICON_PATH = os.path.join(ASSETS_DIR, "disconnected.png")
CHECK_ICON_PATH = os.path.join(ASSETS_DIR, "check.png")
LOCK_ICON_PATH = os.path.join(ASSETS_DIR, "lock.png")
FAVORITES_FILE = os.path.expanduser("~/.config/adguard-gui-favorites.json")
LOCATIONS_CACHE_FILE = os.path.expanduser("~/.config/adguard-locations-cache.json")
SETTINGS_FILE = os.path.expanduser("~/.config/adguard-gui-settings.json")
AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/adguard.desktop")
IPC_SERVER_NAME = "adguard_vpn_gui_ipc"
CLI_NAME = "adguardvpn-cli"
CLI_DEFAULT_PATH = "/opt/adguardvpn_cli/adguardvpn-cli"
CLI_PROJECT_URL = "https://github.com/AdguardTeam/AdGuardVPNCLI"
# The official one-liner from AdGuard's README, shown to the user verbatim.
CLI_INSTALL_COMMAND = ("curl -fsSL https://raw.githubusercontent.com/AdguardTeam/AdGuardVPNCLI/HEAD/"
                       "scripts/release/install.sh | sh -s -- -v")

SCROLLBAR_STYLE_HIDDEN = """
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 4px 2px 4px 0px;
}
QScrollBar::handle:vertical {
    background: transparent;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""

SCROLLBAR_STYLE_VISIBLE = """
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 4px 2px 4px 0px;
}
QScrollBar::handle:vertical {
    background: rgba(148, 163, 184, 0.45);
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(148, 163, 184, 0.75);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""

STRINGS = {
    "ru": {
        "app_title": "AdGuard VPN",
        "checking_status": "Проверка статуса...",
        "connected_pill": "● ПОДКЛЮЧЕНО",
        "disconnected_pill": "● ОТКЛЮЧЕНО",
        "connecting_pill": "● ПОДКЛЮЧЕНИЕ",
        "status_unknown": "Статус неизвестен",
        "cli_missing": "adguardvpn-cli не найден. Установите AdGuard VPN CLI.",
        "cli_missing_title": "AdGuard VPN не установлен",
        "cli_missing_desc": "Это окно работает поверх официальной консольной программы AdGuard VPN. Установите её командой ниже: откроется терминал, установщик задаст вопросы и попросит пароль администратора.",
        "install_in_terminal": "Установить в терминале",
        "copy_command": "Скопировать команду",
        "cli_project_page": "Страница AdGuard VPN CLI",
        "command_copied": "Команда скопирована. Вставьте её в терминал.",
        "terminal_opened": "Терминал открыт. Когда установка закончится, окно переключится само.",
        "no_terminal_found": "Не нашёл терминал. Скопируйте команду и выполните её вручную.",
        "not_protected": "Защита выключена",
        "connect": "Подключиться",
        "disconnect": "Отключиться",
        "working": "Обработка...",
        "connecting": "Подключение...",
        "disconnecting": "Отключение...",
        "checking_ip": "IP: Проверка внешнего IP...",
        "refreshing_ip": "IP: Обновление...",
        "ip_unavailable": "🔒 Публичный IP недоступен",
        "refresh_ip_tooltip": "Обновить публичный IP",
        "locations": "Локации",
        "all": "Все",
        "favorites": "★ Избранное",
        "search_placeholder": "Поиск города или страны (Esc чтобы закрыть)...",
        "search_tooltip": "Поиск локаций",
        "refresh_locations_tooltip": "Обновить локации и пинги (↻)",
        "refreshing_locations_tooltip": "Обновление локаций и пингов...",
        "updated_locations_tooltip": "Обновлено: {count} локаций",
        "refresh_failed_tooltip": "Не удалось обновить локации. Попробуйте снова.",
        "exclusions_btn": "🛡️ Исключения сайтов",
        "autostart": "Автозапуск",
        "autostart_tooltip": "Автоматически запускать AdGuard VPN при входе в систему",
        "not_signed_in": "Не авторизован",
        "not_signed_in_btn": "⚠️ Войти",
        "sign_in_title": "Вход в AdGuard VPN",
        "sign_in_desc": "Войдите в аккаунт AdGuard, чтобы получить доступ к серверам и защитить свой трафик.",
        "sign_in_browser_btn": "🌐 Войти через браузер",
        "browser_opened_status": "В браузере открыта страница авторизации. Завершите вход...",
        "open_link_again": "Открыть снова",
        "copy_link": "Скопировать ссылку",
        "cancel": "Отмена",
        "link_copied": "Ссылка скопирована в буфер обмена!",
        "starting_auth": "Запуск авторизации в браузере...",
        "auth_success": "Авторизация прошла успешно!",
        "auth_canceled": "Авторизация отменена или истекло время.",
        "close_tooltip": "Скрыть в трей (Esc)",
        "user_tier_premium": "Тариф: Premium",
        "user_tier_free": "Тариф: Бесплатный",
        "until": "до",
        "refresh_account": "↻ Обновить данные аккаунта",
        "logout": "🚪 Выйти из аккаунта",
        "quit": "❌ Выйти из AdGuard",
        "logout_confirm_title": "Выход из аккаунта",
        "logout_confirm_msg": "Вы действительно хотите выйти из аккаунта {email}?",
        "connect_to_this": "Подключиться к этой локации",
        "add_favorite": "★ Добавить в избранное",
        "remove_favorite": "Удалить из избранного",
        "exclusions_dialog_title": "Исключения сайтов",
        "exclusions_dialog_info": "Трафик для этих доменов идет напрямую в обход VPN-туннеля:",
        "exclusions_mode_general": "Режим GENERAL: трафик этих доменов идёт напрямую, в обход VPN:",
        "exclusions_mode_selective": "Режим SELECTIVE: через VPN идёт только трафик этих доменов:",
        "exclusions_input_placeholder": "Введите домен (например, example.com)",
        "add": "Добавить",
        "remove": "Удалить",
        "refresh": "Обновить",
        "clear_all": "Очистить всё",
        "clear_exclusions_confirm": "Удалить все добавленные исключения сайтов?",
        "no_exclusions": "Исключения не настроены",
        "exclusions_count": "Исключений: {count}",
        "exclusions_loading": "Загрузка списка исключений...",
        "exclusions_updating": "Обновление списка исключений...",
        "exclusions_error": "Ошибка при обновлении исключений. Попробуйте снова.",
        "tray_tooltip_connected": "AdGuard VPN (Подключено к {location})",
        "tray_tooltip_disconnected": "AdGuard VPN (Отключено)",
        "no_connection": "Нет соединения",
        "copy_ip_tooltip": "Нажмите, чтобы скопировать IP",
        "copied": "Скопировано!"
    },
    "en": {
        "app_title": "AdGuard VPN",
        "checking_status": "Checking status...",
        "connected_pill": "● CONNECTED",
        "disconnected_pill": "● DISCONNECTED",
        "connecting_pill": "● CONNECTING",
        "status_unknown": "Status unknown",
        "cli_missing": "adguardvpn-cli not found. Install AdGuard VPN CLI.",
        "cli_missing_title": "AdGuard VPN is not installed",
        "cli_missing_desc": "This window runs on top of the official AdGuard VPN command-line program. Install it with the command below: a terminal opens, the installer asks its questions and needs your administrator password.",
        "install_in_terminal": "Install in a terminal",
        "copy_command": "Copy command",
        "cli_project_page": "AdGuard VPN CLI page",
        "command_copied": "Command copied. Paste it into a terminal.",
        "terminal_opened": "Terminal opened. The window switches by itself once the install finishes.",
        "no_terminal_found": "No terminal emulator found. Copy the command and run it yourself.",
        "not_protected": "Not Protected",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "working": "Working...",
        "connecting": "Connecting...",
        "disconnecting": "Disconnecting...",
        "checking_ip": "IP: Checking public IP...",
        "refreshing_ip": "IP: Refreshing...",
        "ip_unavailable": "🔒 Public IP unavailable",
        "refresh_ip_tooltip": "Refresh public IP",
        "locations": "Locations",
        "all": "All",
        "favorites": "★ Favorites",
        "search_placeholder": "Search city or country (Esc to close)...",
        "search_tooltip": "Search locations",
        "refresh_locations_tooltip": "Refresh locations & pings (↻)",
        "refreshing_locations_tooltip": "Refreshing locations & pings...",
        "updated_locations_tooltip": "Updated: {count} locations",
        "refresh_failed_tooltip": "Unable to refresh locations. Try again.",
        "exclusions_btn": "🛡️ Site exclusions",
        "autostart": "Autostart",
        "autostart_tooltip": "Automatically launch AdGuard VPN on system startup",
        "not_signed_in": "Not signed in",
        "not_signed_in_btn": "⚠️ Log In",
        "sign_in_title": "Sign in to AdGuard VPN",
        "sign_in_desc": "Connect your account to access high-speed VPN locations and protect your internet traffic.",
        "sign_in_browser_btn": "🌐 Sign in via Browser",
        "browser_opened_status": "A browser window has opened for authorization...",
        "open_link_again": "Open link again",
        "copy_link": "Copy link",
        "cancel": "Cancel",
        "link_copied": "Link copied to clipboard!",
        "starting_auth": "Starting browser authorization...",
        "auth_success": "Signed in successfully!",
        "auth_canceled": "Authorization was canceled or timed out.",
        "close_tooltip": "Hide to tray (Esc)",
        "user_tier_premium": "Tier: Premium",
        "user_tier_free": "Tier: Free",
        "until": "until",
        "refresh_account": "↻ Refresh Account Info",
        "logout": "🚪 Log Out",
        "quit": "❌ Quit AdGuard",
        "logout_confirm_title": "Log Out",
        "logout_confirm_msg": "Are you sure you want to log out from {email}?",
        "connect_to_this": "Connect to this location",
        "add_favorite": "★ Add to Favorites",
        "remove_favorite": "Remove from Favorites",
        "exclusions_dialog_title": "Site exclusions",
        "exclusions_dialog_info": "Traffic to these domains bypasses the VPN tunnel:",
        "exclusions_mode_general": "GENERAL mode: traffic to these domains bypasses the VPN:",
        "exclusions_mode_selective": "SELECTIVE mode: only traffic to these domains goes through the VPN:",
        "exclusions_input_placeholder": "Enter domain name (e.g. example.com)",
        "add": "Add",
        "remove": "Remove",
        "refresh": "Refresh",
        "clear_all": "Clear all",
        "clear_exclusions_confirm": "Remove all site exclusions?",
        "no_exclusions": "No exclusions configured",
        "exclusions_count": "Exclusions count: {count}",
        "exclusions_loading": "Loading exclusions...",
        "exclusions_updating": "Updating exclusions...",
        "exclusions_error": "Action failed. Try again.",
        "tray_tooltip_connected": "AdGuard VPN (Connected to {location})",
        "tray_tooltip_disconnected": "AdGuard VPN (Disconnected)",
        "no_connection": "No connection",
        "copy_ip_tooltip": "Click to copy IP",
        "copied": "Copied!"
    }
}


def send_ipc_message(message="show"):
    socket = QLocalSocket()
    socket.connectToServer(IPC_SERVER_NAME)
    if socket.waitForConnected(600):
        socket.write(message.encode("utf-8") + b"\n")
        socket.waitForBytesWritten(600)
        socket.disconnectFromServer()
        return True
    return False


ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def strip_ansi(text):
    return ANSI_RE.sub('', text or "")


def find_cli():
    """Path of adguardvpn-cli: PATH first, then the installer's default dir
    (the installer offers the /usr/local/bin link as a question, so a user
    who answered "no" still has a working binary in /opt)."""
    found = shutil.which(CLI_NAME)
    if found:
        return found
    if os.access(CLI_DEFAULT_PATH, os.X_OK):
        return CLI_DEFAULT_PATH
    return None


TERMINALS = (
    # (executable, args that precede the program to run)
    ("x-terminal-emulator", ["-e"]),
    ("ptyxis", ["--"]),
    ("gnome-terminal", ["--"]),
    ("konsole", ["-e"]),
    ("xfce4-terminal", ["-x"]),
    ("kgx", ["-e"]),
    ("mate-terminal", ["-x"]),
    ("lxterminal", ["-e"]),
    ("alacritty", ["-e"]),
    ("kitty", ["--"]),
    ("xterm", ["-e"]),
)


def terminal_command_for(script_path, terminals=TERMINALS, which=shutil.which):
    """Return argv that runs `bash script_path` in the first terminal found."""
    for exe, prefix in terminals:
        path = which(exe)
        if path:
            return [path] + prefix + ["bash", script_path]
    return None


def install_script_text(install_command=CLI_INSTALL_COMMAND):
    """Shell script the install terminal runs: the official command, after
    checking for curl (AdGuard's installer downloads the package with curl
    itself, so a wget fallback would only fail later), and a pause so the
    output stays readable. Nothing is answered for the user."""
    return (
        "#!/bin/bash\n"
        "echo 'AdGuard VPN CLI install (official script):'\n"
        f"echo '  {install_command}'\n"
        "echo\n"
        "if command -v curl >/dev/null 2>&1; then\n"
        f"    {install_command}\n"
        "else\n"
        "    echo 'curl is not installed, and the AdGuard installer needs it.'\n"
        "    echo 'Install curl first, then press the button again. For example:'\n"
        "    echo '  Debian/Ubuntu: sudo apt install curl'\n"
        "    echo '  Fedora:        sudo dnf install curl'\n"
        "    echo '  Arch:          sudo pacman -S curl'\n"
        "fi\n"
        "echo\n"
        "read -rp 'Press Enter to close this window...' _\n"
    )


def open_install_terminal():
    """Open a terminal running the official installer. Returns True if a
    terminal was launched."""
    fd, script_path = tempfile.mkstemp(prefix="adguardvpn-install-", suffix=".sh")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(install_script_text())
    os.chmod(script_path, 0o700)
    argv = terminal_command_for(script_path)
    if not argv:
        return False
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        return False
    return True


def run_cli_command(command, timeout=6):
    """Run adguardvpn-cli non-interactively and return (stdout+stderr, ok).

    `connect` gets `-y` so the CLI never waits for a keyboard answer: there is
    no terminal behind the GUI and a prompt would hang until the timeout.
    """
    try:
        if command and command[0] in ("list-locations", "connect"):
            timeout = 30
        if command and command[0] == "connect" and "-y" not in command:
            command = command + ["-y"]
        result = subprocess.run(
            [find_cli() or CLI_NAME] + command,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        out = (result.stdout + ("\n" + result.stderr if result.stderr else "")).strip()
        return out, result.returncode == 0
    except Exception as e:
        return str(e), False


def parse_status_output(out_text):
    """Map `adguardvpn-cli status` output to (state, location).

    state is one of "connected", "connecting", "disconnected", "logged_out",
    "unknown". The CLI prints e.g. "Connected to DENVER in TUN mode, running
    on tun0", "VPN is disconnected", "VPN is starting", "Connecting to X in
    TUN mode", "You are not logged in".
    """
    clean = strip_ansi(out_text)
    first = clean.strip().splitlines()[0].strip() if clean.strip() else ""
    low = first.lower()
    if "not logged in" in low or "please log in" in low:
        return "logged_out", ""
    if low.startswith("connected to"):
        loc = first[len("connected to"):].strip()
        if " in " in loc:
            loc = loc.split(" in ")[0]
        return "connected", loc.strip()
    if low.startswith("connecting") or "is starting" in low:
        loc = ""
        if low.startswith("connecting to"):
            loc = first[len("connecting to"):].strip()
            if " in " in loc:
                loc = loc.split(" in ")[0]
        return "connecting", loc.strip()
    if "disconnected" in low or "not connected" in low:
        return "disconnected", ""
    return "unknown", ""


def parse_license_output(out_text, success):
    """Map `adguardvpn-cli license` output to (state, email, is_premium, valid_until).

    state: "logged_in", "logged_out" or "unknown" (transient failure such as no
    network; the caller must keep its previous auth state in that case).
    """
    clean = strip_ansi(out_text)
    if "Logged in as" in clean:
        email_match = re.search(r'Logged in as\s+([^\s\n]+)', clean)
        email = email_match.group(1) if email_match else "User"
        is_premium = "PREMIUM" in clean.upper()
        exp_match = re.search(r'valid until\s+([^\s\n]+)', clean)
        valid_until = exp_match.group(1) if exp_match else ""
        return "logged_in", email, is_premium, valid_until
    low = clean.lower()
    if "not logged in" in low or "please log in" in low:
        return "logged_out", "", False, ""
    if success and not clean.strip():
        return "logged_out", "", False, ""
    return "unknown", "", False, ""


def parse_exclusions_output(out_text):
    """Map `adguardvpn-cli site-exclusions show` output to (mode, [domains]).

    First line is "Exclusions for GENERAL mode:" (or SELECTIVE), then one
    domain per line.
    """
    clean = strip_ansi(out_text)
    mode = ""
    exclusions = []
    for line in clean.splitlines():
        item = line.strip().lstrip("-• ").strip()
        if not item:
            continue
        low = item.lower()
        if low.startswith("exclusions for "):
            m = re.search(r'exclusions for\s+(\w+)\s+mode', low)
            mode = m.group(1) if m else ""
            continue
        if low.startswith("no exclusions"):
            continue
        exclusions.append(item)
    return mode, exclusions


def split_exclusions_input(text):
    """Split user input "a.com, b.com c.com" into separate CLI arguments."""
    return [part for part in re.split(r'[\s,;]+', text or "") if part]


def parse_locations_output(out_text):
    """Parse the fixed-width table printed by `adguardvpn-cli list-locations`.

    Columns: ISO (0-6), COUNTRY (6-27), CITY (27-58), PING ESTIMATE (58-).
    """
    clean_out = strip_ansi(out_text)
    locations = []
    for line in clean_out.splitlines():
        line = line.rstrip()
        if not line or line.startswith("ISO") or "adguardvpn-cli" in line:
            continue
        if len(line) >= 6:
            iso = line[0:6].strip()
            country = line[6:27].strip() if len(line) > 6 else ""
            city = line[27:58].strip() if len(line) > 27 else ""
            ping = line[58:].strip() if len(line) > 58 else ""
            if iso and len(iso) == 2 and iso.isupper() and (city or country):
                locations.append({
                    "iso": iso,
                    "country": country,
                    "city": city,
                    "ping": ping
                })
    return locations


def is_system_autostart_enabled():
    if os.path.exists(AUTOSTART_FILE):
        try:
            with open(AUTOSTART_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                if "Hidden=true" in content or "X-GNOME-Autostart-enabled=false" in content:
                    return False
                return True
        except Exception:
            return False
    return False


def set_system_autostart_enabled(enabled):
    autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    
    app_path = os.path.join(BASE_DIR, "AdGuard.py")
    python_path = sys.executable
    icon_path = APP_ICON_PATH
    
    if enabled:
        content = f"""[Desktop Entry]
Type=Application
Name=AdGuard
Comment=AdGuard VPN Client
Exec={python_path} {app_path} --minimized
Icon={icon_path}
Terminal=false
Categories=Network;
X-GNOME-Autostart-enabled=true
Hidden=false
"""
        with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        if os.path.exists(AUTOSTART_FILE):
            try:
                os.remove(AUTOSTART_FILE)
            except Exception:
                pass


def is_wayland_session():
    """True when the desktop session is Wayland.

    Under Wayland (also when Qt itself runs through XWayland) the pointer
    position an app can read is stale: it is the last point the pointer was
    seen over one of the app's own windows, not where the tray was clicked.
    """
    return (os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            or bool(os.environ.get("WAYLAND_DISPLAY")))


def compute_popup_position(window_size, avail_geo, anchor=None, margin=8):
    """Return the top-left QPoint for the tray popup window.

    The window always hangs from the top of the available screen area, i.e.
    right under a top panel. Horizontally it is centred on `anchor` (the
    tray icon or the click) when one is known, otherwise it hugs the right
    end of the panel, where indicators live in every desktop.
    """
    w, h = window_size.width(), window_size.height()
    if anchor is not None:
        x = anchor.x() - w // 2
    else:
        x = avail_geo.right() - margin - w
    y = avail_geo.top() + margin // 2
    x = max(avail_geo.left() + margin, min(x, avail_geo.right() - w - margin))
    y = min(y, max(avail_geo.top() + margin // 2, avail_geo.bottom() - h - margin // 2))
    return QPoint(x, y)


class ElidedLabel(QLabel):
    """One-line label that elides long text with an ellipsis and keeps the
    full text in the tooltip. Static on purpose: a scrolling ticker kept the
    process repainting while the window was open."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setFixedHeight(20)
        self.setStyleSheet("color: #94A3B8; font-size: 9pt;")
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self._apply_elide()

    def text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self):
        fm = QFontMetrics(self.font())
        width = max(self.width() - 2, 10)
        super().setText(fm.elidedText(self._full_text, Qt.ElideRight, width))


class RotatingRefreshButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._on_timer)
        self._is_rotating = False
        self.setFixedSize(24, 24)
        self.setCursor(Qt.PointingHandCursor)

    def start_rotation(self):
        self._is_rotating = True
        self.setEnabled(False)
        self._timer.start()

    def stop_rotation(self):
        self._is_rotating = False
        self._timer.stop()
        self._angle = 0
        self.setEnabled(True)
        self.update()

    def _on_timer(self):
        self._angle = (self._angle + 18) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        is_hover = self.underMouse() and self.isEnabled()
        if self._is_rotating:
            bg_color = QColor("#1E293B")
            border_color = QColor("#00E676")
            text_color = QColor("#00E676")
        elif is_hover:
            bg_color = QColor("#333333")
            border_color = QColor("#4CAF50")
            text_color = QColor("#4CAF50")
        else:
            bg_color = QColor("#252525")
            border_color = QColor("#3E3E3E")
            text_color = QColor("#CCCCCC")

        painter.setBrush(bg_color)
        painter.setPen(border_color)
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 4, 4)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        
        font = QFont("Ubuntu", 12, QFont.Bold)
        painter.setFont(font)
        painter.setPen(text_color)
        
        painter.drawText(QRectF(-self.width()/2, -self.height()/2, self.width(), self.height()), Qt.AlignCenter, "↻")
        painter.restore()


class VPNWorker(QThread):
    """Single background thread that owns every adguardvpn-cli call.

    The GUI never calls the CLI directly: it queues actions here and listens
    to the signals. Between actions the thread polls `status` every 2 s and
    `license` every ~30 s, so the window always mirrors what the CLI reports.
    """
    status_updated = pyqtSignal(str, str)          # state, location
    auth_updated = pyqtSignal(bool, str, bool, str)
    login_link_received = pyqtSignal(str)
    login_finished = pyqtSignal(bool, str)
    locations_updated = pyqtSignal(list)
    locations_refresh_finished = pyqtSignal(bool, int)
    exclusions_updated = pyqtSignal(str, list, bool)  # mode, items, ok
    exclusions_action_finished = pyqtSignal(str, bool)
    action_finished = pyqtSignal(str)
    external_ip_updated = pyqtSignal(str, str, bool)

    STATUS_INTERVAL = 2.0
    AUTH_INTERVAL = 30.0

    def __init__(self):
        super().__init__()
        self.running = True
        self.actions = queue.Queue()
        self.login_proc = None
        self.is_authenticated = None  # unknown until the first `license` call

    def run(self):
        self.refresh_auth()
        self.refresh_status()
        self.refresh_locations()
        last_auth = time.monotonic()

        while self.running:
            try:
                action = self.actions.get(timeout=self.STATUS_INTERVAL)
            except queue.Empty:
                self.refresh_status()
                if time.monotonic() - last_auth >= self.AUTH_INTERVAL:
                    self.refresh_auth()
                    last_auth = time.monotonic()
                continue
            if action is None:
                break
            self.handle_action(action)

    def handle_action(self, action):
        if action == "connect":
            run_cli_command(["connect"])
            self.action_finished.emit("connect")
            self.refresh_status()
        elif action == "disconnect":
            run_cli_command(["disconnect"])
            self.action_finished.emit("disconnect")
            self.refresh_status()
        elif action == "login":
            self.perform_browser_login()
        elif action == "cancel_login":
            self.cancel_browser_login()
        elif action == "logout":
            run_cli_command(["logout"])
            self.refresh_auth()
            self.refresh_status()
        elif action == "refresh_auth":
            self.refresh_auth()
        elif action == "refresh_locations":
            self.refresh_locations()
        elif action == "refresh_exclusions":
            self.refresh_exclusions()
        elif action == "refresh_external_ip":
            self.refresh_external_ip()
        elif action.startswith("add_exclusions:"):
            exclusions = split_exclusions_input(action.split(":", 1)[1])
            _, success = run_cli_command(["site-exclusions", "add"] + exclusions)
            self.exclusions_action_finished.emit("add", success)
            self.refresh_exclusions()
        elif action.startswith("remove_exclusion:"):
            exclusion = action.split(":", 1)[1]
            _, success = run_cli_command(["site-exclusions", "remove", exclusion])
            self.exclusions_action_finished.emit("remove", success)
            self.refresh_exclusions()
        elif action == "clear_exclusions":
            _, success = run_cli_command(["site-exclusions", "clear"])
            self.exclusions_action_finished.emit("clear", success)
            self.refresh_exclusions()
        elif action.startswith("connect_to:"):
            location = action.split(":", 1)[1]
            run_cli_command(["connect", "-l", location])
            self.action_finished.emit("connect")
            self.refresh_status()

    def refresh_status(self):
        out, success = run_cli_command(["status"])
        state, location = parse_status_output(out)
        if state == "logged_out":
            if self.is_authenticated is not False:
                self.is_authenticated = False
                self.auth_updated.emit(False, "", False, "")
            self.status_updated.emit("disconnected", "")
            return
        if not success and state == "unknown":
            if find_cli() is None:
                self.status_updated.emit("cli_missing", "")
            else:
                self.status_updated.emit("unknown", "")
            return
        self.status_updated.emit(state, location)

    def refresh_auth(self):
        out, success = run_cli_command(["license"])
        state, email, is_premium, valid_until = parse_license_output(out, success)
        if state == "logged_in":
            self.is_authenticated = True
            self.auth_updated.emit(True, email, is_premium, valid_until)
        elif state == "logged_out":
            self.is_authenticated = False
            self.auth_updated.emit(False, "", False, "")
        # "unknown" (e.g. no network): keep the last known auth state.

    def perform_browser_login(self):
        try:
            self.login_proc = subprocess.Popen(
                [find_cli() or CLI_NAME, "login"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            for line in iter(self.login_proc.stdout.readline, ""):
                line_str = strip_ansi(line).strip()
                if not line_str:
                    continue
                match = re.search(r'(https?://[^\s]+)', line_str)
                if match:
                    auth_url = match.group(1).rstrip(".,)]")
                    self.login_link_received.emit(auth_url)
                    try:
                        webbrowser.open(auth_url)
                    except Exception:
                        pass
            self.login_proc.wait()
            ret = self.login_proc.returncode
            self.login_proc = None

            if ret == 0:
                self.login_finished.emit(True, "auth_success")
                self.refresh_auth()
                self.refresh_locations()
                self.refresh_status()
            else:
                self.login_finished.emit(False, "auth_canceled")
        except Exception as e:
            self.login_proc = None
            self.login_finished.emit(False, str(e))

    def cancel_browser_login(self):
        if self.login_proc:
            try:
                self.login_proc.terminate()
            except Exception:
                pass
            self.login_proc = None

    def refresh_locations(self):
        out, success = run_cli_command(["list-locations"])
        count = 0
        if success:
            locations = parse_locations_output(out)
            if locations:
                count = len(locations)
                self.locations_updated.emit(locations)
                try:
                    with open(LOCATIONS_CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(locations, f, ensure_ascii=False)
                except Exception:
                    pass
            else:
                success = False
        self.locations_refresh_finished.emit(success, count)

    def refresh_exclusions(self):
        out, success = run_cli_command(["site-exclusions", "show"])
        if success:
            mode, exclusions = parse_exclusions_output(out)
            self.exclusions_updated.emit(mode, exclusions, True)
        else:
            self.exclusions_updated.emit("", [], False)

    def refresh_external_ip(self):
        services = ("https://ipwho.is/", "https://ipapi.co/json/")
        for service_url in services:
            try:
                request = Request(
                    service_url,
                    headers={"User-Agent": "AdGuardVPN-GUI/1.0"},
                )
                with urlopen(request, timeout=4) as response:
                    data = json.loads(response.read().decode("utf-8"))

                if data.get("success") is False or not data.get("ip"):
                    raise ValueError("API returned no IP address")

                city = data.get("city") or ""
                region = data.get("region") or data.get("region_name") or ""
                country = data.get("country") or data.get("country_name") or ""
                location_parts = [part for part in (city, region, country) if part]
                location = ", ".join(location_parts) or "Location unavailable"
                self.external_ip_updated.emit(str(data["ip"]), location, True)
                return
            except Exception:
                continue

        self.external_ip_updated.emit("", "", False)

    def request_action(self, action):
        self.actions.put(action)

    def stop(self):
        self.running = False
        self.actions.put(None)


class AdGuardVPNApp(QWidget):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.is_connected = False
        self.is_logged_in = True
        self.current_user_email = ""
        self.is_premium = False
        self.valid_until = ""
        self.auth_link = ""
        self.filter_mode = "all"
        self.exclusions_count = 0
        self.current_lang = "ru"
        self.last_anchor = None
        self.connection_state = "unknown"
        self.current_location_name = ""
        self.exclusions_mode = ""
        
        self.external_ip_refresh_in_progress = False
        self.current_ip_str = ""
        self.refresh_in_progress = False
        self.raw_locations = []
        self.favorites = set()
        
        self.load_settings()
        self.load_favorites()
        self.initUI()
        self.apply_language()
        self.setup_ipc_server()
        self.load_cached_locations()

        self.worker = VPNWorker()
        self.worker.status_updated.connect(self.on_status_updated)
        self.worker.auth_updated.connect(self.on_auth_updated)
        self.worker.login_link_received.connect(self.on_login_link_received)
        self.worker.login_finished.connect(self.on_login_finished)
        self.worker.locations_updated.connect(self.on_locations_updated)
        self.worker.locations_refresh_finished.connect(self.on_locations_refresh_finished)
        self.worker.exclusions_updated.connect(self.on_exclusions_updated)
        self.worker.exclusions_action_finished.connect(self.on_exclusions_action_finished)
        self.worker.action_finished.connect(self.on_action_finished)
        self.worker.external_ip_updated.connect(self.on_external_ip_updated)
        self.worker.start()

        # Without a tray (e.g. GNOME without the AppIndicator extension) a
        # minimized start would leave no way to reach the window: show it.
        if not start_minimized or not QSystemTrayIcon.isSystemTrayAvailable():
            QTimer.singleShot(100, self.show_window)

    def t(self, key, **kwargs):
        lang_dict = STRINGS.get(self.current_lang, STRINGS["ru"])
        text = lang_dict.get(key, STRINGS["en"].get(key, key))
        if kwargs:
            text = text.format(**kwargs)
        return text

    def load_settings(self):
        default_lang = "ru" if os.environ.get("LANG", "").lower().startswith("ru") else "en"
        self.current_lang = default_lang
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.current_lang = settings.get("lang", default_lang)
            except Exception:
                pass

    def save_settings(self):
        try:
            settings = {
                "lang": self.current_lang,
                "autostart": is_system_autostart_enabled()
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False)
        except Exception:
            pass

    def set_language(self, lang):
        if self.current_lang != lang:
            self.current_lang = lang
            self.save_settings()
            self.apply_language()

    def toggle_language(self):
        new_lang = "en" if self.current_lang == "ru" else "ru"
        self.set_language(new_lang)

    def apply_language(self):
        # Update dual-segmented pill buttons
        if hasattr(self, "btn_lang_ru") and hasattr(self, "btn_lang_en"):
            if self.current_lang == "ru":
                self.btn_lang_ru.setStyleSheet("""
                    QPushButton {
                        background-color: #00E676;
                        color: #0F141C;
                        border-radius: 9px;
                        font-weight: bold;
                        border: none;
                    }
                """)
                self.btn_lang_en.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #718096;
                        border-radius: 9px;
                        font-weight: normal;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #FFFFFF;
                    }
                """)
            else:
                self.btn_lang_en.setStyleSheet("""
                    QPushButton {
                        background-color: #00E676;
                        color: #0F141C;
                        border-radius: 9px;
                        font-weight: bold;
                        border: none;
                    }
                """)
                self.btn_lang_ru.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #718096;
                        border-radius: 9px;
                        font-weight: normal;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #FFFFFF;
                    }
                """)
        elif hasattr(self, "lang_btn"):
            self.lang_btn.setText("RU" if self.current_lang == "ru" else "EN")

        if hasattr(self, "app_title_label"):
            self.app_title_label.setText(self.t("app_title"))
        if hasattr(self, "close_btn"):
            self.close_btn.setToolTip(self.t("close_tooltip"))
        if hasattr(self, "loc_label"):
            cnt = len(self.raw_locations) if hasattr(self, "raw_locations") and self.raw_locations else 0
            self.loc_label.setText(f"{self.t('locations')} ({cnt})" if cnt else self.t("locations"))
        if hasattr(self, "filter_all_btn"):
            self.filter_all_btn.setText(self.t("all"))
        if hasattr(self, "filter_fav_btn"):
            fav_cnt = len(self.favorites) if hasattr(self, "favorites") else 0
            self.filter_fav_btn.setText(f"{self.t('favorites')} ({fav_cnt})" if fav_cnt else self.t("favorites"))
        if hasattr(self, "search_input"):
            self.search_input.setPlaceholderText(self.t("search_placeholder"))
        if hasattr(self, "search_btn"):
            self.search_btn.setToolTip(self.t("search_tooltip"))
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setToolTip(self.t("refresh_locations_tooltip"))
        if hasattr(self, "ip_click_btn"):
            self.ip_click_btn.setToolTip(self.t("copy_ip_tooltip"))
        if hasattr(self, "external_ip_refresh_btn"):
            self.external_ip_refresh_btn.setToolTip(self.t("refresh_ip_tooltip"))
        if hasattr(self, "exclusions_btn"):
            self.exclusions_btn.setText(f"{self.t('exclusions_btn')} ({self.exclusions_count})")
        if hasattr(self, "autostart_checkbox"):
            self.autostart_checkbox.setText(self.t("autostart"))
            self.autostart_checkbox.setToolTip(self.t("autostart_tooltip"))
        
        # Login page strings
        if hasattr(self, "login_title"):
            self.login_title.setText(self.t("sign_in_title"))
        if hasattr(self, "login_desc"):
            self.login_desc.setText(self.t("sign_in_desc"))
        if hasattr(self, "start_login_btn"):
            self.start_login_btn.setText(self.t("sign_in_browser_btn"))
        if hasattr(self, "reopen_browser_btn"):
            self.reopen_browser_btn.setText(self.t("open_link_again"))
        if hasattr(self, "copy_link_btn"):
            self.copy_link_btn.setText(self.t("copy_link"))
        if hasattr(self, "cancel_login_btn"):
            self.cancel_login_btn.setText(self.t("cancel"))
        
        if hasattr(self, "no_cli_title"):
            self.no_cli_title.setText(self.t("cli_missing_title"))
            self.no_cli_desc.setText(self.t("cli_missing_desc"))
            self.install_cli_btn.setText(self.t("install_in_terminal"))
            self.copy_cli_command_btn.setText(self.t("copy_command"))
            self.cli_page_btn.setText(self.t("cli_project_page"))

        # Update button text
        if hasattr(self, "toggle_btn"):
            self.update_btn_style(self.is_connected)

        # Update status text immediately
        if hasattr(self, "status_label"):
            self.render_status()
        
        # Update account chip
        if hasattr(self, "account_chip"):
            self.update_account_chip_ui()

        # Re-render locations list if loaded
        if hasattr(self, "raw_locations") and self.raw_locations:
            self.on_locations_updated(self.raw_locations)

    def setup_ipc_server(self):
        self.ipc_server = QLocalServer(self)
        QLocalServer.removeServer(IPC_SERVER_NAME)
        self.ipc_server.newConnection.connect(self.handle_ipc_connection)
        self.ipc_server.listen(IPC_SERVER_NAME)

    def handle_ipc_connection(self):
        client = self.ipc_server.nextPendingConnection()
        if client:
            client.waitForReadyRead(500)
            msg = bytes(client.readAll()).decode("utf-8").strip()
            if msg == "show" or not msg:
                self.show_window()
            client.disconnectFromServer()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setFixedSize(360, 580)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QFrame#container {
                background-color: #1A1A1A;
                border-radius: 14px;
                border: 1px solid #333333;
            }
            QLabel {
                color: #FFFFFF;
            }
        """)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(10)
        container_layout.setContentsMargins(14, 12, 14, 14)
        
        # --- Top Header Bar ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(6)
        
        # Logo Shield Icon
        self.logo_icon = QLabel()
        logo_pixmap = QIcon(APP_ICON_PATH).pixmap(20, 20)
        self.logo_icon.setPixmap(logo_pixmap)
        
        self.app_title_label = QLabel("AdGuard VPN")
        self.app_title_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.app_title_label.setStyleSheet("color: #E0E0E0;")
        
        top_bar.addWidget(self.logo_icon)
        top_bar.addWidget(self.app_title_label)
        top_bar.addStretch()
        
        # Language Switcher Dual-Pill (RU | EN)
        self.lang_container = QFrame()
        self.lang_container.setFixedHeight(24)
        self.lang_container.setStyleSheet("""
            QFrame {
                background-color: #212832;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)
        lang_layout = QHBoxLayout(self.lang_container)
        lang_layout.setContentsMargins(2, 2, 2, 2)
        lang_layout.setSpacing(1)

        self.btn_lang_ru = QPushButton("RU")
        self.btn_lang_en = QPushButton("EN")
        for b in (self.btn_lang_ru, self.btn_lang_en):
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(25, 18)
            b.setFont(QFont("Arial", 9, QFont.Bold))

        self.btn_lang_ru.clicked.connect(lambda: self.set_language("ru"))
        self.btn_lang_en.clicked.connect(lambda: self.set_language("en"))

        lang_layout.addWidget(self.btn_lang_ru)
        lang_layout.addWidget(self.btn_lang_en)
        top_bar.addWidget(self.lang_container)
        
        # User Account Button (pictogram)
        self.account_chip = QPushButton("👤")
        self.account_chip.setFixedSize(26, 24)
        self.account_chip.setCursor(Qt.PointingHandCursor)
        self.account_chip.clicked.connect(self.on_account_chip_clicked)
        self.update_account_chip_ui()
        top_bar.addWidget(self.account_chip)
        
        # Close Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: none;
                font-size: 13px;
                font-weight: bold;
                border-radius: 11px;
            }
            QPushButton:hover { background-color: #333333; color: #FFFFFF; }
        """)
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)
        container_layout.addLayout(top_bar)

        # --- Main Stack ---
        self.main_stack = QStackedWidget()
        
        # PAGE 0: MAIN DASHBOARD
        self.page_main = QWidget()
        page_main_layout = QVBoxLayout(self.page_main)
        page_main_layout.setContentsMargins(0, 0, 0, 0)
        page_main_layout.setSpacing(10)
        
        # Hero Connection Card
        self.hero_card = QFrame()
        self.hero_card.setObjectName("hero_card")
        self.hero_card.setStyleSheet("""
            QFrame#hero_card {
                background-color: #242424;
                border-radius: 12px;
                border: 1px solid #353535;
            }
        """)
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setSpacing(10)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        
        self.status_label = QLabel("Checking status...")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        hero_layout.addWidget(self.status_label)
        
        self.toggle_btn = QPushButton("Connect")
        self.toggle_btn.setFont(QFont("Arial", 14, QFont.Bold))
        self.toggle_btn.setFixedHeight(48)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn_style(False)
        self.toggle_btn.clicked.connect(self.toggle_connection)
        hero_layout.addWidget(self.toggle_btn)
        
        ip_row = QHBoxLayout()
        ip_row.setContentsMargins(0, 0, 0, 0)
        ip_row.setSpacing(6)
        
        self.ip_click_btn = QPushButton("...")
        self.ip_click_btn.setIcon(QIcon(LOCK_ICON_PATH))
        self.ip_click_btn.setIconSize(QSize(13, 13))
        self.ip_click_btn.setCursor(Qt.PointingHandCursor)
        self.ip_click_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #E2E8F0;
                border: none;
                font-size: 13.5px;
                font-weight: bold;
                text-align: left;
                padding: 0;
            }
            QPushButton:hover {
                color: #00E676;
            }
        """)
        self.ip_click_btn.clicked.connect(self.copy_ip_to_clipboard)
        self.ip_click_btn.setToolTip(self.t("copy_ip_tooltip"))
        
        self.ip_dot_label = QLabel("•")
        self.ip_dot_label.setStyleSheet("color: #64748B; font-size: 11px;")
        
        self.ip_ticker = ElidedLabel("")
        
        self.external_ip_refresh_btn = QPushButton("↻")
        self.external_ip_refresh_btn.setCursor(Qt.PointingHandCursor)
        self.external_ip_refresh_btn.setFixedSize(20, 20)
        self.external_ip_refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #777777;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { color: #4CAF50; }
            QPushButton:disabled { color: #444444; }
        """)
        self.external_ip_refresh_btn.clicked.connect(self.refresh_external_ip)
        
        ip_row.addWidget(self.ip_click_btn, 0)
        ip_row.addWidget(self.ip_dot_label, 0)
        ip_row.addWidget(self.ip_ticker, 1)
        ip_row.addWidget(self.external_ip_refresh_btn, 0)
        hero_layout.addLayout(ip_row)
        page_main_layout.addWidget(self.hero_card)

        # Locations Header & Toolbar
        loc_header_layout = QHBoxLayout()
        loc_header_layout.setContentsMargins(0, 2, 0, 0)
        loc_header_layout.setSpacing(6)
        
        self.loc_label = QLabel("Locations")
        self.loc_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.loc_label.setStyleSheet("color: #CCCCCC;")
        
        self.filter_all_btn = QPushButton("All")
        self.filter_all_btn.setCursor(Qt.PointingHandCursor)
        self.filter_all_btn.setFixedHeight(22)
        
        self.filter_fav_btn = QPushButton("★ Favorites")
        self.filter_fav_btn.setCursor(Qt.PointingHandCursor)
        self.filter_fav_btn.setFixedHeight(22)
        
        self.update_filter_tabs()
        self.filter_all_btn.clicked.connect(lambda: self.set_filter_mode("all"))
        self.filter_fav_btn.clicked.connect(lambda: self.set_filter_mode("fav"))
        
        self.refresh_btn = RotatingRefreshButton()
        self.refresh_btn.clicked.connect(self.refresh_locations)
        
        self.search_btn = QPushButton("🔍")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setFixedSize(24, 24)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #252525;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #333333; color: #FFFFFF; }
        """)
        self.search_btn.clicked.connect(self.toggle_search)
        
        loc_header_layout.addWidget(self.loc_label)
        loc_header_layout.addSpacing(6)
        loc_header_layout.addWidget(self.filter_all_btn)
        loc_header_layout.addWidget(self.filter_fav_btn)
        loc_header_layout.addStretch()
        loc_header_layout.addWidget(self.refresh_btn)
        loc_header_layout.addWidget(self.search_btn)
        page_main_layout.addLayout(loc_header_layout)
        
        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                color: white;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLineEdit:focus { border-color: #4CAF50; }
        """)
        self.search_input.textChanged.connect(self.filter_locations)
        self.search_input.installEventFilter(self)
        self.search_input.hide()
        page_main_layout.addWidget(self.search_input)
        
        # Locations List Widget
        self.locations_list = QListWidget()
        self.locations_list.setStyleSheet("""
            QListWidget {
                background-color: #212121;
                border-radius: 10px;
                border: 1px solid #333333;
                color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-bottom: 1px solid #2C2C2C;
            }
            QListWidget::item:selected {
                background-color: #388E3C;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: #2E2E2E;
                border-radius: 6px;
            }
        """)
        self.locations_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.locations_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self._scrollbar_timer = QTimer(self)
        self._scrollbar_timer.setSingleShot(True)
        self._scrollbar_timer.timeout.connect(self._hide_scrollbar)
        
        v_bar = self.locations_list.verticalScrollBar()
        v_bar.setStyleSheet(SCROLLBAR_STYLE_HIDDEN)
        v_bar.valueChanged.connect(self._show_scrollbar)
        v_bar.sliderMoved.connect(self._show_scrollbar)
        self.locations_list.viewport().installEventFilter(self)

        self.locations_list.itemDoubleClicked.connect(self.connect_to_location)
        self.locations_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.locations_list.customContextMenuRequested.connect(self.show_context_menu)
        page_main_layout.addWidget(self.locations_list)
        
        # Bottom Utility Bar (Site Exclusions & Autostart Checkbox)
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(2, 0, 2, 0)
        
        self.exclusions_btn = QPushButton("🛡️ Site exclusions")
        self.exclusions_btn.setCursor(Qt.PointingHandCursor)
        self.exclusions_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: none;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover { color: #4CAF50; }
        """)
        self.exclusions_btn.clicked.connect(self.show_exclusions)
        
        # Autostart Checkbox (Replacing previous Connected: Denver label)
        self.autostart_checkbox = QCheckBox("Автозапуск")
        self.autostart_checkbox.setCursor(Qt.PointingHandCursor)
        self.autostart_checkbox.setChecked(is_system_autostart_enabled())
        self.autostart_checkbox.toggled.connect(self.on_autostart_toggled)
        self.autostart_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: #888888;
                font-size: 11px;
                spacing: 6px;
            }}
            QCheckBox:hover {{
                color: #DDDDDD;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #555555;
                background-color: #242424;
            }}
            QCheckBox::indicator:hover {{
                border-color: #4CAF50;
            }}
            QCheckBox::indicator:checked {{
                background-color: #2E7D32;
                border-color: #4CAF50;
                image: url({CHECK_ICON_PATH});
            }}
        """)
        
        bottom_bar.addWidget(self.exclusions_btn)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.autostart_checkbox)
        page_main_layout.addLayout(bottom_bar)
        
        self.main_stack.addWidget(self.page_main)
        
        # PAGE 1: LOGIN VIEW
        self.page_login = QWidget()
        page_login_layout = QVBoxLayout(self.page_login)
        page_login_layout.setContentsMargins(10, 20, 10, 20)
        page_login_layout.setSpacing(14)
        page_login_layout.setAlignment(Qt.AlignCenter)
        
        self.login_icon_label = QLabel()
        login_pix = QIcon(APP_ICON_PATH).pixmap(64, 64)
        self.login_icon_label.setPixmap(login_pix)
        self.login_icon_label.setAlignment(Qt.AlignCenter)
        page_login_layout.addWidget(self.login_icon_label)
        
        self.login_title = QLabel("Sign in to AdGuard VPN")
        self.login_title.setFont(QFont("Arial", 15, QFont.Bold))
        self.login_title.setAlignment(Qt.AlignCenter)
        page_login_layout.addWidget(self.login_title)
        
        self.login_desc = QLabel(
            "Connect your account to access high-speed VPN locations and protect your internet traffic."
        )
        self.login_desc.setFont(QFont("Arial", 10))
        self.login_desc.setStyleSheet("color: #AAAAAA;")
        self.login_desc.setAlignment(Qt.AlignCenter)
        self.login_desc.setWordWrap(True)
        page_login_layout.addWidget(self.login_desc)
        
        page_login_layout.addSpacing(10)
        
        self.start_login_btn = QPushButton("🌐 Sign in via Browser")
        self.start_login_btn.setFont(QFont("Arial", 13, QFont.Bold))
        self.start_login_btn.setFixedHeight(48)
        self.start_login_btn.setCursor(Qt.PointingHandCursor)
        self.start_login_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 24px;
            }
            QPushButton:hover { background-color: #43A047; }
            QPushButton:pressed { background-color: #388E3C; }
            QPushButton:disabled { background-color: #555555; color: #888888; }
        """)
        self.start_login_btn.clicked.connect(self.start_browser_login)
        page_login_layout.addWidget(self.start_login_btn)
        
        self.login_progress_box = QWidget()
        progress_layout = QVBoxLayout(self.login_progress_box)
        progress_layout.setContentsMargins(0, 5, 0, 0)
        progress_layout.setSpacing(8)
        
        self.login_status_label = QLabel("A browser window has opened for authorization...")
        self.login_status_label.setStyleSheet("color: #81C784; font-size: 11px;")
        self.login_status_label.setAlignment(Qt.AlignCenter)
        self.login_status_label.setWordWrap(True)
        progress_layout.addWidget(self.login_status_label)
        
        btn_box = QHBoxLayout()
        self.reopen_browser_btn = QPushButton("Open link again")
        self.reopen_browser_btn.setCursor(Qt.PointingHandCursor)
        self.reopen_browser_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #DDDDDD;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #383838; color: #FFFFFF; }
        """)
        self.reopen_browser_btn.clicked.connect(self.reopen_auth_link)
        
        self.copy_link_btn = QPushButton("Copy link")
        self.copy_link_btn.setCursor(Qt.PointingHandCursor)
        self.copy_link_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #DDDDDD;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #383838; color: #FFFFFF; }
        """)
        self.copy_link_btn.clicked.connect(self.copy_auth_link)
        
        self.cancel_login_btn = QPushButton("Cancel")
        self.cancel_login_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FF8A80;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #3D2222; }
        """)
        self.cancel_login_btn.clicked.connect(self.cancel_browser_login)
        
        btn_box.addWidget(self.reopen_browser_btn)
        btn_box.addWidget(self.copy_link_btn)
        btn_box.addWidget(self.cancel_login_btn)
        progress_layout.addLayout(btn_box)
        
        self.login_progress_box.hide()
        page_login_layout.addWidget(self.login_progress_box)
        page_login_layout.addStretch()
        
        self.main_stack.addWidget(self.page_login)

        # PAGE 2: CLI NOT INSTALLED
        self.page_no_cli = QWidget()
        no_cli_layout = QVBoxLayout(self.page_no_cli)
        no_cli_layout.setContentsMargins(10, 20, 10, 20)
        no_cli_layout.setSpacing(14)
        no_cli_layout.setAlignment(Qt.AlignCenter)

        no_cli_icon = QLabel()
        no_cli_icon.setPixmap(QIcon(DISCONNECTED_ICON_PATH).pixmap(64, 64))
        no_cli_icon.setAlignment(Qt.AlignCenter)
        no_cli_layout.addWidget(no_cli_icon)

        self.no_cli_title = QLabel("")
        self.no_cli_title.setFont(QFont("Arial", 15, QFont.Bold))
        self.no_cli_title.setAlignment(Qt.AlignCenter)
        self.no_cli_title.setWordWrap(True)
        no_cli_layout.addWidget(self.no_cli_title)

        self.no_cli_desc = QLabel("")
        self.no_cli_desc.setFont(QFont("Arial", 10))
        self.no_cli_desc.setStyleSheet("color: #AAAAAA;")
        self.no_cli_desc.setAlignment(Qt.AlignCenter)
        self.no_cli_desc.setWordWrap(True)
        no_cli_layout.addWidget(self.no_cli_desc)

        self.no_cli_command = QLineEdit(CLI_INSTALL_COMMAND)
        self.no_cli_command.setReadOnly(True)
        self.no_cli_command.setCursorPosition(0)
        self.no_cli_command.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                color: #E2E8F0;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 6px 8px;
                font-family: monospace;
                font-size: 10px;
            }
        """)
        no_cli_layout.addWidget(self.no_cli_command)

        self.install_cli_btn = QPushButton("")
        self.install_cli_btn.setFont(QFont("Arial", 13, QFont.Bold))
        self.install_cli_btn.setFixedHeight(48)
        self.install_cli_btn.setCursor(Qt.PointingHandCursor)
        self.install_cli_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 24px;
            }
            QPushButton:hover { background-color: #43A047; }
            QPushButton:pressed { background-color: #388E3C; }
        """)
        self.install_cli_btn.clicked.connect(self.install_cli_in_terminal)
        no_cli_layout.addWidget(self.install_cli_btn)

        no_cli_buttons = QHBoxLayout()
        secondary_style = """
            QPushButton {
                background-color: #2D2D2D;
                color: #DDDDDD;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #383838; color: #FFFFFF; }
        """
        self.copy_cli_command_btn = QPushButton("")
        self.copy_cli_command_btn.setCursor(Qt.PointingHandCursor)
        self.copy_cli_command_btn.setStyleSheet(secondary_style)
        self.copy_cli_command_btn.clicked.connect(self.copy_cli_install_command)
        self.cli_page_btn = QPushButton("")
        self.cli_page_btn.setCursor(Qt.PointingHandCursor)
        self.cli_page_btn.setStyleSheet(secondary_style)
        self.cli_page_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CLI_PROJECT_URL)))
        no_cli_buttons.addWidget(self.copy_cli_command_btn)
        no_cli_buttons.addWidget(self.cli_page_btn)
        no_cli_layout.addLayout(no_cli_buttons)

        self.no_cli_status = QLabel("")
        self.no_cli_status.setStyleSheet("color: #81C784; font-size: 11px;")
        self.no_cli_status.setAlignment(Qt.AlignCenter)
        self.no_cli_status.setWordWrap(True)
        no_cli_layout.addWidget(self.no_cli_status)
        no_cli_layout.addStretch()

        self.main_stack.addWidget(self.page_no_cli)
        container_layout.addWidget(self.main_stack)
        main_layout.addWidget(self.container)
        
        # System Tray Icon setup (Direct 1-click toggle on Ubuntu GNOME)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(DISCONNECTED_ICON_PATH))
        self.tray_icon.setToolTip("AdGuard VPN")
        
        # Intercept AppIndicator single-click via aboutToShow signal
        self.tray_menu = QMenu(self)
        self.tray_menu.addAction("")
        self.tray_menu.aboutToShow.connect(self.on_tray_menu_triggered)
        self.tray_icon.setContextMenu(self.tray_menu)

        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def on_autostart_toggled(self, checked):
        set_system_autostart_enabled(checked)
        self.save_settings()

    def update_filter_tabs(self):
        active_style = """
            QPushButton {
                background-color: #3E3E3E;
                color: #FFFFFF;
                border: none;
                border-radius: 11px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: bold;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                border-radius: 11px;
                padding: 2px 10px;
                font-size: 10px;
            }
            QPushButton:hover { color: #DDDDDD; }
        """
        if self.filter_mode == "all":
            self.filter_all_btn.setStyleSheet(active_style)
            self.filter_fav_btn.setStyleSheet(inactive_style)
        else:
            self.filter_all_btn.setStyleSheet(inactive_style)
            self.filter_fav_btn.setStyleSheet(active_style)

    def set_filter_mode(self, mode):
        self.filter_mode = mode
        self.update_filter_tabs()
        if self.raw_locations:
            self.on_locations_updated(self.raw_locations)

    def update_account_chip_ui(self):
        if not hasattr(self, "account_chip"):
            return
        self.account_chip.setText("👤")
        if self.is_logged_in:
            tag = "PRO" if self.is_premium else "FREE"
            self.account_chip.setStyleSheet("""
                QPushButton {
                    background-color: #143521;
                    color: #00E676;
                    border: 1px solid #00E676;
                    border-radius: 6px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1D4B2F;
                    color: #FFFFFF;
                    border-color: #69F0AE;
                }
            """)
            email = getattr(self, "current_user_email", "")
            self.account_chip.setToolTip(f"{email}\n{tag}" if email else tag)
        else:
            self.account_chip.setStyleSheet("""
                QPushButton {
                    background-color: #381A1A;
                    color: #EF4444;
                    border: 1px solid #EF4444;
                    border-radius: 6px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #502323;
                    color: #FFFFFF;
                    border-color: #F87171;
                }
            """)
            self.account_chip.setToolTip(self.t("not_signed_in"))

    def on_account_chip_clicked(self):
        if not self.is_logged_in:
            self.main_stack.setCurrentIndex(1)
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #242424;
                color: white;
                border: 1px solid #383838;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
            }
        """)
        
        title_action = QAction(f"{self.current_user_email}", self)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        
        status_text = self.t("user_tier_premium") if self.is_premium else self.t("user_tier_free")
        if self.valid_until:
            status_text += f" ({self.t('until')} {self.valid_until})"
        tier_action = QAction(status_text, self)
        tier_action.setEnabled(False)
        menu.addAction(tier_action)
        
        menu.addSeparator()
        
        refresh_action = QAction(self.t("refresh_account"), self)
        refresh_action.triggered.connect(lambda: self.worker.request_action("refresh_auth"))
        menu.addAction(refresh_action)
        
        logout_action = QAction(self.t("logout"), self)
        logout_action.triggered.connect(self.confirm_logout)
        menu.addAction(logout_action)
        
        menu.addSeparator()
        
        quit_action = QAction(self.t("quit"), self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        
        menu.exec_(self.account_chip.mapToGlobal(QPoint(self.account_chip.width() - 170, self.account_chip.height() + 4)))

    def confirm_logout(self):
        ans = QMessageBox.question(
            self,
            self.t("logout_confirm_title"),
            self.t("logout_confirm_msg", email=self.current_user_email),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if ans == QMessageBox.Yes:
            self.worker.request_action("logout")

    def on_auth_updated(self, is_logged_in, email, is_premium, valid_until):
        self.is_logged_in = is_logged_in
        self.current_user_email = email
        self.is_premium = is_premium
        self.valid_until = valid_until
        self.update_account_chip_ui()
        
        if is_logged_in:
            self.main_stack.setCurrentIndex(0)
            self.login_progress_box.hide()
            self.start_login_btn.setEnabled(True)
        else:
            self.main_stack.setCurrentIndex(1)
            self.status_label.setText(
                f"<span style='color: #FF8A80; font-weight: bold;'>{self.t('not_signed_in')}</span>"
            )

    def start_browser_login(self):
        self.start_login_btn.setEnabled(False)
        self.login_progress_box.show()
        self.login_status_label.setText(self.t("starting_auth"))
        self.worker.request_action("login")

    def on_login_link_received(self, url):
        self.auth_link = url
        self.login_status_label.setText(self.t("browser_opened_status"))

    def reopen_auth_link(self):
        if self.auth_link:
            try:
                if not QDesktopServices.openUrl(QUrl(self.auth_link)):
                    webbrowser.open(self.auth_link)
            except Exception:
                webbrowser.open(self.auth_link)

    def copy_auth_link(self):
        if self.auth_link:
            QApplication.clipboard().setText(self.auth_link)
            self.login_status_label.setText(self.t("link_copied"))

    def cancel_browser_login(self):
        self.worker.request_action("cancel_login")
        self.login_progress_box.hide()
        self.start_login_btn.setEnabled(True)

    def on_login_finished(self, success, message):
        self.start_login_btn.setEnabled(True)
        if success:
            self.login_progress_box.hide()
            self.main_stack.setCurrentIndex(0)
        else:
            self.login_status_label.setText(f"<span style='color: #FF8A80;'>{self.t(message)}</span>")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Q:
            self.quit_app()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if hasattr(self, "locations_list") and obj == self.locations_list.viewport():
            if event.type() == QEvent.Wheel:
                self._show_scrollbar()
        if obj == self.search_input and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide_search()
                return True
        return super().eventFilter(obj, event)

    def _show_scrollbar(self):
        if hasattr(self, "locations_list"):
            self.locations_list.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE_VISIBLE)
            if hasattr(self, "_scrollbar_timer"):
                self._scrollbar_timer.start(800)

    def _hide_scrollbar(self):
        if hasattr(self, "locations_list"):
            self.locations_list.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE_HIDDEN)

    def toggle_search(self):
        if self.search_input.isVisible():
            self.hide_search()
        else:
            self.search_input.show()
            self.search_input.setFocus()

    def hide_search(self):
        self.search_input.clear()
        self.search_input.hide()

    def filter_locations(self, text):
        search_text = text.lower()
        for i in range(self.locations_list.count()):
            item = self.locations_list.item(i)
            if search_text in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def update_btn_style(self, is_connected):
        if is_connected:
            self.toggle_btn.setText(self.t("disconnect"))
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E53935;
                    color: white;
                    border: none;
                    border-radius: 24px;
                }
                QPushButton:hover { background-color: #F44336; }
                QPushButton:pressed { background-color: #D32F2F; }
                QPushButton:disabled { background-color: #555555; color: #888888; }
            """)
        else:
            self.toggle_btn.setText(self.t("connect"))
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 24px;
                }
                QPushButton:hover { background-color: #43A047; }
                QPushButton:pressed { background-color: #388E3C; }
                QPushButton:disabled { background-color: #555555; color: #888888; }
            """)

    def install_cli_in_terminal(self):
        if open_install_terminal():
            self.no_cli_status.setText(self.t("terminal_opened"))
        else:
            self.no_cli_status.setText(self.t("no_terminal_found"))

    def copy_cli_install_command(self):
        QApplication.clipboard().setText(CLI_INSTALL_COMMAND)
        self.no_cli_status.setText(self.t("command_copied"))

    def on_status_updated(self, state, location):
        """Mirror `adguardvpn-cli status` in the window and the tray."""
        if state == "cli_missing":
            if self.main_stack.currentIndex() != 2:
                self.main_stack.setCurrentIndex(2)
                self.no_cli_status.setText("")
        elif self.main_stack.currentIndex() == 2:
            # The CLI appeared (install finished): back to the normal pages;
            # the next `license` answer decides between main and sign-in.
            self.main_stack.setCurrentIndex(0 if self.is_logged_in else 1)
            self.worker.request_action("refresh_auth")
            self.worker.request_action("refresh_locations")
        prev_state = self.connection_state
        prev_location = self.current_location_name
        self.connection_state = state
        self.is_connected = state == "connected"
        if state == "connected":
            self.current_location_name = self.pretty_location(location)
        elif state == "disconnected":
            self.current_location_name = ""
        self.render_status()

        if state in ("connected", "disconnected") and prev_state != "unknown":
            if state != prev_state or self.current_location_name != prev_location:
                self.show_ip_refreshing()
                QTimer.singleShot(1500, self.refresh_external_ip)
        elif state in ("connected", "disconnected") and prev_state == "unknown":
            QTimer.singleShot(300, self.refresh_external_ip)

    def pretty_location(self, cli_location):
        """CLI prints the city upper-cased ("DENVER"); use the list's spelling."""
        if not cli_location:
            return ""
        low = cli_location.lower()
        for loc in self.raw_locations:
            city = loc.get("city", "")
            if city and city.lower() == low:
                return city
        for loc in self.raw_locations:
            country = loc.get("country", "")
            if country and country.lower() == low:
                return country
        return cli_location.title() if cli_location.isupper() else cli_location

    def ping_for_location(self, name):
        low = name.lower()
        for loc in self.raw_locations:
            if loc.get("city", "").lower() == low or loc.get("country", "").lower() == low:
                return loc.get("ping", "")
        return ""

    def render_status(self):
        state = self.connection_state
        loc = self.current_location_name
        if state == "connected":
            ping = self.ping_for_location(loc)
            ping_html = f" <span style='font-size: 11pt; color: #81C784;'>[{ping} ms]</span>" if ping.isdigit() else ""
            display_text = (
                f"<div style='text-align: center;'>"
                f"<span style='color: #4CAF50; font-size: 11pt; font-weight: bold;'>{self.t('connected_pill')}</span><br/>"
                f"<span style='font-size: 16pt; color: #FFFFFF; font-weight: bold;'>{loc}</span>"
                f"{ping_html}"
                f"</div>"
            )
            self.tray_icon.setToolTip(self.t("tray_tooltip_connected", location=loc))
            self.toggle_btn.setEnabled(True)
        elif state == "connecting":
            display_text = (
                f"<div style='text-align: center;'>"
                f"<span style='color: #FFB74D; font-size: 11pt; font-weight: bold;'>{self.t('connecting_pill')}</span><br/>"
                f"<span style='font-size: 15pt; color: #FFFFFF; font-weight: bold;'>{loc or self.t('connecting')}</span>"
                f"</div>"
            )
            self.tray_icon.setToolTip(f"AdGuard VPN: {self.t('connecting')}")
            self.toggle_btn.setEnabled(False)
        elif state == "disconnected":
            display_text = (
                f"<div style='text-align: center;'>"
                f"<span style='color: #757575; font-size: 11pt; font-weight: bold;'>{self.t('disconnected_pill')}</span><br/>"
                f"<span style='font-size: 15pt; color: #FFFFFF; font-weight: bold;'>{self.t('not_protected')}</span>"
                f"</div>"
            )
            self.tray_icon.setToolTip(self.t("tray_tooltip_disconnected"))
            self.toggle_btn.setEnabled(True)
        elif state == "cli_missing":
            display_text = (
                f"<div style='text-align: center;'>"
                f"<span style='font-size: 11pt; color: #FF8A80; font-weight: bold;'>{self.t('cli_missing')}</span></div>"
            )
            self.tray_icon.setToolTip(f"AdGuard VPN: {self.t('cli_missing')}")
            self.toggle_btn.setEnabled(False)
        else:
            display_text = (
                f"<div style='text-align: center;'>"
                f"<span style='font-size: 13pt; color: #FFFFFF;'>{self.t('status_unknown')}</span></div>"
            )
            self.tray_icon.setToolTip(f"AdGuard VPN: {self.t('status_unknown')}")
            self.toggle_btn.setEnabled(True)

        self.status_label.setText(display_text)
        self.update_btn_style(self.is_connected)
        icon_path = CONNECTED_ICON_PATH if self.is_connected else DISCONNECTED_ICON_PATH
        self.tray_icon.setIcon(QIcon(icon_path))

    def show_ip_refreshing(self):
        if hasattr(self, "ip_click_btn"):
            self.ip_click_btn.setIcon(QIcon(LOCK_ICON_PATH))
            self.ip_click_btn.setText("...")
        if hasattr(self, "ip_ticker"):
            self.ip_ticker.setText(self.t("refreshing_ip"))

    def copy_ip_to_clipboard(self):
        ip = getattr(self, "current_ip_str", "").strip()
        if not ip:
            return
        QApplication.clipboard().setText(ip)
        self.ip_click_btn.setIcon(QIcon())
        self.ip_click_btn.setText(f"✓ {self.t('copied')}")
        self.ip_click_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #00E676;
                border: none;
                font-size: 13.5px;
                font-weight: bold;
                text-align: left;
                padding: 0;
            }
        """)
        QTimer.singleShot(1200, self.restore_ip_display)

    def restore_ip_display(self):
        ip = getattr(self, "current_ip_str", "").strip()
        self.ip_click_btn.setIcon(QIcon(LOCK_ICON_PATH))
        if ip:
            self.ip_click_btn.setText(ip)
        else:
            self.ip_click_btn.setText("—")
        self.ip_click_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #E2E8F0;
                border: none;
                font-size: 13.5px;
                font-weight: bold;
                text-align: left;
                padding: 0;
            }
            QPushButton:hover {
                color: #00E676;
            }
        """)

    def refresh_external_ip(self):
        if self.external_ip_refresh_in_progress:
            return
        self.external_ip_refresh_in_progress = True
        self.external_ip_refresh_btn.setEnabled(False)
        self.ip_click_btn.setIcon(QIcon(LOCK_ICON_PATH))
        self.ip_click_btn.setText("...")
        self.ip_ticker.setText(self.t("checking_ip"))
        self.worker.request_action("refresh_external_ip")

    def on_external_ip_updated(self, ip_address, location, success):
        self.external_ip_refresh_in_progress = False
        self.external_ip_refresh_btn.setEnabled(True)
        if success:
            self.current_ip_str = ip_address.strip()
            self.ip_click_btn.setIcon(QIcon(LOCK_ICON_PATH))
            self.ip_click_btn.setText(self.current_ip_str)
            self.ip_click_btn.setEnabled(True)
            self.ip_ticker.setText(location.strip())
        else:
            self.current_ip_str = ""
            self.ip_click_btn.setIcon(QIcon(LOCK_ICON_PATH))
            self.ip_click_btn.setText("—")
            self.ip_click_btn.setEnabled(False)
            self.ip_ticker.setText(self.t("ip_unavailable"))

    def load_favorites(self):
        if os.path.exists(FAVORITES_FILE):
            try:
                with open(FAVORITES_FILE, 'r', encoding="utf-8") as f:
                    self.favorites = set(json.load(f))
            except Exception:
                pass

    def save_favorites(self):
        try:
            with open(FAVORITES_FILE, 'w', encoding="utf-8") as f:
                json.dump(list(self.favorites), f, ensure_ascii=False)
        except Exception:
            pass

    def load_cached_locations(self):
        if os.path.exists(LOCATIONS_CACHE_FILE):
            try:
                with open(LOCATIONS_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if isinstance(cached, list) and cached:
                        self.on_locations_updated(cached)
            except Exception:
                pass

    def show_context_menu(self, position):
        item = self.locations_list.itemAt(position)
        if item:
            identifier = item.data(Qt.UserRole)
            menu = QMenu()
            menu.setStyleSheet("""
                QMenu { background-color: #242424; color: white; border: 1px solid #383838; }
                QMenu::item:selected { background-color: #4CAF50; }
            """)
            connect_action = QAction(self.t("connect_to_this"), self)
            connect_action.triggered.connect(lambda: self.connect_to_location(item))
            menu.addAction(connect_action)
            menu.addSeparator()
            fav_label = self.t("remove_favorite") if identifier in self.favorites else self.t("add_favorite")
            toggle_action = QAction(fav_label, self)
            toggle_action.triggered.connect(lambda: self.toggle_favorite(identifier))
            menu.addAction(toggle_action)
            menu.exec_(self.locations_list.mapToGlobal(position))

    def toggle_favorite(self, identifier):
        if identifier in self.favorites:
            self.favorites.remove(identifier)
        else:
            self.favorites.add(identifier)
        self.save_favorites()
        if self.raw_locations:
            self.on_locations_updated(self.raw_locations)

    def on_locations_updated(self, locations):
        self.raw_locations = locations
        self.locations_list.clear()
        parsed_items = []
        fav_count = 0
        
        for loc in locations:
            iso = loc.get("iso", "")
            country = loc.get("country", "")
            city = loc.get("city", "")
            ping = loc.get("ping", "")
            
            has_ping = ping.isdigit()
            ping_val = int(ping) if has_ping else 999999
            
            identifier = city if city else country
            display_title = f"{city}, {country}" if city and country else (city or country)
            
            is_fav = identifier in self.favorites or iso in self.favorites
            if is_fav:
                fav_count += 1
                
            if self.filter_mode == "fav" and not is_fav:
                continue

            star = "★ " if is_fav else "  "
            if getattr(self, "refresh_in_progress", False):
                ping_text = ""
            else:
                ping_text = f"  [{ping} ms]" if has_ping else ""
                
            display_text = f"{star}{display_title}{ping_text}"
            
            item = QListWidgetItem(display_text)
            if is_fav:
                item.setForeground(QColor("#FFD54F"))
            item.setData(Qt.UserRole, identifier)
            
            if self.filter_mode == "fav":
                # In favorites mode, sort strictly by Country, then City
                sort_key = (country.lower(), city.lower(), ping_val)
            else:
                # In All mode, sort strictly by Ping (lowest to highest)
                sort_key = (ping_val, country.lower(), city.lower())
            
            parsed_items.append((sort_key, item))
                
        parsed_items.sort(key=lambda x: x[0])
        
        for _, item in parsed_items:
            self.locations_list.addItem(item)

        if locations:
            self.loc_label.setText(f"{self.t('locations')} ({len(locations)})")
            self.filter_fav_btn.setText(f"{self.t('favorites')} ({fav_count})")
        if self.connection_state == "connected" and self.current_location_name:
            self.current_location_name = self.pretty_location(self.current_location_name)
            self.render_status()

    def refresh_locations(self):
        self.refresh_in_progress = True
        self.refresh_btn.start_rotation()
        self.refresh_btn.setToolTip(self.t("refreshing_locations_tooltip"))
        if hasattr(self, "raw_locations") and self.raw_locations:
            self.locations_list.clear()
            for loc in self.raw_locations:
                country = loc.get("country", "")
                city = loc.get("city", "")
                iso = loc.get("iso", "")
                identifier = city if city else country
                display_title = f"{city}, {country}" if city and country else (city or country)
                is_fav = identifier in self.favorites or iso in self.favorites
                if self.filter_mode == "fav" and not is_fav:
                    continue
                star = "★ " if is_fav else "  "
                item = QListWidgetItem(f"{star}{display_title}")
                if is_fav:
                    item.setForeground(QColor("#FFD54F"))
                item.setData(Qt.UserRole, identifier)
                self.locations_list.addItem(item)
        self.worker.request_action("refresh_locations")

    def restore_loc_label_text(self):
        if not getattr(self, "refresh_in_progress", False):
            cnt = len(self.raw_locations) if hasattr(self, "raw_locations") and self.raw_locations else 0
            self.loc_label.setText(f"{self.t('locations')} ({cnt})" if cnt else self.t("locations"))
            self.loc_label.setStyleSheet("color: #CCCCCC; font-size: 11px; font-weight: bold;")

    def on_locations_refresh_finished(self, success, count):
        self.refresh_in_progress = False
        self.refresh_btn.stop_rotation()
        if success:
            self.refresh_btn.setToolTip(self.t("updated_locations_tooltip", count=count))
            if hasattr(self, "raw_locations") and self.raw_locations:
                self.on_locations_updated(self.raw_locations)
            else:
                self.restore_loc_label_text()
        else:
            self.refresh_btn.setToolTip(self.t("no_connection"))
            self.loc_label.setText(f"⚠️ {self.t('no_connection')}")
            self.loc_label.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
            if hasattr(self, "raw_locations") and self.raw_locations:
                self.on_locations_updated(self.raw_locations)
            QTimer.singleShot(4000, self.restore_loc_label_text)

    def show_exclusions(self):
        self.exclusions_dialog = QDialog(self)
        self.exclusions_dialog.setWindowTitle(self.t("exclusions_dialog_title"))
        self.exclusions_dialog.setFixedSize(350, 410)
        self.exclusions_dialog.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: white; }
            QLabel { color: white; }
            QListWidget { background-color: #262626; border: 1px solid #333333; border-radius: 6px; color: white; }
            QListWidget::item { padding: 7px; border-bottom: 1px solid #333333; }
            QLineEdit { background-color: #2C2C2C; color: white; border: 1px solid #444444; border-radius: 4px; padding: 6px; }
            QPushButton { background-color: #333333; color: white; border: none; border-radius: 4px; padding: 6px 12px; }
            QPushButton:hover { background-color: #4CAF50; }
            QPushButton:disabled { background-color: #555555; color: #888888; }
        """)

        layout = QVBoxLayout(self.exclusions_dialog)
        self.exclusions_info = QLabel(self.exclusions_info_text())
        self.exclusions_info.setWordWrap(True)
        self.exclusions_info.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        layout.addWidget(self.exclusions_info)

        self.exclusions_list = QListWidget()
        layout.addWidget(self.exclusions_list)

        self.exclusions_status = QLabel(self.t("exclusions_loading"))
        self.exclusions_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.exclusions_status)

        self.exclusion_input = QLineEdit()
        self.exclusion_input.setPlaceholderText(self.t("exclusions_input_placeholder"))
        self.exclusion_input.returnPressed.connect(self.add_exclusions)
        layout.addWidget(self.exclusion_input)

        controls = QHBoxLayout()
        add_btn = QPushButton(self.t("add"))
        add_btn.clicked.connect(self.add_exclusions)
        remove_btn = QPushButton(self.t("remove"))
        remove_btn.clicked.connect(self.remove_selected_exclusion)
        refresh_btn = QPushButton("↻")
        refresh_btn.setToolTip(self.t("refresh"))
        refresh_btn.clicked.connect(self.refresh_exclusions)
        clear_btn = QPushButton(self.t("clear_all"))
        clear_btn.clicked.connect(self.clear_exclusions)
        controls.addWidget(add_btn)
        controls.addWidget(remove_btn)
        controls.addWidget(refresh_btn)
        controls.addWidget(clear_btn)
        layout.addLayout(controls)

        self.refresh_exclusions()
        self.exclusions_dialog.exec_()
        self.exclusions_dialog = None

    def refresh_exclusions(self):
        if hasattr(self, "exclusions_status"):
            self.exclusions_status.setText(self.t("exclusions_loading"))
        self.worker.request_action("refresh_exclusions")

    def exclusions_info_text(self):
        if self.exclusions_mode == "selective":
            return self.t("exclusions_mode_selective")
        if self.exclusions_mode == "general":
            return self.t("exclusions_mode_general")
        return self.t("exclusions_dialog_info")

    def on_exclusions_updated(self, mode, exclusions, success):
        if success:
            self.exclusions_mode = mode
        self.exclusions_count = len(exclusions) if success else 0
        self.exclusions_btn.setText(f"{self.t('exclusions_btn')} ({self.exclusions_count})")
        
        if not getattr(self, "exclusions_dialog", None):
            return
        if not success:
            self.exclusions_status.setText(self.t("exclusions_error"))
            return

        self.exclusions_info.setText(self.exclusions_info_text())
        self.exclusions_list.clear()
        self.exclusions_list.addItems(exclusions)
        self.exclusions_status.setText(
            self.t("no_exclusions") if not exclusions else self.t("exclusions_count", count=len(exclusions))
        )

    def on_exclusions_action_finished(self, action, success):
        if not getattr(self, "exclusions_dialog", None):
            return
        if success:
            if action == "add":
                self.exclusion_input.clear()
            self.exclusions_status.setText(self.t("exclusions_updating"))
        else:
            self.exclusions_status.setText(self.t("exclusions_error"))

    def add_exclusions(self):
        exclusions = self.exclusion_input.text().strip()
        if exclusions:
            self.worker.request_action(f"add_exclusions:{exclusions}")

    def remove_selected_exclusion(self):
        item = self.exclusions_list.currentItem()
        if item:
            self.worker.request_action(f"remove_exclusion:{item.text()}")

    def clear_exclusions(self):
        confirmation = QMessageBox.question(
            self.exclusions_dialog,
            self.t("clear_all"),
            self.t("clear_exclusions_confirm"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmation == QMessageBox.Yes:
            self.worker.request_action("clear_exclusions")

    def toggle_connection(self):
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.setText(self.t("working"))
        if self.is_connected:
            self.worker.request_action("disconnect")
        else:
            selected = self.locations_list.currentItem()
            if selected:
                identifier = selected.data(Qt.UserRole)
                self.worker.request_action(f"connect_to:{identifier}")
            else:
                self.worker.request_action("connect")

    def connect_to_location(self, item):
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.setText(self.t("connecting"))
        self.show_ip_refreshing()
        identifier = item.data(Qt.UserRole)
        self.worker.request_action(f"connect_to:{identifier}")
        self.hide_search()

    def on_action_finished(self, action):
        if action == "connect":
            QTimer.singleShot(1500, self.refresh_external_ip)

    def on_tray_menu_triggered(self):
        # Close the DBusMenu immediately so GNOME Shell doesn't render its popup.
        # Map our window a moment later: while the shell's menu is still open
        # the window manager refuses to focus a new window, and a window that
        # never became active cannot notice losing focus (no auto-hide).
        QTimer.singleShot(0, self.tray_menu.close)
        QTimer.singleShot(150, self.toggle_tray_window)

    def tray_activated(self, reason):
        self.toggle_tray_window()

    def toggle_tray_window(self):
        now = time.time()

        # Debounce rapid activations
        if now - getattr(self, "_last_tray_toggle_time", 0) < 0.25:
            return

        # If window just closed due to losing focus when clicking the tray icon, do not re-open
        if now - getattr(self, "_last_focus_lost_time", 0) < 0.25:
            return

        self._last_tray_toggle_time = now

        if self.isVisible():
            self.hide()
        else:
            self.show_window(anchor=self.tray_anchor())

    def tray_anchor(self):
        """Best available guess of where the tray icon is, or None.

        1. XEmbed trays (Xfce, MATE, LXQt on X11) report the icon rectangle.
        2. On a native X11 session the pointer sits on the icon when it is
           clicked, so the cursor position is a good anchor.
        3. On Wayland (even through XWayland) neither is known: StatusNotifier
           hosts pass the click position over D-Bus, but Qt drops it, and the
           pointer position an X client sees is stale. Return None and let
           compute_popup_position() fall back to the panel's right end.
        """
        geo = self.tray_icon.geometry()
        if geo.isValid() and not geo.isEmpty():
            return geo.center()
        if not is_wayland_session():
            pos = QCursor.pos()
            if pos.x() > 0 or pos.y() > 0:
                return pos
        return None

    def show_window(self, anchor=None):
        if anchor is None:
            anchor = self.last_anchor
        else:
            self.last_anchor = anchor

        screen = None
        if anchor is not None:
            screen = QApplication.screenAt(anchor)
        if screen is None and not is_wayland_session():
            screen = QApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QApplication.primaryScreen()

        pos = compute_popup_position(self.size(), screen.availableGeometry(), anchor)

        self._is_active = False
        self._just_shown_time = time.time()

        self.move(pos)
        self.show()
        self.activateWindow()
        self.raise_()
        # Some window managers re-place a window right after map; re-assert once.
        QTimer.singleShot(50, lambda: self.move(pos))
        QTimer.singleShot(300, self.ensure_active)

    def ensure_active(self):
        """Second activation request: the first one can be refused while the
        panel's own popup is still closing. Being active is what makes the
        later focus loss (click elsewhere) hide the window."""
        if self.isVisible() and not self.isActiveWindow():
            self.activateWindow()
            self.raise_()

    def paintEvent(self, event):
        # Soft shadow around the card: a few translucent rounded strokes, no
        # blur effect (QGraphicsDropShadowEffect re-rendered the whole card on
        # every repaint and cost ~30% of a core while the ticker scrolled).
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        card = self.container.geometry()
        for i in range(8, 0, -1):
            painter.setPen(QColor(0, 0, 0, 10 + (8 - i) * 6))
            rect = QRectF(card).adjusted(-i, -i + 2, i, i + 2)
            painter.drawRoundedRect(rect, 14 + i, 14 + i)
        super().paintEvent(event)

    def changeEvent(self, event):
        if event.type() == event.ActivationChange:
            now = time.time()
            if self.isActiveWindow():
                self._is_active = True
            elif getattr(self, "_is_active", False):
                self._is_active = False
                self._last_focus_lost_time = now
                if now - getattr(self, "_just_shown_time", 0) > 0.3:
                    if not (QApplication.activeModalWidget() or QApplication.activePopupWidget() or getattr(self, "exclusions_dialog", None)):
                        self.hide()
        super().changeEvent(event)

    def hideEvent(self, event):
        self.hide_search()
        super().hideEvent(event)

    def quit_app(self):
        self.worker.stop()
        self.worker.wait(3000)
        QApplication.quit()


if __name__ == '__main__':
    # 1. Quick IPC check first: if already running, trigger show and exit
    if send_ipc_message("show"):
        print("AdGuard GUI is already running. Brought window to front.")
        sys.exit(0)

    # 2. Kernel-level file lock to prevent duplicate instances at system boot
    import fcntl
    lock_file_path = os.path.expanduser("~/.config/adguard-gui.lock")
    try:
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, IOError):
        time.sleep(0.5)
        send_ipc_message("show")
        sys.exit(0)

    start_minimized = "--minimized" in sys.argv or "--tray" in sys.argv

    # Wayland lets no application position its own top-level windows, so a
    # tray popup would land wherever the compositor puts it (GNOME: screen
    # centre). Through XWayland (xcb) move() works on every compositor. Only
    # when X is not available at all do we leave Qt on native Wayland.
    if not os.environ.get("QT_QPA_PLATFORM") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("AdGuard VPN")
    app.setDesktopFileName("adguard")
    
    gui = AdGuardVPNApp(start_minimized=start_minimized)
    
    sys.exit(app.exec_())
