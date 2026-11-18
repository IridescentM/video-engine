"""把文字渲染成透明 PNG（供 ffmpeg overlay 用）。"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if os.name == "nt":
    FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
    FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
else:
    FONT_BOLD = "/System/Library/Fonts/PingFang.ttc"
    FONT_REG = "/System/Library/Fonts/PingFang.ttc"

ACCENT = (56, 189, 248, 255)
WHITE = (255, 255, 255, 255)
SHADOW = (0, 0, 0, 160)

STYLES = {
    # name: (字号, 颜色, 是否描边, 最大宽度占比, 垂直位置)
    "big_center": (96, WHITE, True, 0.86, "center"),
    "big_top": (84, WHITE, True, 0.86, "top"),
    "subtitle": (54, WHITE, True, 0.88, "bottom"),
    "accent": (88, ACCENT, False, 0.86, "center"),
}


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines or [""]


def render(text: str, style: str, size: tuple[int, int], out: Path) -> tuple[Path, str]:
    """渲染一张透明文字贴图，返回 (路径, 垂直定位 anchor)。"""
    w, h = size
    font_size, color, outline, max_ratio, anchor = STYLES.get(style, STYLES["big_center"])

    # 单行太长自动缩字号，最多缩到 60%
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fs = font_size
    while True:
        f = ImageFont.truetype(FONT_BOLD, fs)
        lines = _wrap(d, text, f, int(w * max_ratio))
        widest = max(d.textlength(ln, font=f) for ln in lines)
        if widest <= w * max_ratio or fs <= int(font_size * 0.6):
            break
        fs -= 4

    line_h = int(fs * 1.45)
    total_h = line_h * len(lines)

    if anchor == "top":
        y0 = int(h * 0.16)
    elif anchor == "bottom":
        y0 = int(h * 0.78) - total_h // 2
    else:
        y0 = (h - total_h) // 2

    d = ImageDraw.Draw(img)
    y = y0
    for ln in lines:
        tw = d.textlength(ln, font=f)
        x = (w - tw) / 2
        if outline:
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                d.text((x + dx, y + dy), ln, font=f, fill=SHADOW)
        d.text((x, y), ln, font=f, fill=color)
        y += line_h

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out, anchor
