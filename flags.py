# -*- coding: utf-8 -*-
"""Banderas emoji por equipo (offline, sin dependencias)."""

FLAGS = {
    "Alemania": "🇩🇪",
    "Arabia Saudita": "🇸🇦",
    "Argelia": "🇩🇿",
    "Argentina": "🇦🇷",
    "Australia": "🇦🇺",
    "Austria": "🇦🇹",
    "Bosnia-Herzegovina": "🇧🇦",
    "Brasil": "🇧🇷",
    "Bélgica": "🇧🇪",
    "Cabo Verde": "🇨🇻",
    "Canadá": "🇨🇦",
    "Chequia": "🇨🇿",
    "Colombia": "🇨🇴",
    "Corea del Sur": "🇰🇷",
    "Costa de Marfil": "🇨🇮",
    "Croacia": "🇭🇷",
    "Curazao": "🇨🇼",
    "DR Congo": "🇨🇩",
    "EE.UU.": "🇺🇸",
    "Ecuador": "🇪🇨",
    "Egipto": "🇪🇬",
    "España": "🇪🇸",
    "Francia": "🇫🇷",
    "Ghana": "🇬🇭",
    "Haití": "🇭🇹",
    "Iraq": "🇮🇶",
    "Irán": "🇮🇷",
    "Japón": "🇯🇵",
    "Jordania": "🇯🇴",
    "Marruecos": "🇲🇦",
    "México": "🇲🇽",
    "Noruega": "🇳🇴",
    "Nueva Zelanda": "🇳🇿",
    "Panamá": "🇵🇦",
    "Paraguay": "🇵🇾",
    "Países Bajos": "🇳🇱",
    "Portugal": "🇵🇹",
    "Qatar": "🇶🇦",
    "Senegal": "🇸🇳",
    "Sudáfrica": "🇿🇦",
    "Suecia": "🇸🇪",
    "Suiza": "🇨🇭",
    "Turquía": "🇹🇷",
    "Túnez": "🇹🇳",
    "Uruguay": "🇺🇾",
    "Uzbekistán": "🇺🇿",
    "Inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Escocia": "🏴󠁧󠁢󠁳󠁣󠁴󠁿"
}

def flag(team):
    """Devuelve el emoji de bandera del equipo, o cadena vacia si no hay."""
    return FLAGS.get((team or "").strip(), "")

def with_flag(team):
    """'🇲🇽 México' — bandera + nombre, o solo el nombre si no hay bandera."""
    t = (team or "").strip()
    fl = FLAGS.get(t, "")
    return f"{fl} {t}".strip() if t else ""


# ---------------------------------------------------------------------------
# Banderas como imagen PNG (para las tarjetas generadas con Pillow).
# Los archivos viven en assets/flags/<codigo>.png (fuente: flag-icons, MIT).
# ---------------------------------------------------------------------------
import os

ISO = {
    "Alemania": "de", "Arabia Saudita": "sa", "Argelia": "dz", "Argentina": "ar",
    "Australia": "au", "Austria": "at", "Bosnia-Herzegovina": "ba", "Brasil": "br",
    "Bélgica": "be", "Cabo Verde": "cv", "Canadá": "ca", "Chequia": "cz",
    "Colombia": "co", "Corea del Sur": "kr", "Costa de Marfil": "ci", "Croacia": "hr",
    "Curazao": "cw", "DR Congo": "cd", "EE.UU.": "us", "Ecuador": "ec",
    "Egipto": "eg", "España": "es", "Francia": "fr", "Ghana": "gh",
    "Haití": "ht", "Iraq": "iq", "Irán": "ir", "Japón": "jp",
    "Jordania": "jo", "Marruecos": "ma", "México": "mx", "Noruega": "no",
    "Nueva Zelanda": "nz", "Panamá": "pa", "Paraguay": "py", "Países Bajos": "nl",
    "Portugal": "pt", "Qatar": "qa", "Senegal": "sn", "Sudáfrica": "za",
    "Suecia": "se", "Suiza": "ch", "Turquía": "tr", "Túnez": "tn",
    "Uruguay": "uy", "Uzbekistán": "uz",
    "Inglaterra": "gb-eng", "Escocia": "gb-sct",
}

_FLAGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "flags")
_PNG_CACHE = {}


def flag_png_path(team):
    """Ruta al PNG de la bandera del equipo, o None si no existe."""
    code = ISO.get((team or "").strip())
    if not code:
        return None
    path = os.path.join(_FLAGS_DIR, f"{code}.png")
    return path if os.path.exists(path) else None


def flag_png(team, height=40):
    """Devuelve PIL.Image RGBA de la bandera escalada a `height`, o None.
    Requiere Pillow; se importa de forma diferida."""
    path = flag_png_path(team)
    if not path:
        return None
    key = (path, height)
    if key in _PNG_CACHE:
        return _PNG_CACHE[key]
    try:
        from PIL import Image
        im = Image.open(path).convert("RGBA")
        w, h = im.size
        scale = height / h
        im = im.resize((max(1, int(w * scale)), height), Image.LANCZOS)
        _PNG_CACHE[key] = im
        return im
    except Exception:
        return None
