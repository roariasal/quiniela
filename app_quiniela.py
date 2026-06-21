# -*- coding: utf-8 -*-
"""
QUINIELA MUNDIAL 2026 — App de seguimiento
==========================================
Captura tus predicciones (1/X/2 en grupos, ganador en eliminatorias) y las
variables que el organizador define por partido (v1..v4 + marcador). La app
calcula las posiciones de grupo, rankea los mejores terceros (reglas FIFA por
puntos) y propaga los ganadores por toda la llave hasta el campeon.

Ejecutar:
    streamlit run app_quiniela.py

El estado se guarda en quiniela_estado.json (configurable con la variable de
entorno QUINIELA_FILE).
"""
import streamlit as st

import engine
import storage
import export_share
from flags import with_flag, flag
from wc_data import GROUP_MATCHES, GROUPS, KNOCKOUT

st.set_page_config(page_title="Quiniela Mundial 2026", page_icon="⚽", layout="wide")

ROUND_LABEL = {
    "R32": "Ronda de 32", "R16": "Octavos", "QF": "Cuartos",
    "SF": "Semifinales", "P3": "Tercer Lugar", "F": "Gran Final",
}
GROUP_DATES = sorted({m["fecha"] for m in GROUP_MATCHES},
                     key=lambda d: ("00" if False else d))  # mantener orden de aparicion

# ----------------------------------------------------------------------
# Estado en sesion (se sincroniza con disco al guardar)
# ----------------------------------------------------------------------
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = storage.load_state()
    if "selected" not in st.session_state:
        st.session_state.selected = None  # (kind, match_n)


def get():
    return st.session_state.data


def autosave():
    try:
        ts = storage.save_state(st.session_state.data)
        st.session_state.data["updated"] = ts
    except Exception as e:
        st.error(f"No se pudo guardar: {e}")


def compute():
    """Recalcula posiciones y bracket desde el estado actual."""
    d = get()
    standings = engine.compute_standings(d["group_results"])
    bracket = engine.build_bracket(standings, d["third_assignments"], d["ko_winners"])
    return standings, bracket


# ----------------------------------------------------------------------
# Panel de variables (mango derecho) — estructura fija v1..v4 + marcador
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Panel de variables (mango derecho)
# Cada variable: TITULO editable por partido (lo que pide el organizador) +
# VALOR que predice el jugador. Estructura fija: v1..v4 + marcador.
# ----------------------------------------------------------------------
def _variable_field(n, idx, v):
    """Renderiza el título y el valor de una variable, apilados verticalmente
    (funciona bien en móvil y escritorio). Devuelve (titulo, valor)."""
    tk, vk = f"t{idx}", f"v{idx}"
    titulo = st.text_input(
        f"Variable {idx} — título", value=v.get(tk, ""), key=f"{tk}_{n}",
        placeholder="ej. Goleador")
    valor = st.text_input(
        f"Variable {idx} — tu predicción", value=v.get(vk, ""), key=f"{vk}_{n}",
        placeholder=f"tu predicción para {titulo}" if titulo else "tu predicción",
        label_visibility="collapsed")
    return titulo, valor


def variable_panel(match_n, titulo_partido, subtitulo=""):
    d = get()
    n = str(match_n)
    v = d["variables"].get(n, {})
    st.markdown(f"#### 📋 {titulo_partido}")
    if subtitulo:
        st.caption(subtitulo)
    st.caption("Escribe el título de cada variable (lo que pide el organizador "
               "ese día) y debajo tu predicción.")

    # Layout apilado: una variable debajo de otra. En escritorio Streamlit lo
    # muestra cómodo; en móvil evita columnas estrechas donde no se puede teclear.
    t1, v1 = _variable_field(n, 1, v)
    t2, v2 = _variable_field(n, 2, v)
    t3, v3 = _variable_field(n, 3, v)
    t4, v4 = _variable_field(n, 4, v)

    marcador = st.text_input("Marcador", value=v.get("marcador", ""),
                             key=f"mar_{n}", placeholder="ej. 2-1")

    if st.button("💾 Guardar variables", key=f"save_{n}", type="primary",
                 width='stretch'):
        d["variables"][n] = {
            "t1": t1, "v1": v1, "t2": t2, "v2": v2,
            "t3": t3, "v3": v3, "t4": t4, "v4": v4,
            "marcador": marcador,
        }
        autosave()
        st.success("Guardado.")

    with st.expander("📤 Compartir este partido"):
        _, bracket = compute()
        entry = export_share.entry_for_match(d, bracket, n)
        if entry:
            _share_match_ui(entry, d.get("owner", ""))


# ----------------------------------------------------------------------
# TAB: Fase de Grupos
# ----------------------------------------------------------------------
def tab_grupos():
    d = get()
    st.subheader("Fase de Grupos")
    st.caption("Marca tu predicción 1 / X / 2. Tus resultados calculan las posiciones automáticamente.")

    grupos = sorted(GROUPS.keys())

    # Buscador de país: escribe un país y salta a su grupo.
    team_group = {t: g for g, ts in GROUPS.items() for t in ts}
    import unicodedata

    def _norm(s):
        s = (s or "").lower().strip()
        return "".join(c for c in unicodedata.normalize("NFD", s)
                       if unicodedata.category(c) != "Mn")

    busqueda = st.text_input("🔎 Buscar país", key="buscar_pais",
                             placeholder="ej. Brasil, México, Croacia...")
    grupo_encontrado = None
    if busqueda.strip():
        q = _norm(busqueda)
        # coincidencia por prefijo o contenido
        matches_found = [(t, g) for t, g in team_group.items()
                         if q in _norm(t)]
        if matches_found:
            # priorizar coincidencia que empieza con la búsqueda
            matches_found.sort(key=lambda x: (not _norm(x[0]).startswith(q), x[0]))
            equipo, grupo_encontrado = matches_found[0]
            otros = [t for t, _ in matches_found[1:]]
            msg = f"**{with_flag(equipo)}** está en el **Grupo {grupo_encontrado}**"
            if otros:
                msg += f" · _(también: {', '.join(otros[:3])})_"
            st.success(msg)
        else:
            st.warning(f"No encontré ningún país que coincida con «{busqueda}».")

    # índice por defecto: el grupo encontrado, si lo hay
    default_idx = grupos.index(grupo_encontrado) if grupo_encontrado in grupos else 0
    sel_group = st.selectbox("Grupo", grupos, index=default_idx,
                             format_func=lambda g: f"Grupo {g}")

    # Si hay un partido seleccionado, mostrar el panel de captura a ancho completo
    # ARRIBA (clave para móvil: nada de columnas laterales estrechas).
    sel = st.session_state.selected
    if sel and sel[0] == "grupo":
        m = next((x for x in GROUP_MATCHES if str(x["n"]) == sel[1]), None)
        if m and m["group"] == sel_group:
            with st.container(border=True):
                cc1, cc2 = st.columns([0.85, 0.15])
                with cc2:
                    if st.button("✕", key="close_var_g", help="Cerrar"):
                        st.session_state.selected = None
                        st.rerun()
                variable_panel(m["n"], f"#{m['n']} · {with_flag(m['local'])} vs {with_flag(m['visit'])}",
                               f"{m['fecha']} · {m['sede']}")
            st.divider()

    st.markdown(f"##### Partidos · Grupo {sel_group}")
    for m in [x for x in GROUP_MATCHES if x["group"] == sel_group]:
        n = str(m["n"])
        cur = d["group_results"].get(n, {})
        label = f"**#{m['n']}** · {with_flag(m['local'])} vs {with_flag(m['visit'])}  \n_{m['fecha']} · {m['sede']}_"
        st.markdown(label)
        cols = st.columns([1, 1, 1, 1.4])
        outcome = cur.get("outcome")
        opts = [("1", f"1 · {flag(m['local'])}"), ("X", "X · Empate"), ("2", f"2 · {flag(m['visit'])}")]
        for i, (code, txt) in enumerate(opts):
            with cols[i]:
                btype = "primary" if outcome == code else "secondary"
                if st.button(code, key=f"out_{n}_{code}", type=btype, width='stretch'):
                    d["group_results"].setdefault(n, {})
                    d["group_results"][n]["outcome"] = code
                    autosave()
                    st.rerun()
        with cols[3]:
            active = sel and sel[0] == "grupo" and sel[1] == n
            if st.button("📋 Variables" + (" ✓" if active else ""),
                         key=f"selg_{n}", width='stretch',
                         type="primary" if active else "secondary"):
                st.session_state.selected = ("grupo", n)
                st.rerun()
        st.divider()


# ----------------------------------------------------------------------
# TAB: Posiciones
# ----------------------------------------------------------------------
def tab_posiciones():
    standings, _ = compute()
    st.subheader("Tabla de Posiciones (calculada)")
    st.caption("Se recalcula con tus resultados de grupo. 3 pts victoria · 1 empate.")

    cols = st.columns(3)
    for i, g in enumerate(sorted(standings.keys())):
        with cols[i % 3]:
            st.markdown(f"**Grupo {g}**")
            rows = standings[g]
            table = [{"Pos": j + 1, "Equipo": with_flag(r["team"]), "PJ": r["PJ"],
                      "Pts": r["PTS"], "DG": r["DG"], "GF": r["GF"]}
                     for j, r in enumerate(rows)]
            st.dataframe(table, hide_index=True, width='stretch')

    st.divider()
    st.subheader("Ranking de Mejores Terceros (FIFA)")
    thirds = engine.rank_third_places(standings)
    qual = engine.qualified_thirds(standings)
    qual_teams = {t["team"] for t in qual}
    table = [{"#": i + 1, "Grupo": t["group"], "Equipo": with_flag(t["team"]),
              "Pts": t["PTS"], "DG": t["DG"], "GF": t["GF"],
              "Clasifica": "✅" if t["team"] in qual_teams else ""}
             for i, t in enumerate(thirds)]
    st.dataframe(table, hide_index=True, width='stretch')
    st.caption("Los 8 mejores terceros avanzan. Asígnalos a sus llaves en la pestaña Ronda de 32.")


# ----------------------------------------------------------------------
# TAB: Eliminatorias (una vista por ronda)
# ----------------------------------------------------------------------
def tab_eliminatoria(round_code):
    d = get()
    standings, bracket = compute()
    bmap = {str(b["n"]): b for b in bracket}
    matches = [b for b in bracket if b["round"] == round_code]

    st.subheader(ROUND_LABEL[round_code])

    # Asignacion de terceros (solo en R32)
    if round_code == "R32":
        _third_assignment_ui(standings)

    # Panel de captura a ancho completo arriba si hay partido de esta ronda seleccionado
    sel = st.session_state.selected
    if sel and sel[0] == "ko":
        b = bmap.get(sel[1])
        if b and b["round"] == round_code:
            with st.container(border=True):
                cc1, cc2 = st.columns([0.85, 0.15])
                with cc2:
                    if st.button("✕", key="close_var_k", help="Cerrar"):
                        st.session_state.selected = None
                        st.rerun()
                t1 = with_flag(b["t1"]) if b["t1"] else b["t1_raw"]
                t2 = with_flag(b["t2"]) if b["t2"] else b["t2_raw"]
                variable_panel(b["n"], f"#{b['n']} · {t1} vs {t2}",
                               f"{b['fecha']} · {b['sede']}")
            st.divider()

    for b in matches:
        n = str(b["n"])
        t1 = with_flag(b["t1"]) if b["t1"] else f"⟨{b['t1_raw']}⟩"
        t2 = with_flag(b["t2"]) if b["t2"] else f"⟨{b['t2_raw']}⟩"
        st.markdown(f"**#{b['n']}** · {t1} vs {t2}  \n_{b['fecha']} · {b['sede']}_")

        if b["resolved"]:
            cols = st.columns([1.3, 1.3, 1])
            win = b["winner"]
            with cols[0]:
                bt = "primary" if win == b["t1"] else "secondary"
                if st.button(f"🏆 {with_flag(b['t1'])}", key=f"w1_{n}", type=bt, width='stretch'):
                    d["ko_winners"][n] = b["t1"]; autosave(); st.rerun()
            with cols[1]:
                bt = "primary" if win == b["t2"] else "secondary"
                if st.button(f"🏆 {with_flag(b['t2'])}", key=f"w2_{n}", type=bt, width='stretch'):
                    d["ko_winners"][n] = b["t2"]; autosave(); st.rerun()
            with cols[2]:
                active = sel and sel[0] == "ko" and sel[1] == n
                if st.button("📋" + (" ✓" if active else ""), key=f"selk_{n}",
                             width='stretch', type="primary" if active else "secondary"):
                    st.session_state.selected = ("ko", n); st.rerun()
        else:
            st.caption("⏳ Faltan resultados previos para definir este cruce.")
        st.divider()


def _third_assignment_ui(standings):
    d = get()
    qual = engine.qualified_thirds(standings)
    with st.expander("⚙️ Asignar Mejores Terceros a las llaves", expanded=False):
        if len(qual) < 8:
            st.warning("Aún no hay 8 terceros definidos. Completa más resultados de grupo.")
            return
        st.caption("Elige qué tercero clasificado va en cada llave que lo requiere "
                   "(solo entre los 8 mejores).")
        options = ["—"] + [f"{with_flag(t['team'])} (3° {t['group']})" for t in qual]
        team_by_label = {f"{with_flag(t['team'])} (3° {t['group']})": t["team"] for t in qual}
        slots = engine.third_slots_needed()
        changed = False
        for n, side, opp in slots:
            key = f"{n}:{side}"
            cur = d["third_assignments"].get(key)
            cur_label = next((l for l, t in team_by_label.items() if t == cur), "—")
            sel = st.selectbox(
                f"Partido #{n} — rival de {opp}",
                options, index=options.index(cur_label) if cur_label in options else 0,
                key=f"third_{key}")
            new = team_by_label.get(sel)
            if new != cur:
                if new:
                    d["third_assignments"][key] = new
                else:
                    d["third_assignments"].pop(key, None)
                changed = True
        if changed:
            autosave()
            st.rerun()


# ----------------------------------------------------------------------
# TAB: Compartir (JSON WhatsApp)
# ----------------------------------------------------------------------
def _share_match_ui(entry, jugador):
    """Render compartido: imagen PNG + texto WhatsApp para un partido."""
    import card_render
    png = card_render.png_card(entry, jugador)
    st.image(png, caption=None, width='stretch')
    st.download_button(
        "⬇️ Descargar imagen (PNG)", png,
        file_name=f"quiniela_partido_{entry['n']}.png", mime="image/png",
        key=f"png_{entry['n']}")
    txt = card_render.whatsapp_text(entry, jugador)
    st.markdown("**Texto para WhatsApp** (cópialo):")
    st.code(txt, language=None)


def tab_compartir():
    d = get()
    _, bracket = compute()
    st.subheader("Compartir con el administrador")

    entries = export_share.entries_with_data(d, bracket)
    if not entries:
        st.info("Aún no has capturado datos en ningún partido. "
                "Marca una predicción o llena las variables de un partido.")
        return

    # selector de un partido a la vez
    def _lbl(e):
        return f"#{e['n']} · {e['partido']} ({e['fase']})"
    idx = st.selectbox("Partido", range(len(entries)),
                       format_func=lambda i: _lbl(entries[i]))
    _share_match_ui(entries[idx], d.get("owner", ""))


# ----------------------------------------------------------------------
# Sidebar + main
# ----------------------------------------------------------------------
def sidebar():
    d = get()
    st.sidebar.title("⚽ Quiniela 2026")
    backend = storage.backend_name()
    if backend == "github":
        st.sidebar.success("☁️ Estado en GitHub (persistente)")
    else:
        st.sidebar.info("💾 Estado en disco local")
    d["owner"] = st.sidebar.text_input("Jugador", value=d.get("owner", "Rod"))
    if d.get("updated"):
        st.sidebar.caption(f"Guardado: {d['updated']}")
    st.sidebar.divider()
    # progreso
    g_done = sum(1 for m in GROUP_MATCHES
                 if d["group_results"].get(str(m["n"]), {}).get("outcome"))
    k_done = sum(1 for m in KNOCKOUT if d["ko_winners"].get(str(m["n"])))
    st.sidebar.metric("Grupos predichos", f"{g_done}/72")
    st.sidebar.metric("Eliminatorias", f"{k_done}/32")
    st.sidebar.divider()
    if st.sidebar.button("💾 Guardar todo ahora"):
        autosave(); st.sidebar.success("Guardado.")

    st.sidebar.caption("📤 Para compartir un partido con el admin, usa la "
                       "pestaña **Compartir** o el botón dentro de cada partido.")

    st.sidebar.divider()
    up = st.sidebar.file_uploader("Importar estado (JSON)", type="json")
    if up is not None:
        import json
        try:
            st.session_state.data = json.load(up)
            autosave()
            st.sidebar.success("Estado importado.")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"No se pudo importar: {e}")


def _match_n_for_real(item):
    """Encuentra el número de partido de grupo de la app que corresponde a un
    partido real (por par de equipos), para enlazar variables/predicción."""
    for gm in GROUP_MATCHES:
        if gm["local"] == item["team1"] and gm["visit"] == item["team2"]:
            return str(gm["n"])
    return None


def tab_en_vivo():
    import live_data
    d = get()
    st.subheader("En Vivo")
    st.caption("Partidos en curso ahora (por fecha y hora), con tus variables al lado. "
               "Los datos reales vienen de openfootball (se actualizan ~1 vez al día).")

    if st.button("🔄 Actualizar datos", key="refresh_live"):
        live_data.fetch_real_matches(force=True)
        st.rerun()

    try:
        lu = live_data.live_and_upcoming()
    except Exception as e:
        st.error(f"No se pudieron cargar los datos en vivo: {e}")
        return

    en_vivo = lu["en_vivo"]
    if not en_vivo:
        st.info("No hay partidos en curso en este momento.")
    for m in en_vivo:
        _render_live_match(m, d, en_vivo=True)

    st.divider()
    st.markdown("##### Próximos partidos")
    for m in lu["proximos"][:5]:
        when = live_data.fmt_cdmx(m["start"]) if m["start"] else m.get("date", "")
        st.markdown(f"{with_flag(m['team1'])} vs {with_flag(m['team2'])} — _{when}_")

    if lu["recientes"]:
        st.divider()
        st.markdown("##### Últimos resultados")
        for m in lu["recientes"][:5]:
            gl, gv = m["score"]
            sc = f"{gl}-{gv}" if gl is not None else "—"
            st.markdown(f"{with_flag(m['team1'])} **{sc}** {with_flag(m['team2'])}")


def _render_live_match(m, d, en_vivo=False):
    import live_data
    with st.container(border=True):
        gl, gv = m["score"]
        sc = f"{gl} - {gv}" if gl is not None else "vs"
        badge = "🔴 EN VIVO" if en_vivo else ""
        st.markdown(f"### {with_flag(m['team1'])}  {sc}  {with_flag(m['team2'])}  {badge}")
        hora_cdmx = live_data.fmt_cdmx(m.get("start")) if m.get("start") else m.get("time")
        info = " · ".join(x for x in [m.get("group"), m.get("ground"), hora_cdmx] if x)
        if info:
            st.caption(info)
        # goleadores reales si hay
        goals = []
        for g in (m.get("goals1") or []):
            goals.append(f"⚽ {g.get('name','')} {g.get('minute','')}'")
        for g in (m.get("goals2") or []):
            goals.append(f"{g.get('name','')} {g.get('minute','')}' ⚽")
        if goals:
            st.caption(" · ".join(goals))

        # tus variables/predicción para este partido
        n = _match_n_for_real(m)
        if n:
            pred = (d["group_results"].get(n) or {}).get("outcome")
            var = d["variables"].get(n) or {}
            cols = st.columns(2)
            with cols[0]:
                st.markdown("**Tu predicción**")
                if pred:
                    txt = {"1": m["team1"], "2": m["team2"], "X": "Empate"}[pred]
                    st.markdown(f"{pred} · {txt}")
                else:
                    st.caption("Sin predicción")
                if var.get("marcador"):
                    st.markdown(f"Marcador: **{var['marcador']}**")
            with cols[1]:
                st.markdown("**Tus variables**")
                any_v = False
                for i in range(1, 5):
                    t = (var.get(f"t{i}") or "").strip()
                    val = (var.get(f"v{i}") or "").strip()
                    if t or val:
                        st.markdown(f"• {t or 'Variable'}: {val or '—'}")
                        any_v = True
                if not any_v:
                    st.caption("Sin variables")
        else:
            st.caption("Este partido no está en tu cuadro de grupos.")


def tab_reales():
    import live_data
    d = get()
    st.subheader("Tablas Reales y Analíticas")
    st.caption("Datos reales del Mundial (openfootball). Compara contra tus pronósticos.")

    if st.button("🔄 Actualizar datos", key="refresh_real"):
        live_data.fetch_real_matches(force=True)
        st.rerun()

    try:
        real = live_data.real_standings()
        acc = live_data.accuracy(d["group_results"])
    except Exception as e:
        st.error(f"No se pudieron cargar los datos reales: {e}")
        return

    # Analíticas de aciertos
    st.markdown("### 🎯 Tus aciertos")
    if acc["total"] == 0:
        st.info("Aún no hay partidos jugados que coincidan con tus predicciones.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Partidos evaluados", acc["total"])
        c2.metric("Aciertos", acc["aciertos"])
        c3.metric("% de acierto", f"{acc['pct']:.0f}%")
        with st.expander("Detalle de aciertos"):
            table = [{"#": x["n"], "Partido": f"{x['local']} vs {x['visit']}",
                      "Tu pred.": x["pred"], "Real": x["real"],
                      "Marcador": x["score"], "✓": "✅" if x["ok"] else "❌"}
                     for x in acc["detalle"]]
            st.dataframe(table, hide_index=True, width='stretch')

    st.divider()
    # Tabla real vs pronosticada
    st.markdown("### 📊 Tabla real por grupo")
    pron, _ = compute()  # tabla pronosticada del usuario
    grupos = sorted(real.keys())
    sel = st.selectbox("Grupo", grupos, format_func=lambda g: f"Grupo {g}", key="real_grp")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Real**")
        rt = [{"Pos": i+1, "Equipo": with_flag(r["team"]), "PJ": r["PJ"],
               "Pts": r["PTS"], "DG": r["DG"], "GF": r["GF"]}
              for i, r in enumerate(real[sel])]
        st.dataframe(rt, hide_index=True, width='stretch')
    with cols[1]:
        st.markdown("**Tu pronóstico**")
        pt = [{"Pos": i+1, "Equipo": with_flag(r["team"]), "PJ": r["PJ"],
               "Pts": r["PTS"], "DG": r["DG"], "GF": r["GF"]}
              for i, r in enumerate(pron[sel])]
        st.dataframe(pt, hide_index=True, width='stretch')

    st.divider()
    _prediction_section(live_data)


def _prediction_section(live_data):
    st.markdown("### 🔮 Pronóstico de un partido")
    st.caption("Estimación estadística basada en la forma real de cada equipo en "
               "el torneo (puntos, goles, diferencia). No usa IA — es un cálculo "
               "transparente. El fútbol es impredecible: tómalo como referencia.")

    try:
        proximos = live_data.upcoming_matches(limit=20)
    except Exception as e:
        st.error(f"No se pudieron cargar los próximos partidos: {e}")
        return

    if not proximos:
        st.info("No hay próximos partidos con equipos definidos para pronosticar.")
        return

    def _lbl(m):
        cuando = live_data.fmt_cdmx(m["start"]) if m.get("start") else ""
        return f"{m['team1']} vs {m['team2']} — {cuando}"

    idx = st.selectbox("Próximo partido", range(len(proximos)),
                       format_func=lambda i: _lbl(proximos[i]), key="pred_match")
    m = proximos[idx]

    if st.button("🔮 Generar pronóstico", type="primary", key="gen_pred"):
        p = live_data.predict_match(m["team1"], m["team2"])
        if not p["suficiente"]:
            faltan = []
            if not p["f1"]:
                faltan.append(m["team1"])
            if not p["f2"]:
                faltan.append(m["team2"])
            st.warning("Datos insuficientes para pronosticar: "
                       + ", ".join(faltan) + " aún no tiene(n) partidos jugados "
                       "en el torneo. El pronóstico se puede hacer una vez que "
                       "ambos equipos hayan jugado.")
            return

        st.markdown(f"#### {with_flag(m['team1'])} vs {with_flag(m['team2'])}")
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Gana {m['team1']}", f"{p['prob_1']}%")
        c2.metric("Empate", f"{p['prob_x']}%")
        c3.metric(f"Gana {m['team2']}", f"{p['prob_2']}%")

        fav = p["favorito"]
        st.success(f"**Favorito: {fav}** · Marcador proyectado: **{p['marcador']}**")

        with st.expander("¿Cómo se calculó? (transparencia)"):
            f1, f2 = p["f1"], p["f2"]
            st.markdown(
                f"Se compara la **forma real** de cada equipo en el torneo:\n\n"
                f"- **{m['team1']}**: {f1['PJ']} PJ · {f1['PTS']} pts "
                f"({f1['ppp']:.2f}/partido) · DG {f1['DG']:+d} · "
                f"{f1['gf_pp']:.1f} goles a favor/partido\n"
                f"- **{m['team2']}**: {f2['PJ']} PJ · {f2['PTS']} pts "
                f"({f2['ppp']:.2f}/partido) · DG {f2['DG']:+d} · "
                f"{f2['gf_pp']:.1f} goles a favor/partido\n\n"
                f"La fuerza relativa combina puntos por partido y diferencia de "
                f"goles. Índice de fuerza: {p['score1']} vs {p['score2']}. "
                f"El marcador proyectado promedia el ataque de cada equipo contra "
                f"la defensa del rival.")


def _secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


def check_password():
    """Login simple con contraseña desde st.secrets['APP_PASSWORD'].
    Si no hay secret configurado, no exige contraseña (modo local abierto)."""
    if _secret("APP_PASSWORD") is None:
        return True
    if st.session_state.get("auth_ok"):
        return True
    st.title("⚽ Quiniela Mundial 2026")
    pw = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if pw == _secret("APP_PASSWORD"):
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    return False


def inject_theme():
    """Estilo Mundial — paleta deportiva azul/verde + banner."""
    st.markdown("""
    <style>
      /* Banner del torneo */
      .wc-banner {
        background: linear-gradient(120deg, #0A8754 0%, #0E9F6E 45%, #2E86C1 100%);
        color: #fff; border-radius: 14px; padding: 18px 24px; margin-bottom: 8px;
        box-shadow: 0 4px 14px rgba(10,135,84,.25);
      }
      .wc-banner h1 { color:#fff; margin:0; font-size:1.9rem; letter-spacing:.5px; }
      .wc-banner p  { color:#EAF7F1; margin:.2rem 0 0; font-size:.95rem; }
      /* Pestañas activas en verde césped */
      .stTabs [aria-selected="true"] { color:#0A8754 !important; }
      .stTabs [data-baseweb="tab-highlight"] { background:#0A8754 !important; }
      /* Tarjeta de partido más legible */
      div[data-testid="stVerticalBlock"] hr { border-color:#CFE6DC; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="wc-banner">
      <h1>⚽ Quiniela Mundial 2026</h1>
      <p>11 de junio – 19 de julio · 12 grupos · 48 selecciones</p>
    </div>
    """, unsafe_allow_html=True)


def main():
    if not check_password():
        return
    init_state()
    sidebar()
    inject_theme()

    tabs = st.tabs(["🔴 En Vivo", "📊 Tablas Reales", "Grupos", "Posiciones",
                    "Ronda de 32", "Octavos", "Cuartos", "Semifinales",
                    "Tercer Lugar", "Final", "Compartir"])
    with tabs[0]: tab_en_vivo()
    with tabs[1]: tab_reales()
    with tabs[2]: tab_grupos()
    with tabs[3]: tab_posiciones()
    with tabs[4]: tab_eliminatoria("R32")
    with tabs[5]: tab_eliminatoria("R16")
    with tabs[6]: tab_eliminatoria("QF")
    with tabs[7]: tab_eliminatoria("SF")
    with tabs[8]: tab_eliminatoria("P3")
    with tabs[9]: tab_eliminatoria("F")
    with tabs[10]: tab_compartir()


if __name__ == "__main__":
    main()
