# -*- coding: utf-8 -*-
"""
Motor de la quiniela: calcula posiciones de grupo a partir de los resultados 1/X/2,
rankea los mejores terceros segun reglas FIFA (puntos), y propaga los ganadores de
la fase eliminatoria a traves de todos los cruces hasta el campeon.

El motor es PURO: recibe el estado de predicciones y devuelve estructuras calculadas.
No toca disco ni Streamlit. Esto mantiene la computacion separada del almacenamiento.
"""
from wc_data import GROUPS, GROUP_MATCHES, KNOCKOUT

# Puntos FIFA
WIN, DRAW, LOSS = 3, 1, 0

# -------------------------------------------------------------------------
# 1) TABLA DE POSICIONES POR GRUPO
# -------------------------------------------------------------------------
def _blank_row(team):
    return {"team": team, "PJ": 0, "G": 0, "E": 0, "P": 0,
            "GF": 0, "GC": 0, "DG": 0, "PTS": 0}


def compute_standings(results):
    """
    results: dict { match_n (str|int) : {"outcome": "1"|"X"|"2", "gf": int|None, "gc": int|None} }
        outcome es obligatorio para contar; gf/gc (goles local/visitante) son opcionales
        y solo se usan para el desempate por diferencia de goles.
    Devuelve: dict { group_letter : [filas ordenadas 1ro..4to] }
    """
    tables = {g: {t: _blank_row(t) for t in teams} for g, teams in GROUPS.items()}

    for m in GROUP_MATCHES:
        r = results.get(str(m["n"])) or results.get(m["n"])
        if not r or not r.get("outcome"):
            continue
        g = m["group"]
        loc, vis = m["local"], m["visit"]
        gl = _to_int(r.get("gf"))
        gv = _to_int(r.get("gc"))
        rl, rv = tables[g][loc], tables[g][vis]
        rl["PJ"] += 1; rv["PJ"] += 1
        if gl is not None and gv is not None:
            rl["GF"] += gl; rl["GC"] += gv
            rv["GF"] += gv; rv["GC"] += gl
        out = r["outcome"]
        if out == "1":
            rl["G"] += 1; rl["PTS"] += WIN; rv["P"] += 1
        elif out == "2":
            rv["G"] += 1; rv["PTS"] += WIN; rl["P"] += 1
        else:  # empate
            rl["E"] += 1; rv["E"] += 1
            rl["PTS"] += DRAW; rv["PTS"] += DRAW

    out_tables = {}
    for g, rows in tables.items():
        lst = list(rows.values())
        for row in lst:
            row["DG"] = row["GF"] - row["GC"]
        lst.sort(key=_standings_sort_key, reverse=True)
        out_tables[g] = lst
    return out_tables


def _standings_sort_key(row):
    # Orden FIFA simplificado: PTS, DG, GF
    return (row["PTS"], row["DG"], row["GF"])


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# -------------------------------------------------------------------------
# 2) RANKING DE MEJORES TERCEROS (reglas FIFA: por puntos)
# -------------------------------------------------------------------------
def rank_third_places(standings):
    """
    Devuelve lista ordenada de los 12 terceros lugares (mejor primero).
    Cada item: {"group", "team", "PTS", "DG", "GF"}.
    Los primeros 8 son los que clasifican.
    """
    thirds = []
    for g, rows in standings.items():
        if len(rows) >= 3:
            t = rows[2]
            thirds.append({"group": g, "team": t["team"],
                           "PTS": t["PTS"], "DG": t["DG"], "GF": t["GF"]})
    thirds.sort(key=lambda x: (x["PTS"], x["DG"], x["GF"]), reverse=True)
    return thirds


def qualified_thirds(standings):
    """Los 8 mejores terceros que avanzan a la Ronda de 32."""
    return rank_third_places(standings)[:8]


# -------------------------------------------------------------------------
# 3) RESOLUCION DE SLOTS DE GRUPO ("1° Grupo A", "2° Grupo C")
# -------------------------------------------------------------------------
def resolve_group_slot(slot_text, standings):
    """
    Traduce '1° Grupo A' / '2° Grupo C' al nombre real del equipo si ya
    se conoce la posicion. Devuelve None si aun no se puede resolver.
    Los slots de 'Mejor 3°' se resuelven aparte (asignacion manual).
    """
    s = slot_text.strip()
    if s.startswith("1°") or s.startswith("1\u00b0"):
        pos = 0
    elif s.startswith("2°") or s.startswith("2\u00b0"):
        pos = 1
    else:
        return None
    # extraer letra de grupo
    g = s.split("Grupo")[-1].strip()
    if g not in standings:
        return None
    rows = standings[g]
    if len(rows) <= pos:
        return None
    row = rows[pos]
    # solo resolver si el grupo tiene partidos jugados (evita orden arbitrario)
    if row["PJ"] == 0:
        return None
    return row["team"]


# -------------------------------------------------------------------------
# 4) PROPAGACION DE LA FASE ELIMINATORIA
# -------------------------------------------------------------------------
def build_bracket(standings, third_assignments, ko_winners):
    """
    standings:          salida de compute_standings
    third_assignments:  dict { match_n (str) : team_name }  asignacion manual de
                        los 'Mejor 3°' a las llaves que lo requieren.
    ko_winners:         dict { match_n (str) : team_name }  ganador elegido por el
                        usuario en cada cruce eliminatorio.

    Devuelve lista de cruces con t1/t2 ya resueltos cuando es posible:
      [{n, round, t1, t2, t1_raw, t2_raw, fecha, sede, winner, resolved}]
    'resolved' = ambos equipos tienen nombre real.
    """
    # resultado por partido: ganador y perdedor (para propagar)
    winner_of = {}
    loser_of = {}

    # Iteramos a punto fijo: cada pasada puede resolver mas equipos a partir de
    # los ganadores de la pasada anterior (octavos dependen de R32, cuartos de
    # octavos, etc.). 8 pasadas cubren de sobra las 6 rondas.
    teams = {}  # n -> (t1, t2)
    for _ in range(8):
        changed = False
        for m in KNOCKOUT:
            n = str(m["n"])
            t1 = _resolve_team(m["t1"], standings, third_assignments,
                               winner_of, loser_of, n, "t1")
            t2 = _resolve_team(m["t2"], standings, third_assignments,
                               winner_of, loser_of, n, "t2")
            prev = teams.get(n)
            if prev != (t1, t2):
                teams[n] = (t1, t2)
                changed = True
            winner = ko_winners.get(n)
            valid_winner = winner if winner and winner in (t1, t2) else None
            if valid_winner and winner_of.get(n) != valid_winner:
                winner_of[n] = valid_winner
                loser_of[n] = t2 if valid_winner == t1 else t1
                changed = True
            elif not valid_winner and n in winner_of:
                # el ganador previo ya no es valido (cambio el bracket)
                winner_of.pop(n, None)
                loser_of.pop(n, None)
                changed = True
        if not changed:
            break

    resolved = []
    for m in KNOCKOUT:
        n = str(m["n"])
        t1, t2 = teams.get(n, (None, None))
        resolved.append({
            "n": m["n"], "round": m["round"],
            "t1": t1, "t2": t2,
            "t1_raw": m["t1"], "t2_raw": m["t2"],
            "fecha": m["fecha"], "sede": m["sede"],
            "winner": winner_of.get(n),
            "resolved": bool(t1 and t2),
        })
    return resolved


def _resolve_team(raw, standings, third_assignments, winner_of, loser_of, n, side):
    """Resuelve el texto de un slot al nombre real del equipo, o None."""
    s = (raw or "").strip()

    # Mejor 3° -> asignacion manual por numero de partido + lado
    if "Mejor 3" in s or "Mejor 3\u00b0" in s:
        key = f"{n}:{side}"
        return third_assignments.get(key)

    # Ganador Mxx
    if s.startswith("Ganador M"):
        ref = _extract_match_num(s)
        return winner_of.get(ref)

    # Ganador CFx / SFx / Ganador CF1 (M97 vs M98)
    if s.startswith("Ganador CF") or s.startswith("Ganador SF"):
        ref = _extract_paren_match(s)
        if ref:
            return winner_of.get(ref)
        # CF3/CF4/SF1/SF2 sin parentesis -> mapear por etiqueta
        ref2 = _label_to_match(s)
        return winner_of.get(ref2) if ref2 else None

    # Perdedor SFx
    if s.startswith("Perdedor SF"):
        ref = _label_to_match(s.replace("Perdedor", "Ganador"))
        return loser_of.get(ref) if ref else None

    # Slot de grupo
    return resolve_group_slot(s, standings)


def _extract_match_num(s):
    import re
    m = re.search(r"M(\d+)", s)
    return m.group(1) if m else None


def _extract_paren_match(s):
    """'Ganador CF1 (M97 vs M98)' -> no aplica (ese es el primer Mxx? no).
    En realidad CF1 = ganador del cuarto cuyo n corresponde. Usamos el label."""
    return None


# Mapeo de etiquetas de ronda a numero de partido fuente.
# Cuartos: 97=CF1, 98=CF2, 99=CF3, 100=CF4
# Semis:   101=SF1, 102=SF2
_LABEL_MAP = {
    "CF1": "97", "CF2": "98", "CF3": "99", "CF4": "100",
    "SF1": "101", "SF2": "102",
}


def _label_to_match(s):
    import re
    m = re.search(r"(CF\d|SF\d)", s)
    return _LABEL_MAP.get(m.group(1)) if m else None


# -------------------------------------------------------------------------
# 5) UTILIDAD: lista de cruces R32 que requieren asignacion de 3°
# -------------------------------------------------------------------------
def third_slots_needed():
    """Devuelve [(match_n, side, opponent_raw)] para cada slot 'Mejor 3°'."""
    out = []
    for m in KNOCKOUT:
        if m["round"] != "R32":
            continue
        for side, raw, opp in (("t1", m["t1"], m["t2"]), ("t2", m["t2"], m["t1"])):
            if "Mejor 3" in (raw or ""):
                out.append((str(m["n"]), side, opp))
    return out
