#!/usr/bin/env bash
# Levanta la demo completa con un solo comando: datos de demostración, API y página.
# Uso: scripts/demo.sh [--sin-reiniciar] [--ayuda]
set -euo pipefail
unset CDPATH   # que "cd" no salte a otra carpeta ni imprima nada

PUERTO_API=${PUERTO_API:-8010}   # API (FastAPI)
PUERTO_WEB=${PUERTO_WEB:-5173}   # página (Vite)
BASE_DEMO=${BASE_DEMO:-datos_demo.db}
REINICIAR=1
PID_API=""
PID_WEB=""

ayuda() {
  cat <<'TEXTO'
Uso: scripts/demo.sh [--sin-reiniciar] [--ayuda]
Levanta la demo completa (datos de demostración, API y página) con un solo comando.
  --sin-reiniciar   conserva la base de la demo si ya existe (por defecto se recarga desde cero)
Variables opcionales: PUERTO_API (8010), PUERTO_WEB (5173), BASE_DEMO (datos_demo.db).
Ctrl+C apaga todo; los registros quedan en /tmp y al apagar se indica dónde.
TEXTO
}

fallar() { printf '%s\n' "$@" >&2; exit 1; }

# ---------- puertos ----------

# Éxito si algo escucha en el puerto (en cualquier dirección, IPv4 o IPv6).
puerto_ocupado() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk -v p=":$1" 'NR > 1 && $4 ~ (p "$") { hit = 1 } END { exit !hit }'
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null   # sin ss ni lsof: intenta conectar
  fi
}

# "nombre (PID n)" de quien escucha en el puerto, si se puede saber.
quien_usa() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | awk -v p=":$1" 'NR > 1 && $4 ~ (p "$")' |
      sed -n 's/.*users:(("\([^"]*\)",pid=\([0-9]*\).*/\1 (PID \2)/p' | head -n 1
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR == 2 { print $1 " (PID " $2 ")" }'
  fi
}

NL=$'\n'
ocupados=""
revisar_puerto() {   # revisar_puerto <puerto> <para qué se usa>
  local quien
  puerto_ocupado "$1" || return 0
  quien=$(quien_usa "$1" || true)
  ocupados+="${ocupados:+$NL}  - El puerto $1 ($2) ya está en uso${quien:+ por $quien}."
}

# ---------- procesos ----------

sondear() { curl -sf --noproxy '*' --max-time 2 "$1"; }

# esperar <url> <pid> <segundos>: éxito cuando la URL responde; falla si el proceso se
# cierra antes o se acaba el tiempo.
esperar() {
  local url=$1 pid=$2 intentos=$(($3 * 2)) i
  for ((i = 0; i < intentos; i++)); do
    kill -0 "$pid" 2>/dev/null || return 1
    sondear "$url" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}

# detener <pid>: apaga el servicio con todo su grupo de procesos (PGID = PID, ver más abajo)
# y espera a que termine; si no cae en 5 s, lo fuerza. Siempre por PID, nunca por nombre.
detener() {
  local pid=$1 i
  [ -n "$pid" ] || return 0
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  for ((i = 0; i < 10; i++)); do
    kill -0 -- "-$pid" 2>/dev/null || kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 -- "-$pid" 2>/dev/null || kill -0 "$pid" 2>/dev/null; then
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null || true
}

# La base usa WAL. Con la API ya detenida, pasa el WAL a la base y borra los archivos
# auxiliares -wal y -shm (no están en .gitignore y quedarían sueltos en la raíz del repositorio).
consolidar_base() {
  .venv/bin/python - "$1" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
c.close()
PY
}

# Se ejecuta siempre al salir (Ctrl+C, error o proceso caído) una vez iniciado el arranque.
apagar() {
  local codigo=$?
  set +e
  trap '' INT TERM HUP   # otra pulsación de Ctrl+C no debe cortar el apagado
  echo
  echo "Apagando la demo..."
  detener "$PID_WEB"
  detener "$PID_API"
  if [ -e "$BASE_DEMO-wal" ] || [ -e "$BASE_DEMO-shm" ]; then
    consolidar_base "$BASE_DEMO" >/dev/null 2>&1 || true
  fi
  echo "Demo apagada"
  echo "Registros: API: $LOG_API · Página: $LOG_WEB"
  exit "$codigo"
}

# ---------- argumentos ----------

for arg in "$@"; do
  case $arg in
    --sin-reiniciar) REINICIAR=0 ;;
    --ayuda | -h | --help) ayuda; exit 0 ;;
    *) printf 'Opción desconocida: %s\n\n' "$arg" >&2; ayuda >&2; exit 1 ;;
  esac
done

for puerto in "$PUERTO_API" "$PUERTO_WEB"; do
  case $puerto in
    '' | *[!0-9]*) fallar "Los puertos deben ser números (PUERTO_API=$PUERTO_API, PUERTO_WEB=$PUERTO_WEB)." ;;
  esac
done
[ "$PUERTO_API" != "$PUERTO_WEB" ] || fallar "PUERTO_API y PUERTO_WEB deben ser distintos."

# ---------- 1. raíz del repositorio ----------

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# ---------- 2. requisitos ----------

echo "Comprobando requisitos..."
if [ ! -x .venv/bin/python ] || [ ! -x .venv/bin/uvicorn ]; then
  fallar "Falta el entorno de Python de la demo (carpeta .venv) o está incompleto." \
         "Créelo con:  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  fallar "Falta Node.js (los comandos node y npm), necesario para la página." \
         "Instálelo desde https://nodejs.org y vuelva a ejecutar este script."
fi
command -v curl >/dev/null 2>&1 ||
  fallar "Falta el comando curl, necesario para comprobar que los servicios arrancaron."
if [ ! -d frontend/node_modules ]; then
  echo "Instalando las dependencias de la página (solo la primera vez, puede tardar)..."
  (cd frontend && npm ci) ||
    fallar "No se pudieron instalar las dependencias de la página (npm ci)." \
           "Revise su conexión a internet y ejecute:  cd frontend && npm ci"
fi

# ---------- 3. puertos libres ----------

revisar_puerto "$PUERTO_API" "la API"
revisar_puerto "$PUERTO_WEB" "la página"
if [ -n "$ocupados" ]; then
  fallar "No se puede iniciar la demo: hay puertos ocupados." \
         "$ocupados" \
         "No se detuvo ningún proceso. Cierre lo que usa esos puertos (por ejemplo, otra demo abierta)" \
         "o elija otros:  PUERTO_API=8011 PUERTO_WEB=5174 scripts/demo.sh"
fi

# ---------- 4. datos de demostración en una base propia ----------

export RUTA_BASE_DATOS="$BASE_DEMO"
export CLAVE_ORIENTADOR=demo-orientador   # accesos de demostración predecibles, pase lo que pase en .env
if [ "$REINICIAR" = 1 ] || [ ! -e "$BASE_DEMO" ]; then
  echo "Cargando datos de demostración en $BASE_DEMO..."
  rm -f "$BASE_DEMO-wal" "$BASE_DEMO-shm"   # restos de una corrida anterior (la base usa WAL)
  .venv/bin/python scripts/semilla_demo.py --reiniciar --base "$BASE_DEMO" --matching | sed 's/^/  /' ||
    fallar "No se pudieron cargar los datos de demostración (vea el error de arriba)."
else
  echo "Se conserva la base existente $BASE_DEMO (--sin-reiniciar)."
fi

# ---------- 5 y 6. API y página en segundo plano ----------

LOG_API=$(mktemp /tmp/demo-api.XXXXXX)
LOG_WEB=$(mktemp /tmp/demo-web.XXXXXX)
trap apagar EXIT
trap 'exit 0' INT TERM HUP   # Ctrl+C también termina en apagar() por la trampa de EXIT

# Si la página usa otro puerto, la API debe permitir ese origen; si la API usa otro, la
# página debe saber dónde encontrarla.
[ "$PUERTO_WEB" = 5173 ] || export ORIGENES_PERMITIDOS="http://localhost:$PUERTO_WEB"
[ "$PUERTO_API" = 8010 ] || export VITE_API_URL="http://localhost:$PUERTO_API"

# Con control de trabajos (set -m) cada servicio queda en su propio grupo de procesos, con
# PGID igual a su PID: así "kill -- -PID" también apaga a los hijos (npm lanza a vite como
# otro proceso y, si solo se matara a npm, vite seguiría ocupando el puerto).
echo "Iniciando la API (puerto $PUERTO_API)..."
set -m
.venv/bin/uvicorn api.main:app --port "$PUERTO_API" --timeout-keep-alive 30 --log-level warning \
  >"$LOG_API" 2>&1 </dev/null &
PID_API=$!
set +m
if ! esperar "http://localhost:$PUERTO_API/salud" "$PID_API" 20; then
  echo "La API no quedó lista (se cerró o no respondió en 20 s). Últimas líneas de su registro:" >&2
  tail -n 20 "$LOG_API" | sed 's/^/  /' >&2
  exit 1
fi

echo "Iniciando la página (puerto $PUERTO_WEB)..."
set -m
(cd frontend && exec npm run dev -- --port "$PUERTO_WEB" --strictPort) >"$LOG_WEB" 2>&1 </dev/null &
PID_WEB=$!
set +m
if ! esperar "http://localhost:$PUERTO_WEB" "$PID_WEB" 30; then
  echo "La página no quedó lista (se cerró o no respondió en 30 s). Últimas líneas de su registro:" >&2
  tail -n 20 "$LOG_WEB" | sed 's/^/  /' >&2
  exit 1
fi

# ---------- 7. resumen ----------

salud=$(sondear "http://localhost:$PUERTO_API/salud" || echo "(no se pudo leer /salud)")
echo
echo "=============================================================="
echo "  La demo está lista"
echo "=============================================================="
echo "  Abra en el navegador:  http://localhost:$PUERTO_WEB"
echo "  API y documentación:   http://localhost:$PUERTO_API/docs"
echo
echo "  Agentes conectados (GET /salud):"
echo "    $salud"
echo
echo "  Accesos de demostración (botones en la pantalla de entrada, o pegue el código):"
printf '    %-26s %s\n' "Orientador" "demo-orientador"
printf '    %-26s %s\n' "Joven (deslizar en vivo)" "demo-j11  (Lucía)"
printf '    %-26s %s\n' "Empresa" "demo-e_super"
echo
echo "  Registros:  API: $LOG_API"
echo "              Página: $LOG_WEB"
echo
echo "  Presione Ctrl+C para apagar todo."
echo "=============================================================="

# ---------- 8. vigilar: si algo se cae, se apaga todo ----------

while kill -0 "$PID_API" 2>/dev/null && kill -0 "$PID_WEB" 2>/dev/null; do
  sleep 1
done
if ! kill -0 "$PID_API" 2>/dev/null; then
  echo "La API se detuvo de forma inesperada. Últimas líneas de su registro:" >&2
  tail -n 20 "$LOG_API" | sed 's/^/  /' >&2
else
  echo "La página se detuvo de forma inesperada. Últimas líneas de su registro:" >&2
  tail -n 20 "$LOG_WEB" | sed 's/^/  /' >&2
fi
exit 1
