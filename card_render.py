# -*- coding: utf-8 -*-
"""
Genera el resumen legible de un partido para compartir con el administrador,
en dos formatos:
  - texto formateado para WhatsApp (whatsapp_text)
  - imagen PNG tipo tarjeta (png_card), via Pillow

Diseño de la tarjeta: título del partido (con banderas), pastilla de
predicción/ganador, lista de variables (nombre → valor) y marcador destacado.
"""
import io
import os
import glob

from PIL import Image, ImageDraw, ImageFont
from flags import flag, with_flag

# --- fuentes ---
def _find_font(names):
    """Busca un archivo de fuente por nombre en las rutas típicas de Linux.
    `names` es una lista de nombres de archivo (sin ruta), en orden de preferencia."""
    roots = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        "/Library/Fonts",            # macOS
        "/System/Library/Fonts",     # macOS
        "C:/Windows/Fonts",          # Windows
    ]
    for name in names:
        for root in roots:
            hits = glob.glob(os.path.join(root, "**", name), recursive=True)
            if hits:
                return hits[0]
    return None


_SANS = _find_font([
    "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
    "NotoSans-Regular.ttf", "Arial.ttf", "arial.ttf",
])
_SANS_BOLD = _find_font([
    "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",
    "NotoSans-Bold.ttf", "Arial-Bold.ttf", "arialbd.ttf",
]) or _SANS  # si no hay bold, usa el regular
_EMOJI = _find_font(["NotoColorEmoji.ttf"])

# NotoColorEmoji en Pillow SOLO carga a tamaño 109; se reescala despues.
_EMOJI_NATIVE = 109

# cache simple de fuentes ya cargadas
_FONT_CACHE = {}


def _font(bold=False, size=22):
    key = (bold, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = _SANS_BOLD if bold else _SANS
    try:
        if path:
            f = ImageFont.truetype(path, size)
        else:
            # último recurso: fuente embebida de Pillow (siempre disponible,
            # aunque no escala bien ni soporta acentos perfectamente)
            f = ImageFont.load_default(size=size)
    except Exception:
        try:
            f = ImageFont.load_default(size=size)
        except Exception:
            f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _flag_image(team, target_h):
    """Devuelve una imagen RGBA de la bandera del equipo, escalada a target_h,
    o None si no hay bandera o no hay fuente emoji."""
    fl = flag(team)
    if not fl or not _EMOJI:
        return None
    try:
        ef = ImageFont.truetype(_EMOJI, _EMOJI_NATIVE)
        tmp = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        d.text((0, 0), fl, font=ef, embedded_color=True)
        bbox = tmp.getbbox()
        if not bbox:
            return None
        cropped = tmp.crop(bbox)
        w, h = cropped.size
        scale = target_h / h
        return cropped.resize((max(1, int(w * scale)), target_h), Image.LANCZOS)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Datos del resumen (comun a texto e imagen)
# ---------------------------------------------------------------------------
def match_summary(entry):
    """Normaliza una entrada de export_share a campos para render.
    entry: dict con n, fase, partido, fecha, [prediccion|ganador], [variables], [marcador]."""
    pred = None
    if entry.get("prediccion"):
        code = entry["prediccion"]
        local, _, visit = entry["partido"].partition(" vs ")
        if code == "1":
            pred = ("Predicción", f"1 · Gana {local}")
        elif code == "2":
            pred = ("Predicción", f"2 · Gana {visit}")
        else:
            pred = ("Predicción", "X · Empate")
    elif entry.get("ganador"):
        pred = ("Ganador", entry["ganador"])

    variables = []
    for v in entry.get("variables", []):
        t = (v.get("titulo") or "").strip() or "Variable"
        val = (v.get("valor") or "").strip() or "—"
        variables.append((t, val))

    return {
        "n": entry.get("n"),
        "fase": entry.get("fase", ""),
        "fecha": entry.get("fecha", ""),
        "partido": entry.get("partido", ""),
        "pred": pred,
        "variables": variables,
        "marcador": (entry.get("marcador") or "").strip(),
    }


# ---------------------------------------------------------------------------
# Formato 1: texto WhatsApp
# ---------------------------------------------------------------------------
def whatsapp_text(entry, jugador=""):
    s = match_summary(entry)
    local, _, visit = s["partido"].partition(" vs ")
    titulo = f"{with_flag(local)} vs {with_flag(visit)}" if visit else s["partido"]
    lines = []
    head = "⚽ Quiniela Mundial 2026"
    if jugador:
        head += f" — {jugador}"
    lines.append(head)
    lines.append(titulo)
    lines.append(f"#{s['n']} · {s['fase']} · {s['fecha']}")
    lines.append("")
    if s["pred"]:
        label, value = s["pred"]
        if label == "Ganador":
            value = with_flag(value)
        lines.append(f"{label}: {value}")
    if s["marcador"]:
        lines.append(f"Marcador: {s['marcador']}")
    if s["variables"]:
        lines.append("")
        lines.append("📋 Variables")
        for t, val in s["variables"]:
            lines.append(f"• {t}: {val}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formato 2: imagen PNG (Pillow)
# ---------------------------------------------------------------------------
# Paleta deportiva (coincide con el theme)
_BG = (255, 255, 255)
_INK = (16, 36, 43)        # texto principal
_MUTED = (110, 120, 124)   # texto secundario
_LINE = (220, 230, 224)    # separadores
_GREEN = (10, 135, 84)
_GREEN_BG = (227, 244, 237)
_BLUE_BG = (227, 240, 250)
_BLUE_INK = (12, 68, 124)


def png_card(entry, jugador="", width=720):
    s = match_summary(entry)
    local, _, visit = s["partido"].partition(" vs ")

    pad = 34
    img = Image.new("RGB", (width, 1400), _BG)
    d = ImageDraw.Draw(img)
    y = pad

    f_head = _font(False, 20)
    f_title = _font(True, 30)
    f_meta = _font(False, 19)
    f_label = _font(False, 20)
    f_val = _font(True, 22)
    f_score = _font(True, 40)
    f_pill = _font(True, 21)

    # encabezado
    head = "⚽ Quiniela Mundial 2026" + (f" — {jugador}" if jugador else "")
    # quitamos el emoji del balon en imagen (evita doble-render); usamos texto
    head = head.replace("⚽ ", "")
    d.text((pad, y), head, font=f_head, fill=_GREEN)
    y += 40
    d.line([(pad, y), (width - pad, y)], fill=_LINE, width=2)
    y += 22

    # titulo del partido con banderas
    fh = 38
    x = pad
    fl_local = _flag_image(local, fh)
    if fl_local:
        img.paste(fl_local, (int(x), y), fl_local)
        x += fl_local.width + 10
    d.text((x, y + 2), local, font=f_title, fill=_INK)
    x += d.textlength(local, font=f_title) + 16
    d.text((x, y + 6), "vs", font=f_meta, fill=_MUTED)
    x += d.textlength("vs", font=f_meta) + 16
    fl_visit = _flag_image(visit, fh)
    if fl_visit:
        img.paste(fl_visit, (int(x), y), fl_visit)
        x += fl_visit.width + 10
    d.text((x, y + 2), visit, font=f_title, fill=_INK)
    y += 52

    d.text((pad, y), f"#{s['n']} · {s['fase']} · {s['fecha']}", font=f_meta, fill=_MUTED)
    y += 40

    # pastilla prediccion / ganador
    if s["pred"]:
        label, value = s["pred"]
        d.text((pad, y + 6), label, font=f_label, fill=_MUTED)
        lx = pad + d.textlength(label, font=f_label) + 16
        is_winner = (label == "Ganador")
        bg = _GREEN_BG if is_winner else _BLUE_BG
        ink = _GREEN if is_winner else _BLUE_INK
        # quitar bandera del texto de la pastilla para no romper (se dibuja aparte si gana)
        ptext = value
        tw = d.textlength(ptext, font=f_pill)
        d.rounded_rectangle([lx, y, lx + tw + 28, y + 36], radius=8, fill=bg)
        d.text((lx + 14, y + 6), ptext, font=f_pill, fill=ink)
        y += 54

    # variables
    if s["variables"]:
        d.line([(pad, y), (width - pad, y)], fill=_LINE, width=2)
        y += 18
        for i, (t, val) in enumerate(s["variables"]):
            if i > 0:
                d.line([(pad, y), (width - pad, y)], fill=_LINE, width=1)
                y += 12
            d.text((pad, y), t, font=f_label, fill=_MUTED)
            vw = d.textlength(val, font=f_val)
            d.text((width - pad - vw, y - 1), val, font=f_val, fill=_INK)
            y += 38
        y += 6

    # marcador
    if s["marcador"]:
        d.line([(pad, y), (width - pad, y)], fill=_LINE, width=2)
        y += 20
        d.text((pad, y + 12), "Marcador", font=f_label, fill=_MUTED)
        sc = s["marcador"]
        sw = d.textlength(sc, font=f_score)
        d.text((width - pad - sw, y), sc, font=f_score, fill=_INK)
        y += 60

    y += pad
    # recortar al alto real
    img = img.crop((0, 0, width, y))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
