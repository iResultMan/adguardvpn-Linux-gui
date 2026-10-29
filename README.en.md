# AdGuard VPN GUI for Linux

A tray icon and a settings window on top of the official `adguardvpn-cli`.
Shows whether the VPN is up, which city you are connected to, the ping and
your public IP, and connects or disconnects with one click. It has no logic
of its own: every action runs the command you would otherwise type.

[Русская версия](README.md)

![AdGuard VPN GUI window: connected to Denver, list of locations with pings](docs/screenshot.png)

Project page: https://iresultman.github.io/adguardvpn-Linux-gui/

## Why

AdGuard VPN has no desktop app for Linux, only a CLI. I do not want to
remember commands or keep a terminal open just to learn whether the VPN is
working. Work without a VPN is impossible for me, so its state has to be
visible at all times, like the battery level: one icon in the tray, one
menu on click. That is the whole reason this tool exists.

## What it is made of

Two programs, each with its own job.

**The tray daemon** `adguardvpn-tray`: 2 MB on disk, 4 MB of memory, 0% CPU.
Written in Rust, opens no network connection; the only things it does
outside its own process are running `adguardvpn-cli`, `curl` for the public
IP, and the settings window. Its menu is drawn by the panel itself:

- Connected: Denver
- IP 169.150.231.81 · Denver, Colorado, United States
- Connect / Disconnect
- Settings
- Quit

**The settings window** in Python and PyQt5. Opened with "Settings" in the icon menu or from
the application list, closed with the X, and gone from memory after that.
Everything else lives there: the big status, 80+ locations with pings,
search and favourites, site exclusions with drag-and-drop of a list file,
sign-in, autostart, Russian and English, and installing the CLI when it is
missing.

## How it works

Neither process contains VPN logic. Both run `adguardvpn-cli status` and
show the answer. The daemon has no polling timer; it re-reads the state on
events only: the CLI creates and removes `vpn.socket` in its data directory
when the service starts and stops (inotify), the kernel announces the tunnel
interface (netlink), plus menu opening and the user's own actions. Idle, it
runs nothing. The window polls every 2 seconds while it is open. Everything
else is a CLI call too:

| Action | Command |
|---|---|
| State and city | `adguardvpn-cli status` |
| Account and plan (window, every 30 s) | `adguardvpn-cli license` |
| Locations and pings (window) | `adguardvpn-cli list-locations` |
| "Connect" | `adguardvpn-cli connect -y` |
| Double click on a location (window) | `adguardvpn-cli connect -l "<city>" -y` |
| "Disconnect" | `adguardvpn-cli disconnect` |
| Sign in and out (window) | `adguardvpn-cli login`, `adguardvpn-cli logout` |
| Site exclusions (window) | `adguardvpn-cli site-exclusions show / add / remove / clear` |

The only thing that does not go through the CLI is the public IP, fetched
from `ipwho.is` with `ipapi.co` as a fallback: the daemon runs `curl` for
it, the window uses HTTPS from Python.

If the VPN was brought up some other way, for example by a systemd unit at
boot, the icon shows that too: both processes read the state of the same
CLI daemon.

## Install

Requirements: Linux with a tray, Python 3.8+ with the `venv` module, an
installed and signed-in [AdGuard VPN CLI](https://github.com/AdguardTeam/AdGuardVPNCLI).
Building the daemon from source needs `cargo`; without it the installer
downloads the release binary for x86_64 or aarch64 and verifies its checksum.

```bash
git clone https://github.com/iResultMan/adguardvpn-Linux-gui.git
cd adguardvpn-Linux-gui
./install.sh
```

The script puts the daemon in `bin/`, creates a `venv` with PyQt5, a menu
entry for the window and an autostart entry for the daemon. By hand:

```bash
bin/adguardvpn-tray &
venv/bin/python AdGuard.py
```

If `adguardvpn-cli` is not installed, the window says so and shows the
official install command. "Install in a terminal" opens a terminal with that
command: you answer the installer's questions and type the administrator
password yourself.

**GNOME.** GNOME Shell has no tray; install the AppIndicator extension,
package `gnome-shell-extension-appindicator` on Ubuntu, Debian and Fedora.
Without a tray the daemon opens the window after a minute and exits.

**KDE, Xfce, Cinnamon, MATE, LXQt** work out of the box.

## Reference

| What | How |
|---|---|
| Daemon menu | left or right click on the icon (on KDE a left click opens the window directly) |
| Open the window | "Settings" in the menu, or the application list |
| Close the window | `Esc`, the cross, or the title bar close button |
| Quit the daemon | "Quit" in the icon menu |
| Connect to a location | double click a row in the window, or select it and press "Connect" |
| Favourites | right click a location in the window |
| Search locations | the magnifier button, `Esc` closes the search |
| Exclusions from a file | drop a text file with domains onto the exclusions list |
| Language | the RU / EN switch in the window; the daemon picks it up on the next status change |
| Autostart | the checkbox at the bottom of the window; it controls the daemon |

Files in your home directory:

| File | Holds |
|---|---|
| `~/.config/adguard-gui-settings.json` | language |
| `~/.config/adguard-gui-favorites.json` | favourite locations |
| `~/.config/adguard-locations-cache.json` | cached locations for an instant window start |
| `~/.config/autostart/adguard.desktop` | daemon autostart |
| `$XDG_RUNTIME_DIR/adguardvpn-window.log` | output of a window started from the menu |

### Connect at boot

Optional. `systemd/adguardvpn.service.example` is the system unit the author
uses so that the VPN is up before anyone logs in. Instructions are inside.

## Trust

The daemon is a binary, and there are three ways to know what is in it:

1. The source is `daemon/src/main.rs`, about 500 lines, a 15-minute read.
2. Release files are built by GitHub Actions from that source
   (`.github/workflows/daemon.yml`) next to a `SHA256SUMS` the installer
   checks. The same `cargo build --release` gives the same file locally.
3. The daemon opens no network connections. Verifiable by reading the code:
   there is no networking library in it.

## Limitations

- Linux only. AdGuard has its own apps for macOS and Windows.
- No city label next to the panel icon yet; the icon colour, the tooltip and
  the first menu line carry the state.
- The first `connect` may ask to set up tunnel permissions (CAP_NET_ADMIN).
  Do it once in a terminal: `adguardvpn-cli connect`.

## Development

```
daemon/           tray daemon in Rust (ksni), one file
AdGuard.py        settings window, one file
assets/           window and tray icons
tests/            tests for the CLI output parsers and install helpers
tools/            installs icons into the hicolor theme
systemd/          example unit for connecting at boot
docs/             GitHub Pages site
.github/          daemon build and release upload
```

Tests:

```bash
QT_QPA_PLATFORM=offscreen venv/bin/python -m unittest discover -s tests -v
cargo test --manifest-path daemon/Cargo.toml
```

They are built on real output of AdGuard VPN CLI 1.7.12. If a new CLI
version changes the format, the tests fail before the icon does.

The project page is served from the `docs/` folder of `main`.

## License

MIT, see [LICENSE](LICENSE). AdGuard and AdGuard VPN are trademarks of
AdGuard Software Ltd. This project is independent and not affiliated with
AdGuard.
