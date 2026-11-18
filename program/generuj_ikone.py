#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
# (kod: GPL-3.0-or-later; tworzone obrazy ikony: CC BY-SA 4.0 – patrz niżej i ikony/LICENSE-ikona.txt)
#
# Ikona programu Liber Canticorum: czerwone inicjałowe „C” z rękopiśmiennego kancjonału z 1586 r.
# („Cantional písnek rozmaitých a nábožných…”), na karcie pergaminu.
#
# Źródło litery: fotografia karty tytułowej, autor: Mkonik80 – praca własna, licencja CC BY-SA 4.0,
# https://commons.wikimedia.org/wiki/Special:Redirect/page/56366360
# Litera została wycięta ze zdjęcia, oczyszczona z tła i ornamentów piórkiem, a jej kształt
# zamieniony na wektor (ikony/zrodla/C_cantional_1586.svg). Ikona – utwór zależny – jest na licencji
# CC BY-SA 4.0 (zgodnej w jedną stronę z GPL-3.0 programu).
"""
Użycie:  python generuj_ikone.py [folder]   ->  liber_canticorum.svg, liber_canticorum_<rozmiar>.png, .ico
"""
import os
import sys

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_SVG = os.path.join(HERE, "ikony", "zrodla", "C_cantional_1586.svg")
SRC_INK = os.path.join(HERE, "ikony", "zrodla", "C_cantional_1586_tusz.png")
INK = QColor('#b0392a')                  # cynober rubryk (nieco nasycony względem zdjęcia – czytelność)
PARCH_IN, PARCH_OUT, EDGE = QColor('#f5ebd3'), QColor('#dcc49b'), QColor('#8a6a3c')

_renderer = None
_bbox = None


def renderer():
    global _renderer
    if _renderer is None:
        from PySide6.QtSvg import QSvgRenderer
        _renderer = QSvgRenderer(SRC_SVG)
    return _renderer


def letter_bbox():
    """Prostokąt litery w układzie viewBox pliku SVG (liczony z rastra w dużej rozdzielczości)."""
    global _bbox
    if _bbox is None:
        r = renderer()
        vb = r.viewBoxF()
        n = 1024
        img = QImage(n, n, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        r.render(p, QRectF(0, 0, n, n))
        p.end()
        xs, ys = [], []
        for y in range(0, n, 2):
            for x in range(0, n, 2):
                if img.pixelColor(x, y).alpha() > 60:
                    xs.append(x)
                    ys.append(y)
        sx, sy = vb.width() / n, vb.height() / n
        _bbox = QRectF(min(xs) * sx, min(ys) * sy, (max(xs) - min(xs)) * sx, (max(ys) - min(ys)) * sy)
    return _bbox


def letter_rect(S):
    """Gdzie narysować cały viewBox SVG, żeby litera zajęła ~76 % kafelka i stała pośrodku (optycznie)."""
    vb = renderer().viewBoxF()
    bb = letter_bbox()
    scale = S * 0.76 / max(bb.width(), bb.height())
    cx, cy = S * 0.5, S * 0.505
    x = cx - (bb.x() + bb.width() / 2) * scale
    y = cy - (bb.y() + bb.height() / 2) * scale
    return QRectF(x, y, vb.width() * scale, vb.height() * scale)


def tile_path(S):
    path = QPainterPath()
    m = S * 0.03
    path.addRoundedRect(QRectF(m, m, S - 2 * m, S - 2 * m), S * 0.19, S * 0.19)
    return path


def draw_tile(p, S, textured):
    tile = tile_path(S)
    g = QRadialGradient(QPointF(S * 0.45, S * 0.42), S * 0.75)
    g.setColorAt(0.0, PARCH_IN)
    g.setColorAt(0.6, QColor('#efe2c4'))
    g.setColorAt(1.0, PARCH_OUT)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawPath(tile)
    if textured:                                       # przypalone brzegi karty
        p.save()
        p.setClipPath(tile)
        for (x1, y1, x2, y2) in ((0, 0, 0.09, 0), (1, 0, 0.91, 0), (0, 0, 0, 0.09), (0, 1, 0, 0.91)):
            lg = QLinearGradient(QPointF(x1 * S, y1 * S), QPointF((x2 if x2 else x1) * S, (y2 if y2 else y1) * S))
            lg.setColorAt(0, QColor(110, 75, 30, 70))
            lg.setColorAt(1, QColor(110, 75, 30, 0))
            p.fillRect(QRectF(0, 0, S, S), lg)
        p.restore()
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(EDGE, max(1.0, S * 0.012)))
    p.drawPath(tile)


def letter_layer(S, textured):
    """Litera jako obraz ARGB: kształt z SVG, wypełniony tuszem (tekstura ze zdjęcia lub jednolity kolor)."""
    img = QImage(S, S, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    rect = letter_rect(S)
    if textured and os.path.exists(SRC_INK):
        ink = QImage(SRC_INK)
        p.drawImage(rect, ink)                         # zdjęcie tuszu (ten sam wycinek co maska)
        p.fillRect(QRectF(0, 0, S, S), QColor(INK.red(), INK.green(), INK.blue(), 120))   # ujednolicenie barwy
    else:
        p.fillRect(QRectF(0, 0, S, S), INK)
    mask = QImage(S, S, QImage.Format_ARGB32_Premultiplied)
    mask.fill(Qt.transparent)
    mp = QPainter(mask)
    mp.setRenderHint(QPainter.Antialiasing)
    renderer().render(mp, rect)
    mp.end()
    p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    p.drawImage(0, 0, mask)
    p.end()
    return img, mask


def render_png(S):
    textured = S >= 96
    img = QImage(S, S, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    draw_tile(p, S, textured)
    if textured:
        try:                                           # ziarno pergaminu (z generatora teł)
            sys.path.insert(0, HERE)
            from generuj_tla import grain_warm
            p.end()
            alpha = img.convertToFormat(QImage.Format_ARGB32).alphaChannel() if hasattr(img, 'alphaChannel') else None
            g = grain_warm(img.convertToFormat(QImage.Format_RGB32), 5, 3).convertToFormat(QImage.Format_ARGB32_Premultiplied)
            img = QImage(S, S, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setClipPath(tile_path(S))
            p.drawImage(0, 0, g)
            p.setClipping(False)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(EDGE, max(1.0, S * 0.012)))
            p.drawPath(tile_path(S))
            _ = alpha
        except ImportError:
            pass
    layer, mask = letter_layer(S, textured)
    if textured:                                       # delikatne wsiąknięcie tuszu w pergamin
        from PySide6.QtGui import QPixmap
        soft = QPixmap.fromImage(mask).scaled(S // 3, S // 3, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        p.setOpacity(0.10)
        p.drawPixmap(QRectF(S * 0.004, S * 0.006, S, S), soft, QRectF(soft.rect()))
        p.setOpacity(1.0)
    p.drawImage(0, 0, layer)
    p.end()
    return img


def write_svg(path, S=512):
    """Wersja wektorowa: pergamin (gradient) + litera w jednolitym kolorze tuszu."""
    from PySide6.QtSvg import QSvgGenerator
    gen = QSvgGenerator()
    gen.setFileName(path)
    gen.setSize(QSize(S, S))
    gen.setViewBox(QRectF(0, 0, S, S))
    gen.setTitle("Liber Canticorum")
    gen.setDescription("Inicjał C z kancjonału z 1586 r. (fot. Mkonik80, CC BY-SA 4.0)")
    p = QPainter(gen)
    p.setRenderHint(QPainter.Antialiasing)
    draw_tile(p, S, False)
    # litera: kolor przez warstwę – QSvgRenderer rysuje ścieżki w kolorze z pliku, więc podmieniamy kolor
    from PySide6.QtSvg import QSvgRenderer
    with open(SRC_SVG, encoding="utf-8") as f:
        svg = f.read().replace('fill="#000000"', f'fill="{INK.name()}"')
    QSvgRenderer(svg.encode("utf-8")).render(p, letter_rect(S))
    p.end()


def main(out="ikony"):
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    os.makedirs(out, exist_ok=True)
    write_svg(os.path.join(out, "liber_canticorum.svg"))
    for s in (16, 24, 32, 48, 64, 128, 256, 512):
        render_png(s).save(os.path.join(out, f"liber_canticorum_{s}.png"))
    try:
        from PIL import Image
        big = Image.open(os.path.join(out, "liber_canticorum_256.png"))
        imgs = {s: Image.open(os.path.join(out, f"liber_canticorum_{s}.png")) for s in (16, 24, 32, 48, 64, 128)}
        big.save(os.path.join(out, "liber_canticorum.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
                 append_images=list(imgs.values()))
    except ImportError:
        pass
    return app


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ikony")
