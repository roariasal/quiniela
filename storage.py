# -*- coding: utf-8 -*-
"""
Persistencia del estado de la quiniela.

Dos backends, seleccionados automaticamente:

1) GITHUB (produccion / Streamlit Cloud)
   Si existen los secrets de GitHub, el estado se guarda como un archivo JSON
   dentro del repo (Contents API). Cada guardado hace un commit. Sobrevive a
   los reinicios del filesystem efimero de Streamlit Cloud.

2) DISCO LOCAL (desarrollo)
   Si no hay secrets, cae a un archivo JSON local con escritura atomica.

Secrets esperados (Streamlit -> Settings -> Secrets), formato TOML:

    APP_PASSWORD = "tu-contraseña"

    [github]
    token  = "ghp_xxx"              # PAT con permiso de escritura (Contents)
    repo   = "roariasal/quiniela"   # owner/repo
    path   = "quiniela_estado.json" # ruta del archivo de estado en el repo
    branch = "main"
"""
import base64
import json
import os
import tempfile
from datetime import datetime

import requests

DEFAULT_PATH = os.environ.get("QUINIELA_FILE", "quiniela_estado.json")
API = "https://api.github.com"


# ---------------------------------------------------------------------------
# Estado base
# ---------------------------------------------------------------------------
def empty_state(owner="Rod"):
    return {
        "owner": owner,
        "updated": None,
        "group_results": {},
        "third_assignments": {},
        "ko_winners": {},
        "variables": {},
    }


def _merge_defaults(data):
    base = empty_state(data.get("owner", "Rod"))
    base.update({k: data.get(k, base[k]) for k in base})
    return base


# ---------------------------------------------------------------------------
# Deteccion de backend
# ---------------------------------------------------------------------------
def _gh_conf():
    """Devuelve la config de GitHub desde st.secrets, o None si no hay."""
    try:
        import streamlit as st
        if "github" not in st.secrets:
            return None
        g = st.secrets["github"]
        token = g.get("token")
        repo = g.get("repo")
        if not token or not repo:
            return None
        return {
            "token": token,
            "repo": repo,
            "path": g.get("path", "quiniela_estado.json"),
            "branch": g.get("branch", "main"),
        }
    except Exception:
        return None


def backend_name():
    return "github" if _gh_conf() else "local"


# ---------------------------------------------------------------------------
# Backend GitHub (Contents API)
# ---------------------------------------------------------------------------
def _gh_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_get(conf):
    """Devuelve (contenido_dict, sha) o (None, None) si el archivo no existe."""
    url = f"{API}/repos/{conf['repo']}/contents/{conf['path']}"
    r = requests.get(url, headers=_gh_headers(conf["token"]),
                     params={"ref": conf["branch"]}, timeout=15)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    payload = r.json()
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    return json.loads(raw), payload["sha"]


def _gh_put(conf, state, sha):
    url = f"{API}/repos/{conf['repo']}/contents/{conf['path']}"
    content_b64 = base64.b64encode(
        json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    body = {
        "message": f"Actualizar estado quiniela ({state['updated']})",
        "content": content_b64,
        "branch": conf["branch"],
    }
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=_gh_headers(conf["token"]),
                     data=json.dumps(body), timeout=15)
    r.raise_for_status()
    return r.json()["content"]["sha"]


# ---------------------------------------------------------------------------
# Backend disco local
# ---------------------------------------------------------------------------
def _local_load(path):
    if not os.path.exists(path):
        return empty_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _merge_defaults(json.load(f))
    except (json.JSONDecodeError, OSError):
        return empty_state()


def _local_save(state, path):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------
def load_state(path=DEFAULT_PATH):
    conf = _gh_conf()
    if conf:
        try:
            data, sha = _gh_get(conf)
            if data is None:
                return empty_state()
            state = _merge_defaults(data)
            state["_sha"] = sha  # guardamos el sha para el proximo put
            return state
        except Exception as e:
            # si GitHub falla, no perdemos la sesion: devolvemos vacio y avisamos
            st_warn(f"No se pudo leer el estado de GitHub: {e}")
            return empty_state()
    return _local_load(path)


def save_state(state, path=DEFAULT_PATH):
    state["updated"] = datetime.now().isoformat(timespec="seconds")
    conf = _gh_conf()
    if conf:
        sha = state.get("_sha")
        if sha is None:
            _, sha = _gh_get(conf)
        clean = {k: v for k, v in state.items() if not k.startswith("_")}
        new_sha = _gh_put(conf, clean, sha)
        state["_sha"] = new_sha  # mutamos el dict del llamador
        return state["updated"]
    _local_save({k: v for k, v in state.items() if not k.startswith("_")}, path)
    return state["updated"]


def st_warn(msg):
    try:
        import streamlit as st
        st.warning(msg)
    except Exception:
        pass
