# AdGuard VPN GUI for Linux

A tray window on top of the official `adguardvpn-cli`. It shows whether the
VPN is up, which city you are connected to, the ping and your public IP, and
connects or disconnects with one click. It has no logic of its own: every
button runs the command you would otherwise type in a terminal.

[Русская версия](README.md)

![AdGuard VPN GUI window: connected to Denver, list of locations with pings](docs/screenshot.png)

Project page: https://iresultman.github.io/adguardvpn-Linux-gui/

## Why

AdGuard VPN has no desktop app for Linux, only a CLI. I do not want to
remember commands or keep a terminal open just to learn whether the VPN is
working. Work without a VPN is impossible for me, so its state has to be
visible at all times, like the battery level: one icon in the tray, one window
on click. That is the whole reason this tool exists.

## What it shows and does

- Connection state and the city the tunnel goes through, with ping.
- Public IP and its geolocation. Click the IP to copy it.
- 80+ locations with pings, sorted by ping, with search and favourites.
- Connect to a location by double click or with the button.
- Site exclusions: view, add, remove, and the current mode (GENERAL or
  SELECTIVE).
- Sign in through the browser and sign out, plan and subscription expiry.
- Autostart on login, Russian and English interface.
- The tray icon changes with the state; its tooltip names the city.

## How it works

The GUI contains no VPN logic. A background thread runs
`adguardvpn-cli status` every 2 seconds and shows the answer. Everything else
is a CLI call too:

| Action in the window | Command |
|---|---|
| State and city, every 2 s | `adguardvpn-cli status` |
| Account and plan, every 30 s | `adguardvpn-cli license` |
| Locations and pings | `adguardvpn-cli list-locations` |
| "Connect" button | `adguardvpn-cli connect -y` |
| Double click on a location | `adguardvpn-cli connect -l "<city>" -y` |
| "Disconnect" button | `adguardvpn-cli disconnect` |
| Sign in and out | `adguardvpn-cli login`, `adguardvpn-cli logout` |
| Site exclusions | `adguardvpn-cli site-exclusions show / add / remove / clear` |

The only thing that does not go through the CLI is the public IP: it is
fetched over HTTPS from `ipwho.is`, falling back to `ipapi.co`.

If the VPN was brought up some other way (for example by a systemd unit at
boot), the window shows that too: it reads the state of the same daemon.

## Install

Requirements: Linux, Python 3.8+ with the `venv` module, an installed and
signed-in [AdGuard VPN CLI](https://github.com/AdguardTeam/AdGuardVPNCLI),
and a tray in your panel.

```bash
git clone https://github.com/iResultMan/adguardvpn-Linux-gui.git
cd adguardvpn-Linux-gui
./install.sh
```

The script creates a `venv` with PyQt5, a menu entry, icons and an autostart
entry. Run it by hand:

```bash
venv/bin/python AdGuard.py
```

`--minimized` starts straight into the tray (this is what autostart does).

If `adguardvpn-cli` is not installed, the window says so and shows the
official install command. "Install in a terminal" opens a terminal with that
command: you answer the installer's questions and type the administrator
password yourself, nothing happens behind the terminal's back. When the
install finishes, the window switches to the sign-in page.

**GNOME.** GNOME Shell has no tray; install the AppIndicator extension,
package `gnome-shell-extension-appindicator` on Ubuntu, Debian and Fedora.
Without a tray the window is simply shown on start.

**KDE, Xfce, Cinnamon, MATE, LXQt** work out of the box.

## Reference

| What | How |
|---|---|
| Show or hide the window | click the tray icon, or launch the program again |
| Hide the window | `Esc`, the cross, or a click outside the window |
| Quit | `Ctrl+Q` or the account menu (person icon) |
| Connect to a location | double click a row, or select it and press "Connect" |
| Favourites | right click a location |
| Search locations | the magnifier button, `Esc` closes |
| Refresh pings | the arrow button next to the magnifier |
| Language | the RU / EN switch in the header |
| Autostart | the checkbox at the bottom |

Files in your home directory:

| File | Holds |
|---|---|
| `~/.config/adguard-gui-settings.json` | language |
| `~/.config/adguard-gui-favorites.json` | favourite locations |
| `~/.config/adguard-locations-cache.json` | cached locations for instant start |
| `~/.config/autostart/adguard.desktop` | autostart |

### Connect at boot

Optional. `systemd/adguardvpn.service.example` is the system unit the author
uses so that the VPN is up before anyone logs in. Instructions are inside the
file. The window sees that connection like any other.

## Limitations

- **Window position on Wayland.** Wayland tells applications neither where
  their tray icon is nor where the pointer is. So on Wayland the window opens
  at the right end of the top panel, where indicators live in every desktop,
  rather than exactly under the icon. On X11 it opens under the cursor. For
  that the program runs through XWayland when available.
- Linux only. AdGuard has its own apps for macOS and Windows.
- The first `connect` may ask to set up tunnel permissions (CAP_NET_ADMIN).
  Do it once in a terminal: `adguardvpn-cli connect`.

## Development

```
AdGuard.py        the whole application, one file
assets/           window and tray icons
tests/            tests for the CLI output parsers and window placement
tools/            installs icons into the hicolor theme
systemd/          example unit for connecting at boot
docs/             GitHub Pages site
```

The tests need no display:

```bash
QT_QPA_PLATFORM=offscreen venv/bin/python -m unittest discover -s tests -v
```

They are built on real output of AdGuard VPN CLI 1.7.12. If a new CLI version
changes the format, the tests fail before the window does.

The project page is served from the `docs/` folder of `main`.

## License

MIT. AdGuard and AdGuard VPN are trademarks of AdGuard Software Ltd. This
project is independent and not affiliated with AdGuard.
