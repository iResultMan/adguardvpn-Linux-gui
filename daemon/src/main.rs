//! adguardvpn-tray: the resident part of AdGuard VPN GUI for Linux.
//!
//! One icon in the tray and a short menu: status line, public IP, connect or
//! disconnect, open the settings window, quit. Everything it does outside its
//! own process is running `adguardvpn-cli` (status, connect, disconnect),
//! `curl` for the public IP, and the Python window on request. It opens no
//! network connection itself.
//!
//! No polling timer: the state is re-read when something happens. The CLI
//! creates `vpn.socket` and `vpn.pid` in its data directory when the VPN
//! service starts and removes them when it stops (inotify), the kernel
//! announces the tunnel interface coming and going (netlink), the user opens
//! the menu or clicks connect/disconnect, and a "connecting" state is
//! re-checked once a second until it settles.

use std::io::Read;
use std::os::linux::net::SocketAddrExt;
use std::os::unix::net::{SocketAddr, UnixListener};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

use ksni::blocking::TrayMethods;
use ksni::menu::StandardItem;
use ksni::{Icon, MenuItem, Status, ToolTip};

const CLI_NAME: &str = "adguardvpn-cli";
const CLI_DEFAULT_PATH: &str = "/opt/adguardvpn_cli/adguardvpn-cli";
const CLI_DATA_DIR: &str = ".local/share/adguardvpn-cli";
const IP_SERVICES: [&str; 2] = ["https://ipwho.is/", "https://ipapi.co/json/"];

#[derive(Clone, PartialEq, Debug)]
enum Conn {
    Connected(String),
    Connecting(String),
    Disconnected,
    LoggedOut,
    CliMissing,
    Unknown,
}

enum Cmd {
    Connect,
    Disconnect,
    OpenWindow,
    Quit,
    Refresh,
    IpResult(String, String),
}

#[derive(Clone, Copy, PartialEq)]
enum Lang {
    Ru,
    En,
}

fn t(lang: Lang, key: &str) -> &'static str {
    match (lang, key) {
        (Lang::Ru, "connected") => "Подключено",
        (Lang::Ru, "connecting") => "Подключение…",
        (Lang::Ru, "disconnected") => "Отключено",
        (Lang::Ru, "logged_out") => "Не выполнен вход, откройте окно",
        (Lang::Ru, "cli_missing") => "AdGuard VPN CLI не установлен, откройте окно",
        (Lang::Ru, "unknown") => "Статус неизвестен",
        (Lang::Ru, "connect") => "Подключиться",
        (Lang::Ru, "disconnect") => "Отключиться",
        (Lang::Ru, "working") => "Выполняется…",
        (Lang::Ru, "open_window") => "Настройки",
        (Lang::Ru, "quit") => "Выйти",
        (_, "connected") => "Connected",
        (_, "connecting") => "Connecting…",
        (_, "disconnected") => "Disconnected",
        (_, "logged_out") => "Not signed in, open the window",
        (_, "cli_missing") => "AdGuard VPN CLI is not installed, open the window",
        (_, "unknown") => "Status unknown",
        (_, "connect") => "Connect",
        (_, "disconnect") => "Disconnect",
        (_, "working") => "Working…",
        (_, "open_window") => "Settings",
        (_, "quit") => "Quit",
        _ => key_fallback(key),
    }
}

fn key_fallback(key: &str) -> &'static str {
    // Only reached for a key missing from the table above: make it visible.
    Box::leak(format!("?{key}").into_boxed_str())
}

// ---------------------------------------------------------------- CLI ----

fn find_cli() -> Option<PathBuf> {
    if let Some(paths) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&paths) {
            let candidate = dir.join(CLI_NAME);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    let fallback = Path::new(CLI_DEFAULT_PATH);
    if fallback.is_file() {
        return Some(fallback.to_path_buf());
    }
    None
}

fn strip_ansi(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\x1b' {
            if chars.peek() == Some(&'[') {
                chars.next();
                while let Some(n) = chars.next() {
                    if n.is_ascii_alphabetic() {
                        break;
                    }
                }
            }
            continue;
        }
        out.push(c);
    }
    out
}

/// Same rules as the window's parse_status_output(): the first line decides.
fn parse_status(output: &str) -> Conn {
    let clean = strip_ansi(output);
    let first = clean.trim().lines().next().unwrap_or("").trim();
    let low = first.to_lowercase();
    if low.contains("not logged in") || low.contains("please log in") {
        return Conn::LoggedOut;
    }
    if let Some(rest) = low.strip_prefix("connected to") {
        let loc = location_from(first, rest.len());
        return Conn::Connected(loc);
    }
    if low.starts_with("connecting") || low.contains("is starting") {
        let loc = match low.strip_prefix("connecting to") {
            Some(rest) => location_from(first, rest.len()),
            None => String::new(),
        };
        return Conn::Connecting(loc);
    }
    if low.contains("disconnected") || low.contains("not connected") {
        return Conn::Disconnected;
    }
    Conn::Unknown
}

fn location_from(first: &str, rest_len: usize) -> String {
    let rest = &first[first.len() - rest_len..];
    let loc = rest.split(" in ").next().unwrap_or(rest).trim();
    // The CLI prints the city upper-cased ("DENVER"); show it as a name.
    if loc.chars().all(|c| !c.is_lowercase()) {
        let mut s = String::new();
        for word in loc.split(' ') {
            let mut cs = word.chars();
            if let Some(f) = cs.next() {
                if !s.is_empty() {
                    s.push(' ');
                }
                s.push(f);
                s.push_str(&cs.as_str().to_lowercase());
            }
        }
        s
    } else {
        loc.to_string()
    }
}

fn run_cli(args: &[&str], timeout: Duration) -> Option<String> {
    let cli = find_cli()?;
    let mut child = Command::new(cli)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .ok()?;
    let mut stdout = child.stdout.take()?;
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if start.elapsed() > timeout => {
                let _ = child.kill();
                let _ = child.wait();
                return None;
            }
            Ok(None) => thread::sleep(Duration::from_millis(100)),
            Err(_) => return None,
        }
    }
    let mut out = String::new();
    stdout.read_to_string(&mut out).ok()?;
    Some(out)
}

fn query_status() -> Conn {
    if find_cli().is_none() {
        return Conn::CliMissing;
    }
    match run_cli(&["status"], Duration::from_secs(6)) {
        Some(out) => parse_status(&out),
        None => Conn::Unknown,
    }
}

/// Public IP through curl, like the window does over HTTPS. The daemon has
/// no network code of its own.
fn query_ip() -> Option<(String, String)> {
    for url in IP_SERVICES {
        let out = Command::new("curl")
            .args(["-fsSL", "--max-time", "4", "-A", "AdGuardVPN-GUI/2.0", url])
            .stdin(Stdio::null())
            .output()
            .ok()?;
        if !out.status.success() {
            continue;
        }
        let json: serde_json::Value = match serde_json::from_slice(&out.stdout) {
            Ok(v) => v,
            Err(_) => continue,
        };
        if json.get("success") == Some(&serde_json::Value::Bool(false)) {
            continue;
        }
        let ip = json.get("ip").and_then(|v| v.as_str()).unwrap_or("");
        if ip.is_empty() {
            continue;
        }
        let pick = |keys: &[&str]| -> String {
            keys.iter()
                .filter_map(|k| json.get(*k).and_then(|v| v.as_str()))
                .find(|s| !s.is_empty())
                .unwrap_or("")
                .to_string()
        };
        let parts: Vec<String> = [pick(&["city"]), pick(&["region", "region_name"]), pick(&["country", "country_name"])]
            .into_iter()
            .filter(|s| !s.is_empty())
            .collect();
        return Some((ip.to_string(), parts.join(", ")));
    }
    None
}

// ------------------------------------------------------------- events ----

fn cli_data_dir() -> Option<PathBuf> {
    std::env::var_os("HOME").map(|h| PathBuf::from(h).join(CLI_DATA_DIR))
}

/// inotify on the CLI data directory: `vpn.socket` / `vpn.pid` appear when
/// the VPN service starts and vanish when it stops. Log writes are ignored.
fn watch_cli_dir(tx: mpsc::Sender<Cmd>) {
    let Some(dir) = cli_data_dir() else { return };
    let Ok(cdir) = std::ffi::CString::new(dir.as_os_str().as_encoded_bytes()) else { return };
    unsafe {
        let fd = libc::inotify_init1(libc::IN_CLOEXEC);
        if fd < 0 {
            return;
        }
        let mask = libc::IN_CREATE | libc::IN_DELETE | libc::IN_MOVED_TO | libc::IN_MOVED_FROM;
        // The directory may not exist until the CLI has run once.
        while libc::inotify_add_watch(fd, cdir.as_ptr(), mask) < 0 {
            thread::sleep(Duration::from_secs(30));
            if tx.send(Cmd::Refresh).is_err() {
                return;
            }
        }
        let mut buf = vec![0u8; 4096];
        loop {
            let n = libc::read(fd, buf.as_mut_ptr() as *mut libc::c_void, buf.len());
            if n <= 0 {
                return;
            }
            let mut i = 0usize;
            let mut relevant = false;
            while i + 16 <= n as usize {
                let len = u32::from_ne_bytes([buf[i + 12], buf[i + 13], buf[i + 14], buf[i + 15]]) as usize;
                let name = &buf[i + 16..(i + 16 + len).min(n as usize)];
                let name = name.split(|b| *b == 0).next().unwrap_or(&[]);
                if name.starts_with(b"vpn.") {
                    relevant = true;
                }
                i += 16 + len;
            }
            if relevant && tx.send(Cmd::Refresh).is_err() {
                return;
            }
        }
    }
}

/// Netlink route socket, link group: the kernel tells us when a network
/// interface (the VPN tunnel) is added, removed or changes state.
fn watch_links(tx: mpsc::Sender<Cmd>) {
    unsafe {
        let fd = libc::socket(libc::AF_NETLINK, libc::SOCK_RAW | libc::SOCK_CLOEXEC, libc::NETLINK_ROUTE);
        if fd < 0 {
            return;
        }
        let mut addr: libc::sockaddr_nl = std::mem::zeroed();
        addr.nl_family = libc::AF_NETLINK as u16;
        addr.nl_groups = libc::RTMGRP_LINK as u32;
        if libc::bind(fd, &addr as *const _ as *const libc::sockaddr, std::mem::size_of::<libc::sockaddr_nl>() as u32) < 0 {
            libc::close(fd);
            return;
        }
        let mut buf = vec![0u8; 8192];
        loop {
            let n = libc::recv(fd, buf.as_mut_ptr() as *mut libc::c_void, buf.len(), 0);
            if n <= 0 {
                return;
            }
            if tx.send(Cmd::Refresh).is_err() {
                return;
            }
        }
    }
}

// ------------------------------------------------------------- window ----

/// The settings window lives next to this binary's project folder:
/// <dir>/AdGuard.py with <dir>/venv/bin/python. ADGUARD_GUI_DIR overrides.
fn window_command() -> Option<(PathBuf, PathBuf)> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Some(dir) = std::env::var_os("ADGUARD_GUI_DIR") {
        candidates.push(PathBuf::from(dir));
    }
    if let Ok(exe) = std::env::current_exe() {
        let mut p = exe.as_path();
        while let Some(parent) = p.parent() {
            candidates.push(parent.to_path_buf());
            p = parent;
        }
    }
    for dir in candidates {
        let script = dir.join("AdGuard.py");
        if script.is_file() {
            let venv = dir.join("venv/bin/python");
            let python = if venv.is_file() { venv } else { PathBuf::from("python3") };
            return Some((python, script));
        }
    }
    None
}

/// Where the window's own output goes, so a crash leaves a trace:
/// $XDG_RUNTIME_DIR/adguardvpn-window.log (or /tmp).
fn window_log_path() -> PathBuf {
    let dir = std::env::var_os("XDG_RUNTIME_DIR").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("/tmp"));
    dir.join("adguardvpn-window.log")
}

fn open_window() {
    match window_command() {
        Some((python, script)) => {
            let log = std::fs::File::create(window_log_path()).ok();
            let (out, err) = match log {
                Some(f) => (Stdio::from(f.try_clone().expect("dup log")), Stdio::from(f)),
                None => (Stdio::null(), Stdio::null()),
            };
            let result = Command::new(&python)
                .arg(&script)
                .current_dir(script.parent().unwrap_or(Path::new("/")))
                .stdin(Stdio::null())
                .stdout(out)
                .stderr(err)
                .spawn();
            if let Err(e) = result {
                eprintln!("adguardvpn-tray: cannot start {}: {e}", python.display());
            }
        }
        None => eprintln!("adguardvpn-tray: AdGuard.py not found next to the binary; set ADGUARD_GUI_DIR"),
    }
}

fn read_lang() -> Lang {
    let settings = std::env::var_os("HOME")
        .map(|h| PathBuf::from(h).join(".config/adguard-gui-settings.json"));
    if let Some(path) = settings {
        if let Ok(text) = std::fs::read_to_string(path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) {
                if json.get("lang").and_then(|v| v.as_str()) == Some("en") {
                    return Lang::En;
                }
                if json.get("lang").and_then(|v| v.as_str()) == Some("ru") {
                    return Lang::Ru;
                }
            }
        }
    }
    if std::env::var("LANG").map(|l| l.to_lowercase().starts_with("ru")).unwrap_or(false) {
        Lang::Ru
    } else {
        Lang::En
    }
}

// --------------------------------------------------------------- tray ----

fn decode_png(bytes: &[u8]) -> Icon {
    let decoder = png::Decoder::new(std::io::Cursor::new(bytes));
    let mut reader = decoder.read_info().expect("embedded icon is a valid PNG");
    let mut buf = vec![0; reader.output_buffer_size().expect("icon size")];
    let info = reader.next_frame(&mut buf).expect("decode embedded icon");
    let rgba = &buf[..info.buffer_size()];
    let mut data = Vec::with_capacity(rgba.len());
    for px in rgba.chunks(4) {
        // RGBA -> ARGB, network byte order, as StatusNotifierItem wants it.
        data.extend_from_slice(&[px[3], px[0], px[1], px[2]]);
    }
    Icon { width: info.width as i32, height: info.height as i32, data }
}

struct Tray {
    conn: Conn,
    ip: String,
    ip_place: String,
    busy: bool,
    lang: Lang,
    tx: mpsc::Sender<Cmd>,
    icon_on: Icon,
    icon_off: Icon,
}

impl Tray {
    fn status_line(&self) -> String {
        match &self.conn {
            Conn::Connected(loc) if !loc.is_empty() => format!("{}: {}", t(self.lang, "connected"), loc),
            Conn::Connected(_) => t(self.lang, "connected").to_string(),
            Conn::Connecting(loc) if !loc.is_empty() => format!("{} {}", t(self.lang, "connecting"), loc),
            Conn::Connecting(_) => t(self.lang, "connecting").to_string(),
            Conn::Disconnected => t(self.lang, "disconnected").to_string(),
            Conn::LoggedOut => t(self.lang, "logged_out").to_string(),
            Conn::CliMissing => t(self.lang, "cli_missing").to_string(),
            Conn::Unknown => t(self.lang, "unknown").to_string(),
        }
    }

    fn is_connected(&self) -> bool {
        matches!(self.conn, Conn::Connected(_))
    }
}

impl ksni::Tray for Tray {
    fn id(&self) -> String {
        "adguardvpn-tray".into()
    }

    fn title(&self) -> String {
        format!("AdGuard VPN: {}", self.status_line())
    }

    fn status(&self) -> Status {
        Status::Active
    }

    fn icon_pixmap(&self) -> Vec<Icon> {
        vec![if self.is_connected() { self.icon_on.clone() } else { self.icon_off.clone() }]
    }

    fn tool_tip(&self) -> ToolTip {
        ToolTip {
            title: "AdGuard VPN".into(),
            description: self.status_line(),
            ..Default::default()
        }
    }

    fn activate(&mut self, _x: i32, _y: i32) {
        // Left click where the host sends it (KDE, Xfce). GNOME opens the menu.
        let _ = self.tx.send(Cmd::OpenWindow);
    }

    fn menu_about_to_show(&mut self) {
        // The user is looking: make sure the lines are current.
        let _ = self.tx.send(Cmd::Refresh);
    }

    fn menu(&self) -> Vec<MenuItem<Self>> {
        let lang = self.lang;
        let mut items: Vec<MenuItem<Self>> = vec![StandardItem {
            label: self.status_line(),
            enabled: false,
            ..Default::default()
        }
        .into()];
        if !self.ip.is_empty() {
            let label = if self.ip_place.is_empty() {
                format!("IP {}", self.ip)
            } else {
                format!("IP {} · {}", self.ip, self.ip_place)
            };
            items.push(StandardItem { label, enabled: false, ..Default::default() }.into());
        }
        items.push(MenuItem::Separator);
        let can_toggle = matches!(self.conn, Conn::Connected(_) | Conn::Connecting(_) | Conn::Disconnected | Conn::Unknown);
        if can_toggle {
            let connected = self.is_connected();
            items.push(
                StandardItem {
                    label: if self.busy {
                        t(lang, "working").to_string()
                    } else if connected {
                        t(lang, "disconnect").to_string()
                    } else {
                        t(lang, "connect").to_string()
                    },
                    enabled: !self.busy,
                    activate: Box::new(move |tray: &mut Self| {
                        if !tray.busy {
                            tray.busy = true;
                            let _ = tray.tx.send(if connected { Cmd::Disconnect } else { Cmd::Connect });
                        }
                    }),
                    ..Default::default()
                }
                .into(),
            );
        }
        items.push(
            StandardItem {
                label: t(lang, "open_window").to_string(),
                activate: Box::new(|tray: &mut Self| {
                    let _ = tray.tx.send(Cmd::OpenWindow);
                }),
                ..Default::default()
            }
            .into(),
        );
        items.push(MenuItem::Separator);
        items.push(
            StandardItem {
                label: t(lang, "quit").to_string(),
                activate: Box::new(|tray: &mut Self| {
                    let _ = tray.tx.send(Cmd::Quit);
                }),
                ..Default::default()
            }
            .into(),
        );
        items
    }
}

// --------------------------------------------------------------- main ----

fn single_instance_guard() -> Option<UnixListener> {
    // An abstract Unix socket name is owned by one process per user and
    // disappears with it: a lock with nothing to clean up.
    let uid = std::fs::metadata("/proc/self").map(|m| {
        use std::os::unix::fs::MetadataExt;
        m.uid()
    });
    let name = format!("adguardvpn-tray-{}", uid.unwrap_or(0));
    let addr = SocketAddr::from_abstract_name(name.as_bytes()).ok()?;
    UnixListener::bind_addr(&addr).ok()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--version" || a == "-V") {
        println!("adguardvpn-tray {}", env!("CARGO_PKG_VERSION"));
        return;
    }
    let Some(_guard) = single_instance_guard() else {
        eprintln!("adguardvpn-tray is already running");
        return;
    };

    let (tx, rx) = mpsc::channel::<Cmd>();
    let tray = Tray {
        conn: Conn::Unknown,
        ip: String::new(),
        ip_place: String::new(),
        busy: false,
        lang: read_lang(),
        tx: tx.clone(),
        icon_on: decode_png(include_bytes!("../icons/connected.png")),
        icon_off: decode_png(include_bytes!("../icons/disconnected.png")),
    };

    // The tray host (GNOME extension, Plasma, Xfce plugin) may come up after
    // us at login: retry for a while before giving up.
    let mut handle = None;
    let mut pending = Some(tray);
    for attempt in 0..20 {
        match pending.take().unwrap().spawn() {
            Ok(h) => {
                handle = Some(h);
                break;
            }
            Err(e) => {
                if attempt == 19 {
                    eprintln!("adguardvpn-tray: no system tray available ({e}). On GNOME install the AppIndicator extension. Opening the window instead.");
                    open_window();
                    return;
                }
                thread::sleep(Duration::from_secs(3));
                pending = Some(Tray {
                    conn: Conn::Unknown,
                    ip: String::new(),
                    ip_place: String::new(),
                    busy: false,
                    lang: read_lang(),
                    tx: tx.clone(),
                    icon_on: decode_png(include_bytes!("../icons/connected.png")),
                    icon_off: decode_png(include_bytes!("../icons/disconnected.png")),
                });
            }
        }
    }
    let handle = handle.expect("tray handle");

    let mut last_conn = Conn::Unknown;
    let ip_tx = tx.clone();
    let request_ip = move || {
        let tx = ip_tx.clone();
        thread::spawn(move || {
            if let Some((ip, place)) = query_ip() {
                let _ = tx.send(Cmd::IpResult(ip, place));
            }
        });
    };
    {
        let t = tx.clone();
        thread::spawn(move || watch_cli_dir(t));
        let t = tx.clone();
        thread::spawn(move || watch_links(t));
    }
    let _ = tx.send(Cmd::Refresh);
    let mut settle_checks = 0u32;
    let delayed_refresh = {
        let tx = tx.clone();
        move |after: Duration| {
            let tx = tx.clone();
            thread::spawn(move || {
                thread::sleep(after);
                let _ = tx.send(Cmd::Refresh);
            });
        }
    };

    loop {
        let cmd = match rx.recv() {
            Ok(c) => c,
            Err(_) => return,
        };
        match cmd {
            Cmd::Refresh => {
                let conn = query_status();
                if conn != last_conn {
                    let lang = read_lang();
                    handle.update(|tray| {
                        tray.conn = conn.clone();
                        tray.lang = lang;
                    });
                    if matches!(conn, Conn::Connected(_) | Conn::Disconnected) {
                        request_ip();
                    }
                    last_conn = conn.clone();
                }
                // "Connecting" is transient: look again shortly, a bounded
                // number of times, instead of waiting for the next event.
                if matches!(conn, Conn::Connecting(_)) && settle_checks < 60 {
                    settle_checks += 1;
                    delayed_refresh(Duration::from_secs(1));
                } else if !matches!(conn, Conn::Connecting(_)) {
                    settle_checks = 0;
                }
            }
            Cmd::Connect | Cmd::Disconnect => {
                let args: &[&str] = if matches!(cmd, Cmd::Disconnect) { &["disconnect"] } else { &["connect", "-y"] };
                let _ = run_cli(args, Duration::from_secs(30));
                handle.update(|tray| tray.busy = false);
                let _ = tx.send(Cmd::Refresh);
                delayed_refresh(Duration::from_millis(1500));
            }
            Cmd::OpenWindow => open_window(),
            Cmd::IpResult(ip, place) => {
                handle.update(|tray| {
                    tray.ip = ip;
                    tray.ip_place = place;
                });
            }
            Cmd::Quit => {
                handle.shutdown();
                return;
            }
        }
        if handle.is_closed() {
            return;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_cli_status() {
        assert_eq!(parse_status("Connected to \x1b[1mDENVER\x1b[0m in \x1b[1mTUN\x1b[0m mode, running on tun0\nYou can disconnect by running `adguardvpn-cli disconnect`"), Conn::Connected("Denver".into()));
        assert_eq!(parse_status("Connected to \x1b[1mNEW YORK\x1b[0m in TUN mode"), Conn::Connected("New York".into()));
        assert_eq!(parse_status("VPN is disconnected"), Conn::Disconnected);
        assert_eq!(parse_status("VPN is starting"), Conn::Connecting(String::new()));
        assert_eq!(parse_status("Connecting to \x1b[1mPARIS\x1b[0m in TUN mode"), Conn::Connecting("Paris".into()));
        assert_eq!(parse_status("You are not logged in"), Conn::LoggedOut);
        assert_eq!(parse_status(""), Conn::Unknown);
    }

    #[test]
    fn strips_ansi() {
        assert_eq!(strip_ansi("a\x1b[1mb\x1b[0mc"), "abc");
    }
}
