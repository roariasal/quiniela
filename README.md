# ⚽ Quiniela Mundial 2026

App Streamlit para seguir el Mundial 2026 con esquema de quiniela: predices
resultados, capturas las variables diarias del organizador y generas un JSON
para compartir por WhatsApp. La llave eliminatoria se propaga automáticamente
hasta el campeón. El estado se guarda de forma persistente en GitHub.

## Cómo funciona
- **Grupos** — marca 1 / X / 2 por partido. **Variables ▸** abre el panel
  derecho (Variable 1–4 + Marcador, texto libre que define el organizador).
- **Posiciones** — tabla calculada (3 pts victoria, 1 empate; desempate por
  diferencia de goles y goles a favor) + ranking de los mejores terceros.
  Los 8 mejores clasifican.
- **Ronda de 32** — *Asignar Mejores Terceros* manda cada tercero clasificado
  a su llave; los demás cruces se llenan solos.
- **Octavos → Final** — eliges ganador y se propaga al siguiente cruce.
  Tercer Lugar usa los perdedores de semis.
- **Compartir** — genera el JSON para copiar a WhatsApp o descargar.

## Despliegue en Streamlit Community Cloud

### 1. Sube el código a GitHub
Ya está en `roariasal/quiniela`.

### 2. Crea un Personal Access Token (para persistir el estado)
La app guarda tus predicciones como un archivo JSON dentro del propio repo,
así sobreviven a los reinicios de Streamlit Cloud.

- GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate
- Repository access: **Only select repositories** → `roariasal/quiniela`
- Permissions → Repository permissions → **Contents: Read and write**
- Genera y copia el token (`github_pat_...`)

### 3. Despliega
- [share.streamlit.io](https://share.streamlit.io) → **Create app** → desde GitHub
- Repository: `roariasal/quiniela` · Branch: `main` · Main file: `app_quiniela.py`

### 4. Configura los Secrets
En la app desplegada → **Settings → Secrets**, pega (formato TOML):

```toml
APP_PASSWORD = "tu-contraseña"

[github]
token  = "github_pat_xxx"
repo   = "roariasal/quiniela"
path   = "quiniela_estado.json"
branch = "main"
```

Guarda. La app se reinicia, pide tu contraseña y ya escribe el estado en el repo.

## Desarrollo local
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # opcional
streamlit run app_quiniela.py
```
Sin `secrets.toml`, la app corre sin contraseña y guarda el estado en un
`quiniela_estado.json` local (ignorado por git).

## Persistencia
- **Con secrets de GitHub** → estado en el repo (commit por cada guardado).
  El sidebar muestra ☁️ *Estado en GitHub (persistente)*.
- **Sin secrets** → estado en disco local. El sidebar muestra 💾 *Estado local*.

## Archivos
| Archivo | Rol |
|---|---|
| `app_quiniela.py` | UI Streamlit (entry point) + login |
| `engine.py` | Posiciones, ranking de terceros, propagación de llave (lógica pura) |
| `storage.py` | Persistencia dual: GitHub Contents API / disco local |
| `export_share.py` | Payload JSON para WhatsApp |
| `wc_data.py` | Datos del torneo (extraídos del Excel maestro) |

## Nota sobre los terceros
El ranking de los 12 terceros es automático (reglas FIFA por puntos). La
asignación de *cuál* tercero va a *cuál* llave es manual entre los 8
clasificados, porque la tabla oficial FIFA de asignación para el formato de
12 grupos depende del sorteo y no es determinista solo con los puntos.
