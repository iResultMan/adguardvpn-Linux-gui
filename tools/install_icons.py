#!/usr/bin/env python3
import os
import sys
import subprocess
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QImage, QPainter, QGuiApplication
from PyQt5.QtSvg import QSvgRenderer

app = QGuiApplication(sys.argv)
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
APP_SVG_PATH = f"{ASSETS_DIR}/app_icon.svg"

with open(APP_SVG_PATH, "r") as f:
    app_svg = f.read()

renderer = QSvgRenderer(app_svg.encode('utf-8'))

def render_size(dim, out_path):
    img = QImage(dim, dim, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, dim, dim))
    painter.end()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)

sizes = [16, 22, 24, 32, 48, 64, 128, 256, 512]
base_hicolor = os.path.expanduser("~/.local/share/icons/hicolor")

for s in sizes:
    target = f"{base_hicolor}/{s}x{s}/apps/adguard.png"
    render_size(s, target)
    print(f"Installed {target}")

# Also copy 256x256 to ~/.local/share/icons/adguard.png
render_size(256, os.path.expanduser("~/.local/share/icons/adguard.png"))

# Update GTK icon cache if possible
try:
    subprocess.run(["gtk-update-icon-cache", "-f", "-t", os.path.expanduser("~/.local/share/icons/hicolor")], capture_output=True)
except Exception:
    pass

print("Icon installation complete!")
