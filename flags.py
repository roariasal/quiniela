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
