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
    """Renderiza 'Variable N :  [titulo]' y debajo el campo de valor.
    Devuelve (titulo, valor)."""
    tk, vk = f"t{idx}", f"v{idx}"
    lab, fld = st.columns([0.42, 0.58])
    with lab:
        st.markdown(f"**Variable {idx}** :")
    with fld:
        titulo = st.text_input(
            f"titulo_{idx}", value=v.get(tk, ""), key=f"{tk}_{n}",
            label_visibility="collapsed",
            placeholder="título (ej. Goleador)")
    valor = st.text_input(
        f"valor_{idx}", value=v.get(vk, ""), key=f"{vk}_{n}",
        label_visibility="collapsed",
        placeholder=f"tu predicción para {titulo}" if titulo else "tu predicción")
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

    c1, c2 = st.columns(2)
    with c1:
        t1, v1 = _variable_field(n, 1, v)
        st.write("")
        t2, v2 = _variable_field(n, 2, v)
    with c2:
        t3, v3 = _variable_field(n, 3, v)
        st.write("")
        t4, v4 = _variable_field(n, 4, v)

    st.markdown("**Marcador** :")
    marcador = st.text_input("Marcador", value=v.get("marcador", ""),
                             key=f"mar_{n}", placeholder="ej. 2-1",
                             label_visibility="collapsed")

    if st.button("💾 Guardar variables", key=f"save_{n}", type="primary"):
        d["variables"][n] = {
            "t1": t1, "v1": v1, "t2": t2, "v2": v2,
            "t3": t3, "v3": v3, "t4": t4, "v4": v4,
            "marcador": marcador,
        }
        autosave()
        st.success("Guardado.")


# ----------------------------------------------------------------------
# TAB: Fase de Grupos
# ----------------------------------------------------------------------
def tab_grupos():
    d = get()
    st.subheader("Fase de Grupos")
    st.caption("Marca tu predicción 1 / X / 2. Tus resultados calculan las posiciones automáticamente.")

    grupos = sorted(GROUPS.keys())
    sel_group = st.selectbox("Grupo", grupos, format_func=lambda g: f"Grupo {g}")

    left, right = st.columns([1, 1])

    with left:
        st.markdown(f"##### Partidos · Grupo {sel_group}")
        for m in [x for x in GROUP_MATCHES if x["group"] == sel_group]:
            n = str(m["n"])
            cur = d["group_results"].get(n, {})
            label = f"**#{m['n']}** · {m['local']} vs {m['visit']}  \n_{m['fecha']} · {m['sede']}_"
            st.markdown(label)
            cols = st.columns([1, 1, 1, 1.4])
            outcome = cur.get("outcome")
            opts = [("1", f"1 · {m['local']}"), ("X", "X · Empate"), ("2", f"2 · {m['visit']}")]
            for i, (code, txt) in enumerate(opts):
                with cols[i]:
                    btype = "primary" if outcome == code else "secondary"
                    if st.button(code, key=f"out_{n}_{code}", type=btype, width='stretch'):
                        d["group_results"].setdefault(n, {})
                        d["group_results"][n]["outcome"] = code
                        autosave()
                        st.rerun()
            with cols[3]:
                if st.button("Variables ▸", key=f"selg_{n}", width='stretch'):
                    st.session_state.selected = ("grupo", n)
                    st.rerun()
            st.divider()

    with right:
        sel = st.session_state.selected
        if sel and sel[0] == "grupo":
            m = next(x for x in GROUP_MATCHES if str(x["n"]) == sel[1])
            variable_panel(m["n"], f"#{m['n']} · {m['local']} vs {m['visit']}",
                           f"{m['fecha']} · {m['sede']}")
        else:
            st.info("Selecciona **Variables ▸** en un partido para capturar las variables del día.")


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
            table = [{"Pos": j + 1, "Equipo": r["team"], "PJ": r["PJ"],
                      "Pts": r["PTS"], "DG": r["DG"], "GF": r["GF"]}
                     for j, r in enumerate(rows)]
            st.dataframe(table, hide_index=True, width='stretch')

    st.divider()
    st.subheader("Ranking de Mejores Terceros (FIFA)")
    thirds = engine.rank_third_places(standings)
    qual = engine.qualified_thirds(standings)
    qual_teams = {t["team"] for t in qual}
    table = [{"#": i + 1, "Grupo": t["group"], "Equipo": t["team"],
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

    left, right = st.columns([1, 1])
    with left:
        for b in matches:
            n = str(b["n"])
            t1 = b["t1"] or f"⟨{b['t1_raw']}⟩"
            t2 = b["t2"] or f"⟨{b['t2_raw']}⟩"
            st.markdown(f"**#{b['n']}** · {t1} vs {t2}  \n_{b['fecha']} · {b['sede']}_")

            if b["resolved"]:
                cols = st.columns([1.3, 1.3, 1])
                win = b["winner"]
                with cols[0]:
                    bt = "primary" if win == b["t1"] else "secondary"
                    if st.button(f"🏆 {b['t1']}", key=f"w1_{n}", type=bt, width='stretch'):
                        d["ko_winners"][n] = b["t1"]; autosave(); st.rerun()
                with cols[1]:
                    bt = "primary" if win == b["t2"] else "secondary"
                    if st.button(f"🏆 {b['t2']}", key=f"w2_{n}", type=bt, width='stretch'):
                        d["ko_winners"][n] = b["t2"]; autosave(); st.rerun()
                with cols[2]:
                    if st.button("Variables ▸", key=f"selk_{n}", width='stretch'):
                        st.session_state.selected = ("ko", n); st.rerun()
            else:
                st.caption("⏳ Faltan resultados previos para definir este cruce.")
            st.divider()

    with right:
        sel = st.session_state.selected
        if sel and sel[0] == "ko":
            b = bmap.get(sel[1])
            if b:
                t1 = b["t1"] or b["t1_raw"]; t2 = b["t2"] or b["t2_raw"]
                variable_panel(b["n"], f"#{b['n']} · {t1} vs {t2}",
                               f"{b['fecha']} · {b['sede']}")
        else:
            st.info("Selecciona **Variables ▸** en un partido para capturar las variables del día.")


def _third_assignment_ui(standings):
    d = get()
    qual = engine.qualified_thirds(standings)
    with st.expander("⚙️ Asignar Mejores Terceros a las llaves", expanded=False):
        if len(qual) < 8:
            st.warning("Aún no hay 8 terceros definidos. Completa más resultados de grupo.")
            return
        st.caption("Elige qué tercero clasificado va en cada llave que lo requiere "
                   "(solo entre los 8 mejores).")
        options = ["—"] + [f"{t['team']} (3° {t['group']})" for t in qual]
        team_by_label = {f"{t['team']} (3° {t['group']})": t["team"] for t in qual}
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
def tab_compartir():
    d = get()
    _, bracket = compute()
    st.subheader("Compartir con el administrador")
    only = st.checkbox("Solo partidos con datos capturados", value=True)
    payload = export_share.build_share_payload(d, bracket, only_with_data=only)
    js = export_share.to_json(payload)
    st.caption(f"{len(payload['partidos'])} partido(s) en el envío.")
    st.code(js, language="json")
    st.download_button("⬇️ Descargar JSON", js,
                       file_name="quiniela_envio.json", mime="application/json")
    st.caption("Copia el bloque de arriba y pégalo en WhatsApp, o descarga el archivo.")


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


def main():
    if not check_password():
        return
    init_state()
    sidebar()
    st.title("Quiniela Mundial 2026")

    tabs = st.tabs(["Grupos", "Posiciones", "Ronda de 32", "Octavos",
                    "Cuartos", "Semifinales", "Tercer Lugar", "Final", "Compartir"])
    with tabs[0]: tab_grupos()
    with tabs[1]: tab_posiciones()
    with tabs[2]: tab_eliminatoria("R32")
    with tabs[3]: tab_eliminatoria("R16")
    with tabs[4]: tab_eliminatoria("QF")
    with tabs[5]: tab_eliminatoria("SF")
    with tabs[6]: tab_eliminatoria("P3")
    with tabs[7]: tab_eliminatoria("F")
    with tabs[8]: tab_compartir()


if __name__ == "__main__":
    main()
