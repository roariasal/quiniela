# -*- coding: utf-8 -*-
"""
Genera el JSON compacto para compartir con el administrador por WhatsApp.
Contiene, por partido, las predicciones del jugador y las variables que
el organizador definio ese dia (estructura fija: v1..v4 + marcador).
"""
import json
from wc_data import GROUP_MATCHES, KNOCKOUT

ROUND_LABEL = {
    "R32": "Ronda de 32", "R16": "Octavos", "QF": "Cuartos",
    "SF": "Semifinal", "P3": "Tercer Lugar", "F": "Final",
}


def _has_variable_data(v):
    return v and any((v.get(k) or "").strip()
                     for k in ("v1", "v2", "v3", "v4", "marcador"))


def build_share_payload(state, bracket=None, only_with_data=True):
    """
    Construye el dict que se serializa a JSON para WhatsApp.
    Por defecto incluye solo partidos donde el jugador capturo algo
    (prediccion o variables), para mantener el mensaje compacto.
    """
    payload = {
        "quiniela": "Mundial 2026",
        "jugador": state.get("owner", ""),
        "actualizado": state.get("updated"),
        "partidos": [],
    }

    group_results = state.get("group_results", {})
    ko_winners = state.get("ko_winners", {})
    variables = state.get("variables", {})

    # Fase de grupos
    for m in GROUP_MATCHES:
        n = str(m["n"])
        res = group_results.get(n)
        var = variables.get(n)
        if only_with_data and not (res and res.get("outcome")) and not _has_variable_data(var):
            continue
        entry = {
            "n": m["n"],
            "fase": "Grupos",
            "partido": f"{m['local']} vs {m['visit']}",
            "fecha": m["fecha"],
        }
        if res and res.get("outcome"):
            entry["prediccion"] = res["outcome"]  # 1 / X / 2
        if _has_variable_data(var):
            entry["variables"] = _clean_vars(var)
        payload["partidos"].append(entry)

    # Fase eliminatoria
    bracket_by_n = {str(b["n"]): b for b in (bracket or [])}
    for m in KNOCKOUT:
        n = str(m["n"])
        win = ko_winners.get(n)
        var = variables.get(n)
        if only_with_data and not win and not _has_variable_data(var):
            continue
        b = bracket_by_n.get(n)
        if b and b.get("t1") and b.get("t2"):
            matchup = f"{b['t1']} vs {b['t2']}"
        else:
            matchup = f"{m['t1']} vs {m['t2']}"
        entry = {
            "n": m["n"],
            "fase": ROUND_LABEL.get(m["round"], m["round"]),
            "partido": matchup,
            "fecha": m["fecha"],
        }
        if win:
            entry["ganador"] = win
        if _has_variable_data(var):
            entry["variables"] = _clean_vars(var)
        payload["partidos"].append(entry)

    return payload


def _clean_vars(v):
    out = {}
    for k in ("v1", "v2", "v3", "v4", "marcador"):
        val = (v.get(k) or "").strip()
        if val:
            out[k] = val
    return out


def to_json(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)
