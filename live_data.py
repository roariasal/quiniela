# -*- coding: utf-8 -*-
"""
Integración de datos reales del Mundial 2026 desde openfootball/worldcup.json
(dominio público, sin API key). Provee:

  - fetch_real_matches(): descarga (con cache) los 104 partidos reales
  - real_standings(): tabla real por grupo a partir de marcadores reales
  - live_and_upcoming(): partido(s) en curso ahora + próximos, por fecha/hora
  - accuracy(): compara las predicciones del usuario con los resultados reales

Notas:
  - Los datos NO son en vivo al minuto: el upstream se actualiza ~1 vez al día.
  - Mientras el Mundial no se juega, los marcadores son placeholders; la lógica
    es idéntica para los resultados reales cuando empiece el torneo.
"""
import json
import time
import datetime as dt
from urllib.request import urlopen, Request

from wc_data import GROUPS

DATA_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
_CACHE = {"ts": 0, "data": None}
_CACHE_TTL = 600  # 10 min

# Mapeo nombre API (inglés) -> nombre app (español)
EN_TO_ES = {
    "Algeria": "Argelia", "Argentina": "Argentina", "Australia": "Australia",
    "Austria": "Austria", "Belgium": "Bélgica", "Bosnia & Herzegovina": "Bosnia-Herzegovina",
    "Brazil": "Brasil", "Canada": "Canadá", "Cape Verde": "Cabo Verde",
    "Colombia": "Colombia", "Croatia": "Croacia", "Curaçao": "Curazao",
    "Czech Republic": "Chequia", "DR Congo": "DR Congo", "Ecuador": "Ecuador",
    "Egypt": "Egipto", "England": "Inglaterra", "France": "Francia",
    "Germany": "Alemania", "Ghana": "Ghana", "Haiti": "Haití",
    "Iran": "Irán", "Iraq": "Iraq", "Ivory Coast": "Costa de Marfil",
    "Japan": "Japón", "Jordan": "Jordania", "Mexico": "México",
    "Morocco": "Marruecos", "Netherlands": "Países Bajos", "New Zealand": "Nueva Zelanda",
    "Norway": "Noruega", "Panama": "Panamá", "Paraguay": "Paraguay",
    "Portugal": "Portugal", "Qatar": "Qatar", "Saudi Arabia": "Arabia Saudita",
    "Scotland": "Escocia", "Senegal": "Senegal", "South Africa": "Sudáfrica",
    "South Korea": "Corea del Sur", "Spain": "España", "Sweden": "Suecia",
    "Switzerland": "Suiza", "Tunisia": "Túnez", "Turkey": "Turquía",
    "USA": "EE.UU.", "Uruguay": "Uruguay", "Uzbekistan": "Uzbekistán",
}


def _es(name):
    return EN_TO_ES.get((name or "").strip(), (name or "").strip())


def fetch_real_matches(force=False):
    """Descarga los partidos reales (con cache de 10 min). Devuelve lista o []."""
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["ts"]) < _CACHE_TTL:
        return _CACHE["data"]
    try:
        req = Request(DATA_URL, headers={"User-Agent": "quiniela-app"})
        raw = urlopen(req, timeout=20).read()
        data = json.loads(raw)
        matches = data.get("matches", [])
        _CACHE["data"] = matches
        _CACHE["ts"] = now
        return matches
    except Exception:
        return _CACHE["data"] or []


def _parse_score(m):
    """Devuelve (gl, gv) marcador final o (None, None) si no jugado."""
    sc = m.get("score") or {}
    ft = sc.get("ft")
    if isinstance(ft, list) and len(ft) == 2:
        try:
            return int(ft[0]), int(ft[1])
        except (TypeError, ValueError):
            return None, None
    return None, None


def _parse_dt(m):
    """Combina date + time del partido en un datetime UTC, o None.
    time viene como '13:00 UTC-6' o '20:00 UTC-4' etc."""
    date = m.get("date")
    tstr = m.get("time", "")
    if not date:
        return None
    try:
        hh, mm = 12, 0
        off = 0
        if tstr:
            parts = tstr.split()
            hm = parts[0].split(":")
            hh, mm = int(hm[0]), int(hm[1])
            if len(parts) > 1 and parts[1].startswith("UTC"):
                off = int(parts[1].replace("UTC", "") or 0)
        local = dt.datetime.fromisoformat(date).replace(hour=hh, minute=mm)
        # convertir a UTC restando el offset
        return local - dt.timedelta(hours=off)
    except Exception:
        try:
            return dt.datetime.fromisoformat(date)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Tabla real por grupo
# ---------------------------------------------------------------------------
def _blank(team):
    return {"team": team, "PJ": 0, "G": 0, "E": 0, "P": 0,
            "GF": 0, "GC": 0, "DG": 0, "PTS": 0}


def real_standings():
    """Tabla real por grupo a partir de los marcadores reales descargados."""
    matches = fetch_real_matches()
    tables = {g: {t: _blank(t) for t in teams} for g, teams in GROUPS.items()}
    # set de equipos por grupo para validar pertenencia
    team_group = {t: g for g, ts in GROUPS.items() for t in ts}

    for m in matches:
        t1, t2 = _es(m.get("team1")), _es(m.get("team2"))
        if t1 not in team_group or t2 not in team_group:
            continue  # ignora cruces de eliminatoria o placeholders
        g = team_group[t1]
        if team_group.get(t2) != g:
            continue
        gl, gv = _parse_score(m)
        if gl is None:
            continue
        r1, r2 = tables[g][t1], tables[g][t2]
        r1["PJ"] += 1; r2["PJ"] += 1
        r1["GF"] += gl; r1["GC"] += gv
        r2["GF"] += gv; r2["GC"] += gl
        if gl > gv:
            r1["G"] += 1; r1["PTS"] += 3; r2["P"] += 1
        elif gv > gl:
            r2["G"] += 1; r2["PTS"] += 3; r1["P"] += 1
        else:
            r1["E"] += 1; r2["E"] += 1; r1["PTS"] += 1; r2["PTS"] += 1

    out = {}
    for g, rows in tables.items():
        lst = list(rows.values())
        for r in lst:
            r["DG"] = r["GF"] - r["GC"]
        lst.sort(key=lambda r: (r["PTS"], r["DG"], r["GF"]), reverse=True)
        out[g] = lst
    return out


# ---------------------------------------------------------------------------
# Partido en vivo / próximos
# ---------------------------------------------------------------------------
def live_and_upcoming(now_utc=None, live_window_min=120):
    """Clasifica los partidos en: en_vivo, proximos, recientes (jugados).
    Un partido se considera 'en vivo' si ahora está dentro de live_window_min
    minutos después de su hora de inicio y aún no tiene marcador final."""
    if now_utc is None:
        now_utc = dt.datetime.utcnow()
    matches = fetch_real_matches()
    en_vivo, proximos, recientes = [], [], []
    for m in matches:
        start = _parse_dt(m)
        gl, gv = _parse_score(m)
        item = {
            "team1": _es(m.get("team1")), "team2": _es(m.get("team2")),
            "raw1": m.get("team1"), "raw2": m.get("team2"),
            "start": start, "score": (gl, gv),
            "ht": (m.get("score") or {}).get("ht"),
            "group": m.get("group"), "round": m.get("round"),
            "ground": m.get("ground"), "time": m.get("time"),
            "date": m.get("date"),
            "goals1": m.get("goals1", []), "goals2": m.get("goals2", []),
        }
        if start is None:
            continue
        delta_min = (now_utc - start).total_seconds() / 60.0
        if 0 <= delta_min <= live_window_min and gl is None:
            en_vivo.append(item)
        elif delta_min < 0:
            proximos.append(item)
        else:
            recientes.append(item)
    proximos.sort(key=lambda x: x["start"])
    recientes.sort(key=lambda x: x["start"], reverse=True)
    return {"en_vivo": en_vivo, "proximos": proximos, "recientes": recientes}


# ---------------------------------------------------------------------------
# Aciertos: predicciones del usuario vs resultados reales
# ---------------------------------------------------------------------------
def accuracy(group_results):
    """Compara las predicciones 1/X/2 del usuario (group_results) con los
    resultados reales. Devuelve métricas y detalle por partido.
    group_results: { '<match_n>': {'outcome': '1|X|2', ...} } (de storage)
    Necesita mapear match_n -> partido real por equipos."""
    from wc_data import GROUP_MATCHES
    real = fetch_real_matches()
    # index real por par de equipos (es)
    real_by_pair = {}
    for m in real:
        t1, t2 = _es(m.get("team1")), _es(m.get("team2"))
        gl, gv = _parse_score(m)
        if gl is not None:
            real_by_pair[(t1, t2)] = (gl, gv)

    total, aciertos = 0, 0
    detalle = []
    for gm in GROUP_MATCHES:
        n = str(gm["n"])
        pred = (group_results.get(n) or {}).get("outcome")
        if not pred:
            continue
        real_sc = real_by_pair.get((gm["local"], gm["visit"]))
        if real_sc is None:
            continue
        gl, gv = real_sc
        real_out = "1" if gl > gv else ("2" if gv > gl else "X")
        ok = (pred == real_out)
        total += 1
        aciertos += 1 if ok else 0
        detalle.append({
            "n": gm["n"], "local": gm["local"], "visit": gm["visit"],
            "pred": pred, "real": real_out, "score": f"{gl}-{gv}", "ok": ok,
        })
    pct = (aciertos / total * 100) if total else 0.0
    return {"total": total, "aciertos": aciertos, "pct": pct, "detalle": detalle}


# ---------------------------------------------------------------------------
# Formato de hora en zona Ciudad de México (UTC-6, sin horario de verano)
# ---------------------------------------------------------------------------
CDMX_OFFSET = -6  # horas respecto a UTC

_MESES = ["ene", "feb", "mar", "abr", "may", "jun",
          "jul", "ago", "sep", "oct", "nov", "dic"]


def to_cdmx(utc_dt):
    """Convierte un datetime UTC a hora de Ciudad de México (UTC-6)."""
    if utc_dt is None:
        return None
    return utc_dt + dt.timedelta(hours=CDMX_OFFSET)


def fmt_cdmx(utc_dt, with_date=True):
    """Formatea un datetime UTC como hora CDMX legible.
    Ej: '18 jun · 13:00 (CDMX)' o '13:00 (CDMX)'."""
    local = to_cdmx(utc_dt)
    if local is None:
        return ""
    hora = local.strftime("%H:%M")
    if with_date:
        return f"{local.day} {_MESES[local.month - 1]} · {hora} (CDMX)"
    return f"{hora} (CDMX)"


def now_cdmx():
    """Hora actual en CDMX (para mostrar)."""
    return to_cdmx(dt.datetime.utcnow())


# ---------------------------------------------------------------------------
# Pronóstico estadístico (sin IA, sin key) basado en datos reales del torneo
# ---------------------------------------------------------------------------
def _team_form(team, standings_by_team):
    """Devuelve métricas de forma del equipo a partir de la tabla real."""
    r = standings_by_team.get(team)
    if not r or r["PJ"] == 0:
        return None
    pj = r["PJ"]
    return {
        "PJ": pj, "PTS": r["PTS"], "DG": r["DG"], "GF": r["GF"], "GC": r["GC"],
        "G": r["G"], "E": r["E"], "P": r["P"],
        "ppp": r["PTS"] / pj,          # puntos por partido
        "gf_pp": r["GF"] / pj,         # goles a favor por partido
        "gc_pp": r["GC"] / pj,         # goles en contra por partido
    }


def predict_match(team1, team2):
    """Pronóstico estadístico de un cruce a partir de la forma real de ambos
    equipos en el torneo. Devuelve dict con probabilidades estimadas, marcador
    proyectado y el detalle de las métricas (transparente, sin caja negra).
    Si algún equipo no tiene partidos jugados, lo indica."""
    st = real_standings()
    by_team = {r["team"]: r for rows in st.values() for r in rows}
    f1 = _team_form(team1, by_team)
    f2 = _team_form(team2, by_team)

    res = {"team1": team1, "team2": team2, "f1": f1, "f2": f2,
           "suficiente": bool(f1 and f2)}
    if not (f1 and f2):
        return res

    # Fuerza relativa: combina puntos/partido (peso 2), DG/partido (peso 1.5),
    # y diferencial de goles esperados. Es una heurística simple y explicable.
    dg1_pp = f1["DG"] / f1["PJ"]
    dg2_pp = f2["DG"] / f2["PJ"]
    score1 = f1["ppp"] * 2.0 + dg1_pp * 1.5
    score2 = f2["ppp"] * 2.0 + dg2_pp * 1.5

    # Marcador proyectado: promedio entre ataque propio y defensa rival
    g1 = (f1["gf_pp"] + f2["gc_pp"]) / 2.0
    g2 = (f2["gf_pp"] + f1["gc_pp"]) / 2.0

    # Convertir diferencia de fuerza en probabilidades (logística suave)
    import math
    diff = score1 - score2
    p1 = 1.0 / (1.0 + math.exp(-diff * 0.9))   # prob. de que gane team1
    # margen de empate: cuanto más parejo, más probable el empate
    parity = math.exp(-abs(diff) * 1.2)
    p_draw = 0.28 * parity + 0.10
    # normalizar
    p_win1 = p1 * (1 - p_draw)
    p_win2 = (1 - p1) * (1 - p_draw)
    total = p_win1 + p_win2 + p_draw
    p_win1, p_win2, p_draw = p_win1/total, p_win2/total, p_draw/total

    if p_win1 > p_win2 and p_win1 > p_draw:
        favorito, signo = team1, "1"
    elif p_win2 > p_win1 and p_win2 > p_draw:
        favorito, signo = team2, "2"
    else:
        favorito, signo = "Empate", "X"

    res.update({
        "prob_1": round(p_win1 * 100), "prob_x": round(p_draw * 100),
        "prob_2": round(p_win2 * 100),
        "marcador": f"{round(g1)}-{round(g2)}",
        "favorito": favorito, "signo": signo,
        "score1": round(score1, 2), "score2": round(score2, 2),
    })
    return res


def upcoming_matches(limit=20, now_utc=None):
    """Lista de próximos partidos del calendario real (no jugados aún),
    con equipos resueltos cuando es posible. Para el selector de pronóstico."""
    lu = live_and_upcoming(now_utc=now_utc)
    out = []
    for m in lu["proximos"][:limit]:
        # solo cruces con equipos reales conocidos (no 'Winner M..')
        if m["team1"] in EN_TO_ES.values() and m["team2"] in EN_TO_ES.values():
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# Mini-resumen de un partido (marcador, medio tiempo, cronología de goles)
# ---------------------------------------------------------------------------
def match_summary_live(m):
    """Arma el resumen de un partido a partir del item de live_and_upcoming.
    Devuelve dict con marcador, medio tiempo y cronología de goles ordenada.
    Solo usa datos disponibles (sin tarjetas: la fuente no las tiene)."""
    gl, gv = m.get("score", (None, None))
    # medio tiempo: hay que releerlo del match crudo; lo guardamos al construir
    ht = m.get("ht")  # puede venir o no
    # cronología combinada de goles, ordenada por minuto
    crono = []
    for g in (m.get("goals1") or []):
        crono.append({"team": m["team1"], "side": 1,
                      "name": g.get("name", ""), "minute": _min_int(g.get("minute"))})
    for g in (m.get("goals2") or []):
        crono.append({"team": m["team2"], "side": 2,
                      "name": g.get("name", ""), "minute": _min_int(g.get("minute"))})
    crono.sort(key=lambda x: x["minute"] if x["minute"] is not None else 999)
    return {
        "team1": m["team1"], "team2": m["team2"],
        "gl": gl, "gv": gv, "ht": ht, "crono": crono,
        "jugado": gl is not None,
    }


def _min_int(v):
    try:
        return int(str(v).replace("'", "").split("+")[0])
    except (TypeError, ValueError):
        return None
