"""Unit tests for the pure functions that translate adguardvpn-cli output.

Fixtures are verbatim captures from AdGuard VPN CLI v1.7.12 (including ANSI
bold escapes), so a CLI format change shows up here before it shows up in
the window.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRect, QSize, QPoint  # noqa: E402

import AdGuard  # noqa: E402

STATUS_CONNECTED = (
    "Connected to \x1b[1mDENVER\x1b[0m in \x1b[1mTUN\x1b[0m mode, running on \x1b[1mtun0\x1b[0m\n"
    "You can disconnect by running `adguardvpn-cli disconnect`"
)
STATUS_DISCONNECTED = "VPN is disconnected"
STATUS_STARTING = "VPN is starting"
STATUS_CONNECTING = "Connecting to \x1b[1mNEW YORK\x1b[0m in \x1b[1mTUN\x1b[0m mode"
STATUS_LOGGED_OUT = "You are not logged in"

LICENSE_PREMIUM = (
    "Logged in as \x1b[1mmedush@example.com\x1b[0m\n"
    "You are using the \x1b[1mPREMIUM\x1b[0m version\n"
    "Up to \x1b[1m10\x1b[0m devices simultaneously\n"
    "Your subscription is valid until 2027-06-18"
)
LICENSE_LOGGED_OUT = "You are not logged in"

LOCATIONS = (
    "\x1b[1mISO   COUNTRY              CITY                           PING ESTIMATE\n"
    "\x1b[0mSE    Sweden               Stockholm                      27        \n"
    "GB    United Kingdom       London                         58        \n"
    "US    United States        New York                       --        \n"
)

EXCLUSIONS_EMPTY = "Exclusions for \x1b[1mGENERAL\x1b[0m mode:\n\n"
EXCLUSIONS_FULL = "Exclusions for \x1b[1mSELECTIVE\x1b[0m mode:\nexample.com\nbank.ru\n"


class StatusParsing(unittest.TestCase):
    def test_connected_with_location(self):
        self.assertEqual(AdGuard.parse_status_output(STATUS_CONNECTED), ("connected", "DENVER"))

    def test_disconnected(self):
        self.assertEqual(AdGuard.parse_status_output(STATUS_DISCONNECTED), ("disconnected", ""))

    def test_starting_is_connecting(self):
        self.assertEqual(AdGuard.parse_status_output(STATUS_STARTING)[0], "connecting")

    def test_connecting_with_location(self):
        self.assertEqual(AdGuard.parse_status_output(STATUS_CONNECTING), ("connecting", "NEW YORK"))

    def test_logged_out(self):
        self.assertEqual(AdGuard.parse_status_output(STATUS_LOGGED_OUT)[0], "logged_out")

    def test_garbage_is_unknown(self):
        self.assertEqual(AdGuard.parse_status_output("")[0], "unknown")
        self.assertEqual(AdGuard.parse_status_output("No such file or directory")[0], "unknown")

    def test_second_line_does_not_flip_state(self):
        # The hint line mentions "disconnect"; only the first line decides.
        state, _ = AdGuard.parse_status_output(STATUS_CONNECTED)
        self.assertEqual(state, "connected")


class LicenseParsing(unittest.TestCase):
    def test_premium(self):
        self.assertEqual(
            AdGuard.parse_license_output(LICENSE_PREMIUM, True),
            ("logged_in", "medush@example.com", True, "2027-06-18"),
        )

    def test_logged_out(self):
        self.assertEqual(AdGuard.parse_license_output(LICENSE_LOGGED_OUT, False)[0], "logged_out")

    def test_transient_failure_keeps_state(self):
        self.assertEqual(AdGuard.parse_license_output("Connection timed out", False)[0], "unknown")


class LocationsParsing(unittest.TestCase):
    def test_table(self):
        locs = AdGuard.parse_locations_output(LOCATIONS)
        self.assertEqual([l["city"] for l in locs], ["Stockholm", "London", "New York"])
        self.assertEqual(locs[0], {"iso": "SE", "country": "Sweden", "city": "Stockholm", "ping": "27"})
        self.assertEqual(locs[2]["ping"], "--")

    def test_header_skipped(self):
        self.assertEqual(AdGuard.parse_locations_output("ISO   COUNTRY  CITY  PING"), [])


class ExclusionsParsing(unittest.TestCase):
    def test_empty_general(self):
        self.assertEqual(AdGuard.parse_exclusions_output(EXCLUSIONS_EMPTY), ("general", []))

    def test_selective_list(self):
        self.assertEqual(AdGuard.parse_exclusions_output(EXCLUSIONS_FULL), ("selective", ["example.com", "bank.ru"]))

    def test_input_split(self):
        self.assertEqual(AdGuard.split_exclusions_input("a.com, b.com  c.com;d.com"), ["a.com", "b.com", "c.com", "d.com"])
        self.assertEqual(AdGuard.split_exclusions_input("   "), [])


class PopupPosition(unittest.TestCase):
    SIZE = QSize(360, 580)

    def test_gnome_top_bar_without_anchor(self):
        avail = QRect(77, 32, 2483, 1408)  # top bar 32px + left dock 77px
        pos = AdGuard.compute_popup_position(self.SIZE, avail, None)
        self.assertEqual(pos, QPoint(2559 - 360 - 8, 32 + 4))  # right() is inclusive in Qt

    def test_bottom_panel_still_opens_at_the_top(self):
        avail = QRect(0, 0, 2560, 1400)  # KDE-style 40px bottom panel
        pos = AdGuard.compute_popup_position(self.SIZE, avail, None)
        self.assertEqual(pos, QPoint(2559 - 360 - 8, 4))

    def test_anchor_centres_under_icon(self):
        avail = QRect(0, 32, 2560, 1408)
        pos = AdGuard.compute_popup_position(self.SIZE, avail, QPoint(2300, 16))
        self.assertEqual(pos, QPoint(2300 - 180, 36))

    def test_anchor_near_right_edge_is_clamped(self):
        avail = QRect(0, 32, 2560, 1408)
        pos = AdGuard.compute_popup_position(self.SIZE, avail, QPoint(2550, 16))
        self.assertEqual(pos.x(), 2559 - 360 - 8)

    def test_anchor_near_left_edge_is_clamped(self):
        avail = QRect(0, 32, 2560, 1408)
        pos = AdGuard.compute_popup_position(self.SIZE, avail, QPoint(20, 16))
        self.assertEqual(pos.x(), 8)


class InstallHelpers(unittest.TestCase):
    def test_terminal_picked_in_order(self):
        which = lambda exe: "/usr/bin/" + exe if exe in ("konsole", "xterm") else None
        argv = AdGuard.terminal_command_for("/tmp/x.sh", which=which)
        self.assertEqual(argv, ["/usr/bin/konsole", "-e", "bash", "/tmp/x.sh"])

    def test_no_terminal(self):
        self.assertIsNone(AdGuard.terminal_command_for("/tmp/x.sh", which=lambda exe: None))

    def test_install_script_is_the_official_command_and_checks_curl(self):
        script = AdGuard.install_script_text()
        self.assertIn("curl -fsSL https://raw.githubusercontent.com/AdguardTeam/AdGuardVPNCLI/HEAD/scripts/release/install.sh | sh -s -- -v", script)
        self.assertIn("command -v curl", script)  # the installer itself needs curl
        self.assertNotIn("-a y", script)  # the user answers the installer's questions

    def test_find_cli_falls_back_to_opt(self):
        self.assertIn(AdGuard.find_cli(), (None, AdGuard.CLI_DEFAULT_PATH, "/usr/local/bin/adguardvpn-cli", "/usr/bin/adguardvpn-cli"))


if __name__ == "__main__":
    unittest.main()
