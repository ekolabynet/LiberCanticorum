#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
"""
Generator teł do slajdów (motywy sztuki kościelnej: kodeks z neumami, iluminacje, witraże…).
Wszystko rysowane wektorowo od zera – obrazy wynikowe można swobodnie używać (CC0).
Ozdobniki są tylko na brzegach i mają niski kontrast, żeby nie rozpraszać od tekstu.

Jasne tła (jasny_*) naśladują styl iluminowanych ksiąg chórałowych: pergamin, czerwone linie,
czarne nuty kwadratowe i menzuralne, złocone inicjały, ornament piórkowy, bordiury roślinne.

Użycie:  python generuj_tla.py [folder_wyjściowy] [nazwa_motywu ...]     (domyślnie: ./tla, wszystkie)
Plik tla.json zawiera zalecane kolory tekstu i marginesy dla każdego tła.
"""
import math
import os
import sys

import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPolygonF, QRadialGradient)

SIZES = {'16x9': (1920, 1080), '4x3': (1440, 1080)}


# ------------------------------------------------------------------ narzędzia
def col(hexstr, alpha=1.0):
    c = QColor(hexstr)
    c.setAlphaF(alpha)
    return c


def base(p, W, H, inner, outer, center=(0.5, 0.48)):
    g = QRadialGradient(QPointF(W * center[0], H * center[1]), max(W, H) * 0.75)
    g.setColorAt(0, QColor(inner))
    g.setColorAt(1, QColor(outer))
    p.fillRect(QRectF(0, 0, W, H), g)


def grain(img, strength=6, seed=1):
    """Delikatne ziarno pergaminu: miękkie plamy + drobny szum."""
    rng = np.random.default_rng(seed)
    W, H = img.width(), img.height()
    low = rng.normal(0, 1, (H // 24 + 2, W // 24 + 2)).astype(np.float32)
    small = QImage(((low * 40 + 128).clip(0, 255)).astype(np.uint8).tobytes(), low.shape[1], low.shape[0],
                   low.shape[1], QImage.Format_Grayscale8).scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    sb = small.constBits()
    blot = (np.frombuffer(sb, np.uint8).reshape(H, small.bytesPerLine())[:, :W].astype(np.float32) - 128) / 40
    n = blot * 1.0 + rng.normal(0, 0.45, (H, W)).astype(np.float32)
    img = img.convertToFormat(QImage.Format_RGB32)
    arr = np.frombuffer(img.bits(), np.uint8).reshape(H, img.bytesPerLine() // 4, 4)[:, :W, :3]
    arr[:] = np.clip(arr.astype(np.float32) + n[..., None] * strength, 0, 255).astype(np.uint8)
    return img


def vignette(p, W, H, strength=0.55):
    g = QRadialGradient(QPointF(W / 2, H / 2), math.hypot(W, H) / 2)
    g.setColorAt(0.55, col('#000000', 0))
    g.setColorAt(1.0, col('#000000', strength))
    p.fillRect(QRectF(0, 0, W, H), g)


def frame(p, W, H, color, m=0.035, double=True, width=2.0):
    p.save()
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(color, width))
    d = H * m
    p.drawRect(QRectF(d, d, W - 2 * d, H - 2 * d))
    if double:
        p.setPen(QPen(color, width * 0.5))
        d2 = d + H * 0.012
        p.drawRect(QRectF(d2, d2, W - 2 * d2, H - 2 * d2))
    p.restore()


def star(cx, cy, r_out, r_in, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
    return QPolygonF(pts)


def leaf_path(x, y, ang, L, w):
    """Listek (dwie krzywe) od punktu (x,y) w kierunku ang."""
    ca, sa = math.cos(ang), math.sin(ang)
    tip = QPointF(x + ca * L, y + sa * L)
    nx, ny = -sa, ca
    c1 = QPointF(x + ca * L * 0.5 + nx * w, y + sa * L * 0.5 + ny * w)
    c2 = QPointF(x + ca * L * 0.5 - nx * w, y + sa * L * 0.5 - ny * w)
    path = QPainterPath(QPointF(x, y))
    path.quadTo(c1, tip)
    path.quadTo(c2, QPointF(x, y))
    return path


# ------------------------------------------------------------------ neumy (notacja kwadratowa)
def neume_staff(p, x, y, length, gap, line_color, ink, rng, clef=True, density=1.0):
    """Czterolinia (tetragram) z neumami chorałowymi – jak w średniowiecznym graduale."""
    p.save()
    p.setPen(QPen(line_color, max(1.0, gap * 0.09)))
    for i in range(4):
        p.drawLine(QPointF(x, y + i * gap), QPointF(x + length, y + i * gap))
    p.setPen(Qt.NoPen)
    p.setBrush(ink)
    s = gap * 0.78                     # bok kwadratowej nuty
    stem = QPen(ink, max(1.0, gap * 0.11))

    def note(cx, pos):                 # pos: 0 = górna linia, 1 = pole niżej (pół odstępu)…
        cy = y + pos * gap / 2
        path = QPainterPath()
        path.addRect(QRectF(cx - s / 2, cy - s / 2 + s * 0.06, s, s * 0.88))
        p.drawPath(path)
        return cy

    cx = x + gap * 0.6
    if clef:                           # klucz C (do): dwa kwadraty i pionowa kreska
        p.setPen(stem)
        p.drawLine(QPointF(cx - s * 0.55, y + gap * 0.6), QPointF(cx - s * 0.55, y + gap * 2.4))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(cx - s * 0.5, y + gap * 0.75, s * 0.75, s * 0.6))
        p.drawRect(QRectF(cx - s * 0.5, y + gap * 1.65, s * 0.75, s * 0.6))
        cx += gap * 1.8
    pos = rng.integers(1, 6)
    while cx < x + length - gap * 1.5:
        kind = rng.choice(['punctum', 'punctum', 'virga', 'podatus', 'clivis', 'torculus', 'divisio'],
                          p=[.25, .1, .15, .17, .15, .1, .08])
        if kind == 'divisio':
            p.setPen(stem)
            p.drawLine(QPointF(cx, y + gap * 0.5), QPointF(cx, y + gap * 2.5))
            p.setPen(Qt.NoPen)
            cx += gap * 1.2
            continue
        pos = int(np.clip(pos + rng.integers(-2, 3), 0, 7))
        if kind == 'punctum':
            note(cx, pos)
        elif kind == 'virga':
            cy = note(cx, pos)
            p.setPen(stem)
            p.drawLine(QPointF(cx + s / 2, cy), QPointF(cx + s / 2, cy + gap * 1.5))
            p.setPen(Qt.NoPen)
        elif kind == 'podatus':                   # niższa pod wyższą, kreska z prawej
            hi = max(0, pos - rng.integers(1, 4))
            c1, c2 = note(cx, pos), note(cx, hi)
            p.setPen(stem)
            p.drawLine(QPointF(cx + s / 2, c1), QPointF(cx + s / 2, c2))
            p.setPen(Qt.NoPen)
        elif kind == 'clivis':                    # wyższa, potem niższa, kreska z lewej
            lo = min(7, pos + rng.integers(1, 3))
            c1 = note(cx, pos)
            p.setPen(stem)
            p.drawLine(QPointF(cx - s / 2, c1), QPointF(cx - s / 2, c1 + gap * 1.4))
            p.drawLine(QPointF(cx + s / 2, c1), QPointF(cx + s / 2, y + lo * gap / 2))
            p.setPen(Qt.NoPen)
            note(cx + s, lo)
            cx += s
        elif kind == 'torculus':
            hi = max(0, pos - 2)
            note(cx, pos)
            note(cx + s, hi)
            note(cx + 2 * s, pos)
            p.setPen(stem)
            p.drawLine(QPointF(cx + s / 2, y + pos * gap / 2), QPointF(cx + s / 2, y + hi * gap / 2))
            p.drawLine(QPointF(cx + 1.5 * s, y + hi * gap / 2), QPointF(cx + 1.5 * s, y + pos * gap / 2))
            p.setPen(Qt.NoPen)
            cx += 2 * s
        cx += gap * (1.25 + rng.random() * 0.9) / density
    p.restore()


def manuscript_lines(p, x, y, length, gap, color, rng, lines=2):
    """Imitacja minuskuły pod pięciolinią – drobne kreski i łuki (nieczytelne, czysto ozdobne)."""
    p.save()
    p.setPen(QPen(color, max(1.0, gap * 0.08), Qt.SolidLine, Qt.RoundCap))
    for li in range(lines):
        cx, yy = x, y + li * gap * 1.1
        end = x + length * (0.75 + 0.25 * rng.random())
        while cx < end:
            word = rng.integers(2, 7)
            for _ in range(word):
                h = gap * (0.45 if rng.random() < 0.8 else 0.8)
                p.drawLine(QPointF(cx, yy), QPointF(cx, yy - h))
                if rng.random() < 0.5:
                    path = QPainterPath(QPointF(cx, yy - gap * 0.45))
                    path.quadTo(QPointF(cx + gap * 0.18, yy - gap * 0.62), QPointF(cx + gap * 0.3, yy - gap * 0.4))
                    p.drawPath(path)
                cx += gap * 0.28
            cx += gap * 0.45
    p.restore()


# ------------------------------------------------------------------ ornamenty roślinne
def vine_corner(p, cx, cy, sx, sy, size, stroke, fill, rng, leaves=True):
    """Wić roślinna w narożniku (sx, sy = kierunki ±1), ze spiralnym zakończeniem i listkami."""
    p.save()
    p.translate(cx, cy)
    p.scale(sx, sy)
    pen = QPen(stroke, max(1.2, size * 0.012), Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    for (L, ang0) in ((size, 0.0), (size * 0.75, math.pi / 2)):
        # łodyga wzdłuż krawędzi, falująca
        path = QPainterPath(QPointF(0, 0))
        pts = []
        steps = 40
        for i in range(1, steps + 1):
            t = i / steps
            along = L * t
            wave = size * 0.035 * math.sin(t * math.pi * 3)
            x, y = (along, wave) if ang0 == 0 else (wave, along)
            pts.append((x, y))
            path.lineTo(QPointF(x, y))
        p.drawPath(path)
        # spirale odchodzące od łodygi
        for k, t in enumerate((0.3, 0.62, 0.92)):
            bx, by = pts[int(t * steps) - 1]
            r0 = size * (0.11 - 0.025 * k)
            sp = QPainterPath(QPointF(bx, by))
            turns = 1.6
            for j in range(1, 60):
                th = j / 59 * turns * 2 * math.pi
                r = r0 * (1 - j / 66)
                ox, oy = (r * math.sin(th), r0 - r * math.cos(th)) if ang0 == 0 else (r0 - r * math.cos(th), r * math.sin(th))
                sp.lineTo(QPointF(bx + ox, by + oy))
            p.drawPath(sp)
            if leaves:
                p.save()
                p.setBrush(fill)
                p.setPen(QPen(stroke, pen.widthF() * 0.6))
                a = (math.pi / 2 if ang0 == 0 else 0) + rng.uniform(-0.5, 0.5)
                p.drawPath(leaf_path(bx, by, a + 0.6, size * 0.09, size * 0.03))
                p.drawPath(leaf_path(bx, by, a - 0.9, size * 0.07, size * 0.025))
                p.restore()
        # kropki (motyw z rękopisów)
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(stroke)
        for t in (0.15, 0.45, 0.78):
            bx, by = pts[int(t * steps) - 1]
            for d in range(3):
                off = size * (0.03 + d * 0.022)
                x, y = (bx, by - off) if ang0 == 0 else (bx - off, by)
                p.drawEllipse(QPointF(x, y), size * 0.007, size * 0.007)
        p.restore()
    # medalion w narożniku
    p.setBrush(fill)
    p.drawEllipse(QPointF(0, 0), size * 0.045, size * 0.045)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(0, 0), size * 0.07, size * 0.07)
    p.restore()


def lily(p, x, y, h, color, outline=None):
    """Stylizowana lilia (fleur-de-lis)."""
    p.save()
    p.translate(x, y)
    p.scale(h / 100, h / 100)
    path = QPainterPath(QPointF(0, -50))
    path.cubicTo(QPointF(14, -30), QPointF(12, -5), QPointF(0, 10))
    path.cubicTo(QPointF(-12, -5), QPointF(-14, -30), QPointF(0, -50))
    for s in (1, -1):
        side = QPainterPath(QPointF(4 * s, 8))
        side.cubicTo(QPointF(40 * s, -2), QPointF(48 * s, -40), QPointF(26 * s, -36))
        side.cubicTo(QPointF(36 * s, -20), QPointF(24 * s, 4), QPointF(6 * s, 16))
        path.addPath(side)
    path.addRect(QRectF(-22, 12, 44, 7))
    foot = QPainterPath(QPointF(-4, 19))
    foot.cubicTo(QPointF(-6, 32), QPointF(-18, 40), QPointF(-26, 42))
    foot.lineTo(QPointF(26, 42))
    foot.cubicTo(QPointF(18, 40), QPointF(6, 32), QPointF(4, 19))
    path.addPath(foot)
    p.setPen(QPen(outline, 1.5) if outline else Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path.simplified())
    p.restore()


# ------------------------------------------------------------------ motywy
def t_kodeks(p, W, H, rng):
    base(p, W, H, '#2a1f14', '#0b0805')
    gold, red, ink = col('#c9a45c', 0.30), col('#b0402e', 0.38), col('#e8d9b5', 0.30)
    gap = H * 0.022
    m = H * 0.06
    # dwie czterolinie u góry i jedna u dołu, po bokach margines
    neume_staff(p, m * 0.55 + gap * 4.4, m, W - m * 2.15 - gap * 4.4, gap, red, ink, rng)
    manuscript_lines(p, m * 0.55 + gap * 5, m + gap * 5.2, W - m * 3.6, gap * 0.9, col('#e8d9b5', 0.16), rng, 1)
    neume_staff(p, m * 1.6, H - m - gap * 5.2, W - m * 3.2, gap, red, ink, rng)
    manuscript_lines(p, m * 1.6 + gap * 2, H - m + gap * 0.6, W - m * 3.6, gap * 0.9, col('#e8d9b5', 0.16), rng, 1)
    frame(p, W, H, gold, m=0.025)
    # inicjał-medalion w lewym górnym rogu
    p.setPen(QPen(gold, 2))
    p.setBrush(col('#7a2a1d', 0.25))
    p.drawRect(QRectF(m * 0.55, m * 0.7, gap * 3.4, gap * 3.4))
    f = QFont("DejaVu Serif")
    f.setPixelSize(int(gap * 3))
    f.setBold(True)
    p.setFont(f)
    p.setPen(col('#d8b56a', 0.45))
    p.drawText(QRectF(m * 0.55, m * 0.7, gap * 3.4, gap * 3.4), Qt.AlignCenter, "A")
    vignette(p, W, H, 0.6)


def t_iluminacja(p, W, H, rng):
    base(p, W, H, '#14213d', '#05080f')
    gold, fill = col('#d4af37', 0.42), col('#8a6d1f', 0.25)
    s = H * 0.36
    d = H * 0.055
    vine_corner(p, d, d, 1, 1, s, gold, fill, rng)
    vine_corner(p, W - d, d, -1, 1, s, gold, fill, rng)
    vine_corner(p, d, H - d, 1, -1, s, gold, fill, rng)
    vine_corner(p, W - d, H - d, -1, -1, s, gold, fill, rng)
    frame(p, W, H, col('#d4af37', 0.18), m=0.02, double=False, width=1.5)
    vignette(p, W, H, 0.5)


def t_adwent(p, W, H, rng):
    base(p, W, H, '#2a1640', '#08040e')
    gold = col('#e3c27a', 0.35)
    # gwiazdki u góry
    p.setPen(Qt.NoPen)
    for _ in range(70):
        x, y = rng.uniform(0, W), rng.uniform(0, H * 0.18) ** 1.0
        r = rng.uniform(0.8, 2.4)
        p.setBrush(col('#f4e7c5', rng.uniform(0.15, 0.45)))
        p.drawEllipse(QPointF(x, y), r, r)
    # wieniec z 4 świecami – mały, w prawym dolnym rogu
    cx, cy, R = W - H * 0.2, H - H * 0.11, H * 0.1
    def wreath(front):
        p.setPen(QPen(col('#88a86e', 0.4), 1.5))
        p.setBrush(col('#2f4a2a', 0.55))
        for k in range(30):
            a = k / 30 * 2 * math.pi
            if (math.sin(a) > 0) != front:
                continue
            p.drawPath(leaf_path(cx + R * math.cos(a), cy + R * 0.3 * math.sin(a), a + 1.2, H * 0.032, H * 0.009))

    wreath(False)
    for k, (dx, lit) in enumerate(((-0.62, True), (-0.2, True), (0.22, False), (0.64, False))):
        x = cx + dx * R
        base_y = cy + (0.06 if k in (0, 3) else -0.03) * R
        h = H * 0.075
        p.setPen(Qt.NoPen)
        p.setBrush(col('#d9b3ff' if k != 2 else '#f2b6d0', 0.34))
        p.drawRoundedRect(QRectF(x - H * 0.011, base_y - h, H * 0.022, h), 2, 2)
        if lit:
            top = base_y - h
            g = QRadialGradient(QPointF(x, top - H * 0.018), H * 0.045)
            g.setColorAt(0, col('#ffe9a8', 0.4))
            g.setColorAt(1, col('#ffe9a8', 0))
            p.setBrush(g)
            p.drawEllipse(QPointF(x, top - H * 0.018), H * 0.045, H * 0.045)
            fl = QPainterPath(QPointF(x, top - H * 0.04))
            fl.quadTo(QPointF(x + H * 0.009, top - H * 0.012), QPointF(x, top - H * 0.003))
            fl.quadTo(QPointF(x - H * 0.009, top - H * 0.012), QPointF(x, top - H * 0.04))
            p.setBrush(col('#ffd77a', 0.7))
            p.drawPath(fl)
    wreath(True)
    # delikatny szlaczek u dołu
    p.setPen(QPen(gold, 1.2))
    y = H * 0.955
    p.drawLine(QPointF(W * 0.06, y), QPointF(W * 0.6, y))
    for x in np.arange(W * 0.07, W * 0.6, H * 0.04):
        p.drawPolygon(star(x, y, H * 0.006, H * 0.003, 4))
    vignette(p, W, H, 0.55)


def t_boze_narodzenie(p, W, H, rng):
    base(p, W, H, '#0e1e3a', '#02050c', center=(0.5, 0.4))
    p.setPen(Qt.NoPen)
    for _ in range(160):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        if abs(x - W / 2) < W * 0.33 and abs(y - H / 2) < H * 0.32:
            continue                                   # środek czysty
        r = rng.uniform(0.6, 2.0)
        p.setBrush(col('#ffffff', rng.uniform(0.08, 0.35)))
        p.drawEllipse(QPointF(x, y), r, r)
    # Gwiazda Betlejemska w prawym górnym rogu
    sx, sy = W - H * 0.2, H * 0.17
    g = QRadialGradient(QPointF(sx, sy), H * 0.16)
    g.setColorAt(0, col('#fff4cf', 0.35))
    g.setColorAt(1, col('#fff4cf', 0))
    p.setBrush(g)
    p.drawEllipse(QPointF(sx, sy), H * 0.16, H * 0.16)
    for k, L in enumerate((0.13, 0.05, 0.08, 0.05, 0.3, 0.05, 0.08, 0.05)):   # długi promień w dół-lewo
        a = -math.pi / 2 + k * math.pi / 4
        if k == 4:
            a = math.pi * 0.62
        lg = QLinearGradient(QPointF(sx, sy), QPointF(sx + math.cos(a) * H * L, sy + math.sin(a) * H * L))
        lg.setColorAt(0, col('#fff1c2', 0.55))
        lg.setColorAt(1, col('#fff1c2', 0))
        p.setPen(QPen(QBrush(lg), 2.2 if k % 2 == 0 else 1.2))
        p.drawLine(QPointF(sx, sy), QPointF(sx + math.cos(a) * H * L, sy + math.sin(a) * H * L))
    p.setPen(Qt.NoPen)
    p.setBrush(col('#fff8e0', 0.75))
    p.drawPolygon(star(sx, sy, H * 0.03, H * 0.008, 4, rot=-math.pi / 2))
    # sylwetka stajenki na dole, bardzo ciemna
    p.setBrush(col('#000000', 0.45))
    path = QPainterPath(QPointF(0, H))
    path.lineTo(QPointF(0, H * 0.94))
    path.cubicTo(QPointF(W * 0.2, H * 0.9), QPointF(W * 0.4, H * 0.95), QPointF(W * 0.62, H * 0.93))
    path.cubicTo(QPointF(W * 0.8, H * 0.91), QPointF(W * 0.9, H * 0.95), QPointF(W, H * 0.93))
    path.lineTo(QPointF(W, H))
    p.drawPath(path)
    bx, by = W * 0.14, H * 0.915
    st = QPolygonF([QPointF(bx - H * 0.06, by), QPointF(bx - H * 0.06, by - H * 0.04), QPointF(bx, by - H * 0.085),
                    QPointF(bx + H * 0.06, by - H * 0.04), QPointF(bx + H * 0.06, by)])
    p.drawPolygon(st)
    vignette(p, W, H, 0.45)


def t_maryjne(p, W, H, rng):
    base(p, W, H, '#123063', '#030914')
    gold = col('#e8cf8a', 0.42)
    # 12 gwiazd w łuku u góry (Ap 12,1)
    p.setPen(Qt.NoPen)
    p.setBrush(gold)
    cx = W / 2
    for k in range(12):
        p.drawPolygon(star(cx + (k - 5.5) * H * 0.07, H * 0.075 + ((k - 5.5) ** 2) * H * 0.0012, H * 0.013, H * 0.005))
    # lilie w dolnych narożnikach
    for x in (H * 0.13, W - H * 0.13):
        lily(p, x, H * 0.86, H * 0.17, col('#f2f2ea', 0.22), col('#e8cf8a', 0.35))
    # błękitny welon-łuk na dole
    p.setPen(QPen(col('#9fb7e6', 0.18), 2))
    p.setBrush(Qt.NoBrush)
    for i in range(3):
        path = QPainterPath(QPointF(W * 0.22, H * (0.97 - i * 0.012)))
        path.quadTo(QPointF(W / 2, H * (0.9 - i * 0.012)), QPointF(W * 0.78, H * (0.97 - i * 0.012)))
        p.drawPath(path)
    frame(p, W, H, col('#e8cf8a', 0.16), m=0.022, double=False, width=1.2)
    vignette(p, W, H, 0.5)


def t_wielki_post(p, W, H, rng):
    base(p, W, H, '#1d1424', '#050307')
    c = col('#a58fb8', 0.22)
    # krzyż po lewej, smukły
    x, y0 = H * 0.13, H * 0.18
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    p.drawRect(QRectF(x - H * 0.006, y0, H * 0.012, H * 0.62))
    p.drawRect(QRectF(x - H * 0.07, y0 + H * 0.13, H * 0.14, H * 0.012))
    # korona cierniowa – trzy splecione pędy z kolcami, zawieszona na krzyżu
    ccx, ccy, rx, ry = x, y0 + H * 0.2, H * 0.05, H * 0.017
    for strand in range(3):
        path = QPainterPath()
        for j in range(121):
            th = j / 120 * 2 * math.pi
            off = 1 + 0.18 * math.sin(5 * th + strand * 2.1)
            pt = QPointF(ccx + rx * off * math.cos(th), ccy + ry * off * math.sin(th) + H * 0.004 * math.sin(5 * th + strand))
            path.moveTo(pt) if j == 0 else path.lineTo(pt)
        p.setPen(QPen(col('#8c7a5e', 0.38), 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
    p.setPen(QPen(col('#8c7a5e', 0.38), 1.2))
    for k in range(26):
        th = k / 26 * 2 * math.pi + 0.1
        px_, py_ = ccx + rx * 1.1 * math.cos(th), ccy + ry * 1.1 * math.sin(th)
        a = th + (0.5 if k % 2 else -0.5)
        p.drawLine(QPointF(px_, py_), QPointF(px_ + math.cos(a) * H * 0.011, py_ + math.sin(a) * H * 0.011))
    # meander u dołu (szlaczek grecki), bardzo dyskretny
    p.setPen(QPen(col('#a58fb8', 0.16), 2))
    s = H * 0.022
    y = H * 0.93
    path = QPainterPath(QPointF(W * 0.22, y))
    xx = W * 0.22
    while xx < W * 0.92:
        path.lineTo(QPointF(xx, y - s))
        path.lineTo(QPointF(xx + s, y - s))
        path.lineTo(QPointF(xx + s, y - s * 0.5))
        path.lineTo(QPointF(xx + s * 0.5, y - s * 0.5))
        path.lineTo(QPointF(xx + s * 0.5, y))
        path.lineTo(QPointF(xx + s * 1.6, y))
        xx += s * 1.6
    p.drawPath(path)
    vignette(p, W, H, 0.6)


def t_wielkanoc(p, W, H, rng):
    base(p, W, H, '#2b2412', '#070502', center=(0.5, 0.45))
    gold = col('#f0d58a', 0.38)
    # promienie od góry
    cx, cy = W / 2, -H * 0.25
    for k in range(40):
        a = math.pi / 2 + (k - 19.5) * 0.035
        lg = QLinearGradient(QPointF(cx, cy), QPointF(cx + math.cos(a) * H * 1.2, cy + math.sin(a) * H * 1.2))
        lg.setColorAt(0, col('#fff3c4', 0.10))
        lg.setColorAt(0.45, col('#fff3c4', 0.03))
        lg.setColorAt(1, col('#fff3c4', 0))
        p.setPen(QPen(QBrush(lg), H * 0.012))
        p.drawLine(QPointF(cx, cy), QPointF(cx + math.cos(a) * H * 1.2, cy + math.sin(a) * H * 1.2))
    # Chi-Rho w medalionie u dołu, Alfa i Omega po bokach
    mx, my, r = W / 2, H * 0.89, H * 0.06
    p.setPen(QPen(gold, 2))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(mx, my), r, r)
    p.setPen(QPen(gold, 3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(mx, my - r * 0.75), QPointF(mx, my + r * 0.75))             # Rho – trzon
    rho = QPainterPath(QPointF(mx, my - r * 0.75))
    rho.cubicTo(QPointF(mx + r * 0.55, my - r * 0.75), QPointF(mx + r * 0.55, my - r * 0.15), QPointF(mx, my - r * 0.15))
    p.drawPath(rho)
    p.drawLine(QPointF(mx - r * 0.5, my - r * 0.45), QPointF(mx + r * 0.5, my + r * 0.55))   # Chi
    p.drawLine(QPointF(mx + r * 0.5, my - r * 0.45), QPointF(mx - r * 0.5, my + r * 0.55))
    f = QFont("DejaVu Serif")
    f.setPixelSize(int(H * 0.06))
    p.setFont(f)
    p.setPen(gold)
    p.drawText(QRectF(mx - r * 4.2, my - r, r * 2, r * 2), Qt.AlignCenter, "Α")
    p.drawText(QRectF(mx + r * 2.2, my - r, r * 2, r * 2), Qt.AlignCenter, "Ω")
    for x in (H * 0.12, W - H * 0.12):
        lily(p, x, H * 0.87, H * 0.15, col('#ffffff', 0.16), col('#f0d58a', 0.3))
    vignette(p, W, H, 0.5)


def t_duch_swiety(p, W, H, rng):
    base(p, W, H, '#3a0c0c', '#0a0202', center=(0.5, 0.35))
    # promienie z góry i 7 płomieni (siedem darów) w łuku
    cx, cy = W / 2, -H * 0.05
    p.setPen(Qt.NoPen)
    for k in range(7):
        x = cx + (k - 3) * H * 0.075
        y = H * 0.09 + abs(k - 3) ** 1.6 * H * 0.008
        g = QRadialGradient(QPointF(x, y), H * 0.03)
        g.setColorAt(0, col('#ffcf6b', 0.35))
        g.setColorAt(1, col('#ffcf6b', 0))
        p.setBrush(g)
        p.drawEllipse(QPointF(x, y), H * 0.03, H * 0.03)
        fl = QPainterPath(QPointF(x, y - H * 0.03))
        fl.cubicTo(QPointF(x + H * 0.014, y - H * 0.012), QPointF(x + H * 0.012, y + H * 0.012), QPointF(x, y + H * 0.014))
        fl.cubicTo(QPointF(x - H * 0.012, y + H * 0.012), QPointF(x - H * 0.014, y - H * 0.012), QPointF(x, y - H * 0.03))
        p.setBrush(col('#ffb347', 0.55))
        p.drawPath(fl)
    for k in range(24):
        a = math.pi / 2 + (k - 11.5) * 0.06
        lg = QLinearGradient(QPointF(cx, cy), QPointF(cx + math.cos(a) * H, cy + math.sin(a) * H))
        lg.setColorAt(0, col('#ffd9a0', 0.08))
        lg.setColorAt(1, col('#ffd9a0', 0))
        p.setPen(QPen(QBrush(lg), H * 0.01))
        p.drawLine(QPointF(cx, cy), QPointF(cx + math.cos(a) * H, cy + math.sin(a) * H))
    frame(p, W, H, col('#e0a050', 0.14), m=0.022, double=True, width=1.2)
    vignette(p, W, H, 0.55)


def gothic_arch(p, x, y_base, w, h, pen):
    """Ostrołuk z maswerkiem (trójliść)."""
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    r = w                                           # łuk ostry: promień = szerokość
    path = QPainterPath(QPointF(x, y_base))
    path.lineTo(QPointF(x, y_base - h))
    path.arcTo(QRectF(x - 0, y_base - h - r, 2 * r, 2 * r), 180, -60)
    path.moveTo(QPointF(x + w, y_base))
    path.lineTo(QPointF(x + w, y_base - h))
    path.arcTo(QRectF(x + w - 2 * r, y_base - h - r, 2 * r, 2 * r), 0, 60)
    p.drawPath(path)
    cx, cy, rr = x + w / 2, y_base - h - r * 0.42, w * 0.17
    for k in range(3):
        a = -math.pi / 2 + k * 2 * math.pi / 3
        p.drawEllipse(QPointF(cx + math.cos(a) * rr * 0.9, cy + math.sin(a) * rr * 0.9), rr * 0.75, rr * 0.75)


def t_gotyk(p, W, H, rng):
    base(p, W, H, '#1c2228', '#050608')
    pen = QPen(col('#b9c4cf', 0.2), 2)
    # arkada ostrołukowa u góry – smukłe łuki wzdłuż krawędzi
    n = 9
    w = W / n
    for i in range(n):
        gothic_arch(p, i * w + w * 0.08, H * 0.2, w * 0.84, H * 0.06, pen)
    p.setPen(QPen(col('#b9c4cf', 0.12), 1.5))
    p.drawLine(QPointF(0, H * 0.2), QPointF(W, H * 0.2))
    p.drawLine(QPointF(0, H * 0.21), QPointF(W, H * 0.21))
    # kolumny po bokach
    for x in (H * 0.05, W - H * 0.05):
        p.drawLine(QPointF(x - H * 0.012, H * 0.21), QPointF(x - H * 0.012, H))
        p.drawLine(QPointF(x + H * 0.012, H * 0.21), QPointF(x + H * 0.012, H))
    vignette(p, W, H, 0.6)


def t_witraz(p, W, H, rng):
    base(p, W, H, '#10141c', '#030405')
    colors = ['#8b1e2d', '#1f4e8c', '#c99a2e', '#2e6b3f', '#5b2a86']
    for (cx, cy) in ((0, 0), (W, 0), (0, H), (W, H)):
        R = H * 0.42
        for ring, (r0, r1, n) in enumerate(((0.2, 0.45, 8), (0.45, 0.75, 16), (0.75, 1.0, 24))):
            for k in range(n):
                a0, a1 = k / n * 360, (k + 1) / n * 360
                path = QPainterPath()
                path.arcMoveTo(QRectF(cx - R * r1, cy - R * r1, 2 * R * r1, 2 * R * r1), a0)
                path.arcTo(QRectF(cx - R * r1, cy - R * r1, 2 * R * r1, 2 * R * r1), a0, a1 - a0)
                path.arcTo(QRectF(cx - R * r0, cy - R * r0, 2 * R * r0, 2 * R * r0), a1, a0 - a1)
                path.closeSubpath()
                c = col(colors[(k + ring) % len(colors)], 0.20 - ring * 0.04)
                p.setBrush(c)
                p.setPen(QPen(col('#000000', 0.8), H * 0.006))
                p.drawPath(path)
        p.setBrush(col('#d9b860', 0.18))
        p.drawEllipse(QPointF(cx, cy), R * 0.2, R * 0.2)
    vignette(p, W, H, 0.45)


def t_czyste(p, W, H, rng):
    base(p, W, H, '#1b1f2a', '#050609')
    vignette(p, W, H, 0.4)


# ================================================================== JASNE TŁA (pergamin, księgi chórałowe)
INK = '#1c130c'           # atrament żelazowo-galasowy
RUBRA = '#a8291f'         # czerwień rubryk / linii
AZUR = '#1f4f9c'          # błękit azurytowy
GOLD = '#c9a032'


def parchment(p, W, H, rng, tone='#f1e6cc', edge='#c4a46f'):
    """Karta pergaminu: jasny środek, ciemniejsze, „przypalone” brzegi, plamy."""
    g = QRadialGradient(QPointF(W * 0.5, H * 0.5), math.hypot(W, H) * 0.62)
    g.setColorAt(0.0, QColor(tone))
    g.setColorAt(0.55, QColor(tone))
    g.setColorAt(1.0, QColor(edge))
    p.fillRect(QRectF(0, 0, W, H), g)
    p.setPen(Qt.NoPen)
    for _ in range(14):                                   # plamy przy brzegach
        side = rng.integers(4)
        x = rng.uniform(0, W) if side < 2 else (rng.uniform(0, W * 0.12) if side == 2 else rng.uniform(W * 0.88, W))
        y = (rng.uniform(0, H * 0.12) if side == 0 else rng.uniform(H * 0.88, H)) if side < 2 else rng.uniform(0, H)
        r = rng.uniform(H * 0.05, H * 0.2)
        sg = QRadialGradient(QPointF(x, y), r)
        sg.setColorAt(0, col('#8a6a3a', rng.uniform(0.05, 0.14)))
        sg.setColorAt(1, col('#8a6a3a', 0))
        p.setBrush(sg)
        p.drawEllipse(QPointF(x, y), r, r)
    for (x1, y1, x2, y2) in ((0, 0, 0, 1), (0, 1, 0, 0), (0, 0, 1, 0), (1, 0, 0, 0)):  # przyciemnione krawędzie
        lg = QLinearGradient(QPointF(x1 * W, y1 * H), QPointF(x1 * W + (x2 - x1) * W * 0.05 if x1 != x2 else x1 * W,
                                                             y1 * H + (y2 - y1) * H * 0.07 if y1 != y2 else y1 * H))
        lg.setColorAt(0, col('#5a3d1a', 0.35))
        lg.setColorAt(1, col('#5a3d1a', 0))
        p.fillRect(QRectF(0, 0, W, H), lg)


def _smooth_noise(rng, W, H, cell):
    """Gładki szum wielkoskalowy: mała siatka -> dwukrotne powiększenie z rozmyciem."""
    gw, gh = max(2, W // cell + 2), max(2, H // cell + 2)
    low = rng.normal(0, 1, (gh, gw)).astype(np.float32)
    img = QImage(((low * 30 + 128).clip(0, 255)).astype(np.uint8).tobytes(), gw, gh, gw, QImage.Format_Grayscale8)
    mid = img.scaled(gw * 8, gh * 8, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    a = np.frombuffer(mid.constBits(), np.uint8).reshape(mid.height(), mid.bytesPerLine())[:, :mid.width()].astype(np.float32)
    for _ in range(3):                                     # rozmycie pudełkowe usuwa „kafelki”
        a = (a + np.roll(a, 2, 0) + np.roll(a, -2, 0) + np.roll(a, 2, 1) + np.roll(a, -2, 1)) / 5
    mid = QImage(a.clip(0, 255).astype(np.uint8).tobytes(), a.shape[1], a.shape[0], a.shape[1], QImage.Format_Grayscale8)
    full = mid.scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return (np.frombuffer(full.constBits(), np.uint8).reshape(H, full.bytesPerLine())[:, :W].astype(np.float32) - 128) / 30


def grain_warm(img, strength=7, seed=1):
    """Faktura pergaminu w ciepłej tonacji (brąz, nie szarość)."""
    rng = np.random.default_rng(seed)
    W, H = img.width(), img.height()
    n = 0.9 * _smooth_noise(rng, W, H, 160) + 0.45 * _smooth_noise(rng, W, H, 40)
    n += rng.normal(0, 0.35, (H, W)).astype(np.float32)
    img = img.convertToFormat(QImage.Format_RGB32)
    arr = np.frombuffer(img.bits(), np.uint8).reshape(H, img.bytesPerLine() // 4, 4)[:, :W, :3]
    tint = np.array([0.55, 0.8, 1.0], np.float32)           # BGR: najmocniej w czerwieni/żółci
    arr[:] = np.clip(arr.astype(np.float32) + n[..., None] * strength * tint, 0, 255).astype(np.uint8)
    return img


def ruling(p, W, H, mx, my, color):
    """Liniatura strony – cienkie podwójne linie wyznaczające kolumnę pisma."""
    p.save()
    p.setPen(QPen(color, 1.2))
    for d in (0, H * 0.008):
        p.drawLine(QPointF(mx - d, 0), QPointF(mx - d, H))
        p.drawLine(QPointF(W - mx + d, 0), QPointF(W - mx + d, H))
        p.drawLine(QPointF(0, my - d), QPointF(W, my - d))
        p.drawLine(QPointF(0, H - my + d), QPointF(W, H - my + d))
    p.restore()


def penwork(p, x, y0, y1, c1, c2, size, rng, horizontal=False):
    """Ornament piórkowy (fleuronnée): cienka łodyga z naprzemiennymi zawijasami i kropkami."""
    p.save()
    if horizontal:
        p.translate(x, y0)
        p.rotate(-90)
        p.translate(-x, -y0)
        y1 = y0 + (y1 - y0)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(c1, max(1.2, size * 0.06)))
    p.drawLine(QPointF(x, y0), QPointF(x, y1))
    p.setPen(QPen(c2, max(1.0, size * 0.04)))
    p.drawLine(QPointF(x + size * 0.18, y0), QPointF(x + size * 0.18, y1))
    k, y = 0, y0 + size * 0.6
    while y < y1 - size * 0.4:
        s = 1 if k % 2 == 0 else -1
        c = c1 if k % 2 == 0 else c2
        p.setPen(QPen(c, max(1.0, size * 0.045)))
        path = QPainterPath(QPointF(x, y))
        r0 = size * 0.55
        for j in range(1, 50):
            th = j / 49 * 2.6 * math.pi
            r = r0 * (1 - j / 56)
            path.lineTo(QPointF(x + s * (r0 - r * math.cos(th)), y - r * math.sin(th) * 0.9))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(x + s * r0 * 1.6, y + size * 0.15), size * 0.07, size * 0.07)
        p.setBrush(Qt.NoBrush)
        y += size * (1.1 + rng.random() * 0.3)
        k += 1
    p.restore()


def illuminated_initial(p, x, y, s, letter, rng, field=AZUR, letter_col=RUBRA, gold=True):
    """Inicjał iluminowany: złote pole, litera w kolorze, białe żyłki, ornament piórkowy."""
    p.save()
    if gold:
        g = QLinearGradient(QPointF(x, y), QPointF(x + s, y + s))
        g.setColorAt(0, QColor('#e9cf7a'))
        g.setColorAt(0.5, QColor(GOLD))
        g.setColorAt(1, QColor('#8f6a1c'))
        p.setBrush(g)
    else:
        p.setBrush(QColor(field))
    p.setPen(QPen(QColor('#3a2a14'), max(1.5, s * 0.012)))
    p.drawRect(QRectF(x, y, s, s))
    # wewnętrzne pole w kolorze z białym deseniem
    inset = s * 0.08
    p.setBrush(QColor(field))
    p.drawRect(QRectF(x + inset, y + inset, s - 2 * inset, s - 2 * inset))
    p.setPen(QPen(col('#ffffff', 0.55), max(1.0, s * 0.008)))
    for k in range(6):                               # białe wąsy (filigran)
        cx, cy = x + inset + rng.uniform(0.1, 0.9) * (s - 2 * inset), y + inset + rng.uniform(0.1, 0.9) * (s - 2 * inset)
        path = QPainterPath(QPointF(cx, cy))
        for j in range(1, 30):
            th = j / 29 * 2 * math.pi
            r = s * 0.05 * (1 - j / 34)
            path.lineTo(QPointF(cx + r * math.sin(th), cy - s * 0.05 + r * math.cos(th)))
        p.drawPath(path)
    f = QFont("DejaVu Serif")
    f.setPixelSize(int(s * 0.78))
    f.setBold(True)
    p.setFont(f)
    tp = QPainterPath()
    fm_rect = QRectF(x, y, s, s)
    tp.addText(QPointF(0, 0), f, letter)
    br = tp.boundingRect()
    tp.translate(fm_rect.center().x() - br.center().x(), fm_rect.center().y() - br.center().y())
    p.setPen(QPen(QColor('#f4ead2'), max(2.0, s * 0.02)))
    p.setBrush(QColor(letter_col))
    p.drawPath(tp)
    p.restore()


def mensural_staff(p, x, y, length, gap, line_color, ink, rng, lines=5, scale=1.0, custos=True):
    """Pięciolinia z notacją menzuralną (brewisy, semibrewisy-romby, minimy z laską)."""
    p.save()
    p.setPen(QPen(line_color, max(1.2, gap * 0.08)))
    for i in range(lines):
        p.drawLine(QPointF(x, y + i * gap), QPointF(x + length, y + i * gap))
    s = gap * 0.9 * scale
    stem = QPen(ink, max(1.2, gap * 0.1))
    cx = x + gap * 0.8
    # klucz C
    p.setPen(stem)
    p.drawLine(QPointF(cx, y + gap * 0.5), QPointF(cx, y + gap * 3.5))
    p.setPen(Qt.NoPen)
    p.setBrush(ink)
    p.drawRect(QRectF(cx + gap * 0.1, y + gap * 1.25, s * 0.7, s * 0.5))
    p.drawRect(QRectF(cx + gap * 0.1, y + gap * 2.25, s * 0.7, s * 0.5))
    cx += gap * 2.2
    pos = int(rng.integers(2, 7))
    while cx < x + length - gap * 2.0:
        pos = int(np.clip(pos + rng.integers(-2, 3), 0, 2 * (lines - 1)))
        cy = y + pos * gap / 2
        kind = rng.choice(['brevis', 'semibrevis', 'minima', 'minima', 'ligatura', 'pausa'], p=[.18, .27, .25, .1, .12, .08])
        p.setPen(Qt.NoPen)
        p.setBrush(ink)
        if kind == 'brevis':
            p.drawRect(QRectF(cx - s * 0.6, cy - s * 0.42, s * 1.2, s * 0.84))
            cx += gap * 1.0
        elif kind in ('semibrevis', 'minima'):
            p.drawPolygon(QPolygonF([QPointF(cx, cy - s * 0.55), QPointF(cx + s * 0.45, cy), QPointF(cx, cy + s * 0.55),
                                     QPointF(cx - s * 0.45, cy)]))
            if kind == 'minima':
                p.setPen(stem)
                p.drawLine(QPointF(cx, cy - s * 0.5), QPointF(cx, cy - gap * 2.6))
        elif kind == 'ligatura':
            pos2 = int(np.clip(pos + rng.choice([-2, -1, 1, 2]), 0, 2 * (lines - 1)))
            cy2 = y + pos2 * gap / 2
            p.drawRect(QRectF(cx - s * 0.6, cy - s * 0.42, s * 1.1, s * 0.84))
            p.drawRect(QRectF(cx + s * 0.5, cy2 - s * 0.42, s * 1.1, s * 0.84))
            p.setPen(stem)
            p.drawLine(QPointF(cx + s * 0.5, cy), QPointF(cx + s * 0.5, cy2))
            p.drawLine(QPointF(cx - s * 0.6, cy), QPointF(cx - s * 0.6, cy + gap * 1.6))
            cx += s * 1.2
            pos = pos2
        else:
            p.drawRect(QRectF(cx - gap * 0.12, y + gap, gap * 0.24, gap))
        cx += gap * (1.25 + rng.random() * 0.8)
    if custos:                                     # kustosz na końcu linii
        p.setPen(QPen(ink, max(1.0, gap * 0.08)))
        cy = y + pos * gap / 2
        path = QPainterPath(QPointF(x + length - gap * 1.2, cy))
        for j in range(4):
            path.lineTo(QPointF(x + length - gap * 1.2 + (j + 0.5) * gap * 0.18, cy + (-1) ** j * gap * 0.25))
        path.lineTo(QPointF(x + length - gap * 0.3, cy - gap * 1.2))
        p.drawPath(path)
    p.restore()


def flower(p, x, y, r, petal, center, n=5, rot=0.0):
    p.save()
    p.setPen(QPen(col('#3a2a14', 0.6), max(0.8, r * 0.06)))
    p.setBrush(QColor(petal))
    for k in range(n):
        a = rot + k * 2 * math.pi / n
        p.drawEllipse(QPointF(x + math.cos(a) * r * 0.6, y + math.sin(a) * r * 0.6), r * 0.48, r * 0.48)
    p.setBrush(QColor(center))
    p.drawEllipse(QPointF(x, y), r * 0.35, r * 0.35)
    p.restore()


def vine_border(p, x0, y0, x1, y1, w, rng, palette):
    """Bordiura roślinna (styl renesansowy): falująca złota łodyga, liście, kwiaty, złote kropki."""
    p.save()
    horizontal = abs(x1 - x0) > abs(y1 - y0)
    L = abs(x1 - x0) if horizontal else abs(y1 - y0)
    steps = int(L / (w * 0.08))
    pts = []
    for i in range(steps + 1):
        t = i / steps
        a = t * L
        o = w * 0.32 * math.sin(t * L / (w * 1.4) * math.pi)
        pts.append((x0 + a, y0 + o) if horizontal else (x0 + o, y0 + a))
    path = QPainterPath(QPointF(*pts[0]))
    for q in pts[1:]:
        path.lineTo(QPointF(*q))
    p.setPen(QPen(QColor('#8a6a22'), max(2.0, w * 0.05)))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(QPen(QColor(GOLD), max(1.2, w * 0.025)))
    p.drawPath(path)
    k = 0
    for i in range(3, len(pts) - 3, max(3, int(w * 0.9 / (w * 0.08)))):
        px_, py_ = pts[i]
        side = 1 if k % 2 == 0 else -1
        ang = (math.pi / 2 if horizontal else 0) * side + (0 if horizontal else (math.pi if side < 0 else 0))
        p.setPen(QPen(QColor('#2f4a1e'), 1.2))
        p.setBrush(QColor('#4f7a2e'))
        p.drawPath(leaf_path(px_, py_, ang + 0.5 * side, w * 0.38, w * 0.12))
        if k % 3 == 1:
            fx, fy = px_ + math.cos(ang) * w * 0.32, py_ + math.sin(ang) * w * 0.32
            c = palette[k % len(palette)]
            flower(p, fx, fy, w * 0.16, c, GOLD, n=5, rot=rng.uniform(0, 1))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(GOLD))
            for d in range(3):
                p.drawEllipse(QPointF(px_ - math.cos(ang) * w * (0.2 + d * 0.1), py_ - math.sin(ang) * w * (0.2 + d * 0.1)),
                              w * 0.03, w * 0.03)
        k += 1
    p.restore()


def text_underlay(p, x, y, length, h, rng, color):
    """Wiersz tekstu pod nutami – imitacja minuskuły gotyckiej (nieczytelna)."""
    manuscript_lines(p, x, y, length, h, color, rng, 1)


def t_jasny_pergamin(p, W, H, rng):
    parchment(p, W, H, rng)
    ruling(p, W, H, H * 0.07, H * 0.06, col(RUBRA, 0.28))


def t_jasny_gradual(p, W, H, rng):
    parchment(p, W, H, rng)
    gap = H * 0.024
    m = H * 0.045
    ini = gap * 5.2
    illuminated_initial(p, m * 1.3, m, ini, "A", rng)
    penwork(p, m * 0.75, m + ini + gap, H - m * 2.2, col(RUBRA, 0.85), col(AZUR, 0.85), gap * 1.3, rng)
    x0 = m * 1.3 + ini + gap * 1.2
    neume_staff(p, x0, m + gap * 0.4, W - x0 - m * 1.3, gap, col(RUBRA, 0.9), col(INK, 0.92), rng)
    text_underlay(p, x0 + gap, m + gap * 4.6, W - x0 - m * 2, gap * 0.95, rng, col(INK, 0.7))
    neume_staff(p, m * 1.6, H - m - gap * 5.0, W - m * 2.9, gap, col(RUBRA, 0.9), col(INK, 0.92), rng)
    text_underlay(p, m * 1.6 + gap, H - m - gap * 0.6, W - m * 3.4, gap * 0.95, rng, col(INK, 0.7))


def t_jasny_iluminacja(p, W, H, rng):
    parchment(p, W, H, rng, tone='#f3e9d2')
    w = H * 0.085
    pal = ['#b3261e', AZUR, '#c06f9a', '#d8a326']
    # bordiura: lewa i dolna pełna, górna krótka – jak w księgach godzinek
    p.setPen(QPen(col(GOLD, 0.9), 2))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(w * 0.45, w * 0.45, W - w * 0.9, H - w * 0.9))
    vine_border(p, w, w * 1.2, w, H - w * 1.2, w, rng, pal)
    vine_border(p, w * 1.6, H - w, W - w * 1.6, H - w, w, rng, pal)
    vine_border(p, W - w, H - w * 1.4, W - w, H * 0.55, w, rng, pal)
    illuminated_initial(p, w * 1.75, w * 0.85, w * 1.6, "S", rng, field='#7a1f1a', letter_col=AZUR)
    penwork(p, w * 1.75 + w * 1.6 + w * 0.3, w * 1.1, w * 1.1 + W * 0.45, col(RUBRA, 0.8), col(AZUR, 0.8), w * 0.32, rng,
            horizontal=True)
    for (x, y) in ((W - w, w), (w, H - w)):
        flower(p, x, y, w * 0.35, '#b3261e', GOLD, n=6)


def t_jasny_choral_renesans(p, W, H, rng):
    parchment(p, W, H, rng, tone='#efe2c2', edge='#b8955c')
    gap = H * 0.022
    m = H * 0.04
    ini = gap * 7
    illuminated_initial(p, m * 1.2, m * 0.9, ini, "K", rng, field=AZUR, letter_col='#a8291f')
    penwork(p, m * 1.2 + ini * 0.25, m * 0.9 + ini + gap * 0.5, H * 0.62, col(RUBRA, 0.75), col(AZUR, 0.75), gap, rng)
    x0 = m * 1.2 + ini + gap * 2.2
    mensural_staff(p, x0, m + gap * 0.3, W - x0 - m * 1.2, gap, col(RUBRA, 0.9), col(INK, 0.92), rng)
    text_underlay(p, x0 + gap, m + gap * 6.0, W - x0 - m * 2, gap, rng, col(INK, 0.65))
    mensural_staff(p, m * 1.5, H - m - gap * 6.4, W - m * 2.7, gap, col(RUBRA, 0.9), col(INK, 0.92), rng)
    text_underlay(p, m * 1.5 + gap, H - m - gap * 0.7, W - m * 3.2, gap, rng, col(INK, 0.65))
    # mały kwiatowy akcent w prawym dolnym rogu marginesu
    flower(p, W - m * 0.9, H - m * 0.9, gap * 0.9, '#b3261e', GOLD)


def t_jasny_kolonialny(p, W, H, rng):
    """Wielkie folio chórowe (styl hiszpańsko-kolonialny): grube czerwone linie, duże czarne nuty,
    inicjał w polu z szachownicą, kwiaty w narożnikach."""
    parchment(p, W, H, rng, tone='#ecdcb8', edge='#a9854d')
    gap = H * 0.03
    m = H * 0.04
    # górna i dolna linia pięciolinii – mniej linii, większe nuty jak w księgach chórowych
    ini = gap * 4.8
    # inicjał: szachownica czerwono-niebieska z literą
    x, y = m * 1.1, m * 0.9
    p.setPen(QPen(col('#2a1a0c', 0.9), 2))
    cells = 6
    for i in range(cells):
        for j in range(cells):
            p.setBrush(QColor('#9e2a1f' if (i + j) % 2 else '#2b4f8f'))
            p.drawRect(QRectF(x + i * ini / cells, y + j * ini / cells, ini / cells, ini / cells))
    f = QFont("DejaVu Serif")
    f.setPixelSize(int(ini * 0.85))
    f.setBold(True)
    tp = QPainterPath()
    tp.addText(QPointF(0, 0), f, "G")
    br = tp.boundingRect()
    tp.translate(x + ini / 2 - br.center().x(), y + ini / 2 - br.center().y())
    p.setPen(QPen(QColor('#2a1a0c'), 3))
    p.setBrush(QColor('#e8cf7a'))
    p.drawPath(tp)
    flower(p, x + ini, y + ini, gap * 0.8, '#d8a326', '#9e2a1f', n=6)
    x0 = x + ini + gap * 1.2
    mensural_staff(p, x0, m + gap * 0.2, W - x0 - m * 1.1, gap, col('#b0281c', 0.95), col(INK, 0.95), rng,
                   lines=5, scale=1.15)
    mensural_staff(p, m * 1.3, H - m - gap * 4.4, W - m * 2.6, gap, col('#b0281c', 0.95), col(INK, 0.95), rng,
                   lines=5, scale=1.15)
    # foliacja (numer karty) w prawym górnym rogu – rzymskie cyfry jak w księgach
    f2 = QFont("DejaVu Serif")
    f2.setPixelSize(int(gap * 0.9))
    p.setFont(f2)
    p.setPen(col('#9e2a1f', 0.85))
    p.drawText(QRectF(W - m * 4.5, H - m * 1.0, m * 3, gap), Qt.AlignRight | Qt.AlignVCenter, "fol. XLII")
    for (cx, cy) in ((W - m * 0.7, H - m * 0.55), (m * 0.7, H - m * 0.55)):
        flower(p, cx, cy, gap * 0.55, '#9e2a1f', GOLD, n=5)


# presety: kolory tekstu i marginesy (procent szer./wys.), żeby tekst nie wchodził na ozdobniki
PRESETS_DARK = {'kolor_tekstu': '#ffffff', 'kolor_refrenu': '#ffff99', 'jasne': False}
PRESETS_LIGHT = {'kolor_tekstu': '#2b1d12', 'kolor_refrenu': '#a3201c', 'jasne': True}
PRESETS = {
    'kodeks': dict(PRESETS_DARK, margines_x=8, margines_y=17),
    'iluminacja': dict(PRESETS_DARK, margines_x=12, margines_y=9),
    'adwent': dict(PRESETS_DARK, margines_x=8, margines_y=7),
    'boze_narodzenie': dict(PRESETS_DARK, margines_x=9, margines_y=7),
    'maryjne': dict(PRESETS_DARK, margines_x=10, margines_y=10),
    'wielki_post': dict(PRESETS_DARK, margines_x=10, margines_y=7),
    'wielkanoc': dict(PRESETS_DARK, margines_x=10, margines_y=12),
    'duch_swiety': dict(PRESETS_DARK, margines_x=8, margines_y=12),
    'gotyk': dict(PRESETS_DARK, margines_x=8, margines_y=20),
    'witraz': dict(PRESETS_DARK, margines_x=14, margines_y=6),
    'czyste': dict(PRESETS_DARK, margines_x=7, margines_y=5),
    'jasny_pergamin': dict(PRESETS_LIGHT, margines_x=9, margines_y=8),
    'jasny_gradual': dict(PRESETS_LIGHT, margines_x=8, margines_y=19),
    'jasny_iluminacja': dict(PRESETS_LIGHT, margines_x=12, margines_y=21),
    'jasny_choral_renesans': dict(PRESETS_LIGHT, margines_x=8, margines_y=21),
    'jasny_kolonialny': dict(PRESETS_LIGHT, margines_x=8, margines_y=23),
}


THEMES = {
    'kodeks': (t_kodeks, 7), 'iluminacja': (t_iluminacja, 4), 'adwent': (t_adwent, 4),
    'boze_narodzenie': (t_boze_narodzenie, 3), 'maryjne': (t_maryjne, 3), 'wielki_post': (t_wielki_post, 3),
    'wielkanoc': (t_wielkanoc, 3), 'duch_swiety': (t_duch_swiety, 3), 'gotyk': (t_gotyk, 4),
    'witraz': (t_witraz, 3), 'czyste': (t_czyste, 3),
    'jasny_pergamin': (t_jasny_pergamin, -6), 'jasny_gradual': (t_jasny_gradual, -6),
    'jasny_iluminacja': (t_jasny_iluminacja, -6), 'jasny_choral_renesans': (t_jasny_choral_renesans, -6),
    'jasny_kolonialny': (t_jasny_kolonialny, -7),
}


def render(name, W, H, seed=7):
    fn, grain_strength = THEMES[name]
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(Qt.black)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    fn(p, W, H, np.random.default_rng(seed))
    p.end()
    if grain_strength < 0:                       # jasne: ciepłe ziarno pergaminu
        return grain_warm(img, -grain_strength, seed)
    return grain(img, grain_strength, seed)


def main(out_dir="tla", only=None):
    import json
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "tla.json"), "w", encoding="utf-8") as f:
        json.dump(PRESETS, f, ensure_ascii=False, indent=1)
    for name in THEMES:
        if only and name not in only:
            continue
        for tag, (W, H) in SIZES.items():
            path = os.path.join(out_dir, f"{name}_{tag}.jpg")
            render(name, W, H).save(path, "JPG", 88)
            print("zapisano", path)
    return app


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tla", sys.argv[2:] or None)
