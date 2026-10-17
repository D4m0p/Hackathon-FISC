#!/usr/bin/env bash
# Revisa todo lo necesario antes de entregar y termina con un resumen tipo semáforo.
# Uso: scripts/verificar_entrega.sh [--rapido] [--ayuda]
# Solo lee el repositorio: no levanta servidores ni toca los puertos de la demo. La única
# escritura es la de los evals en evals/resultados.md, que se devuelve a su estado anterior.
# Sin "set -e" a propósito: cada chequeo sigue aunque otro falle.
set -u
unset CDPATH   # que "cd" no salte a otra carpeta ni imprima nada
export GIT_OPTIONAL_LOCKS=0   # consultar git no debe tomar el candado del índice (otros pueden estar usándolo)

RAPIDO=0

ayuda() {
  cat <<'TEXTO'
Uso: scripts/verificar_entrega.sh [--rapido] [--ayuda]
Revisa todo lo necesario antes de entregar y termina con un resumen tipo semáforo:
✔ está bien, ✘ hay que corregirlo, ⚠ informativo o por revisar a mano.
Código de salida: 0 si no hubo ningún ✘, 1 si hubo alguno (2 si la opción no existe).
  --rapido   salta las pruebas y los evals (revisa solo lo demás)
  --ayuda    muestra este texto
Revisa, en orden: 1 pruebas · 2 evals · 3 que el frontend compile · 4 marcas de IA en lo que
irá al repositorio oficial · 5 higiene del repositorio · 6 entregables del reglamento ·
7 tag final-24h · 8 pendientes de AVISOS.md.
Se puede correr desde cualquier carpeta. No levanta servidores ni usa los puertos de la demo.
La corrida de evals reescribe evals/resultados.md: el script lo devuelve a su estado anterior.
TEXTO
}

for arg in "$@"; do
  case "$arg" in
    --rapido) RAPIDO=1 ;;
    --ayuda|-h|--help) ayuda; exit 0 ;;
    *) printf 'Opción desconocida: %s\n\n' "$arg" >&2; ayuda >&2; exit 2 ;;
  esac
done

# ---------- ubicación ----------

raiz=$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P) || exit 2
cd "$raiz" || exit 2
if ! command -v git >/dev/null 2>&1 || ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Este script debe correr dentro del repositorio git (no se encontró git o la carpeta no es un repositorio)." >&2
  exit 2
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/verificar_entrega.XXXXXX") || { echo "No se pudo crear una carpeta temporal." >&2; exit 2; }

# ---------- evals/resultados.md: se devuelve a su estado anterior ----------

RES_RUTA=evals/resultados.md
RES_EXISTIA=0       # 1 si el archivo existía antes de correr los evals
RES_COPIA=""        # copia del archivo antes de correr los evals (vacío si no se pudo copiar)
RES_MODO=""         # git: versionado y sin cambios locales | copia: con cambios locales o sin versionar
RES_PENDIENTE=0     # 1 mientras los evals puedan haberlo reescrito y falte devolverlo
RES_NOTA=""

# Antes de correr los evals: anota cómo dejar evals/resultados.md igual que está ahora.
guardar_resultados() {
  RES_EXISTIA=0
  RES_COPIA=""
  if git ls-files --error-unmatch -- "$RES_RUTA" >/dev/null 2>&1 && git diff --quiet -- "$RES_RUTA"; then
    RES_MODO=git
  else
    RES_MODO=copia
  fi
  if [ -e "$RES_RUTA" ]; then
    RES_EXISTIA=1
    RES_COPIA="$TMP/resultados.antes"
    cp -p -- "$RES_RUTA" "$RES_COPIA" 2>/dev/null || RES_COPIA=""
  fi
  RES_PENDIENTE=1
}

# Deja una nota en RES_NOTA si tuvo que restaurar. Solo usa "git checkout" si antes no había
# cambios locales; si los había, devuelve el contenido exacto desde la copia.
restaurar_resultados() {
  RES_NOTA=""
  [ "$RES_PENDIENTE" = 1 ] || return 0
  RES_PENDIENTE=0
  if [ "$RES_EXISTIA" = 0 ]; then   # no existía: no debe quedar el que generó la corrida
    if [ -e "$RES_RUTA" ]; then
      rm -f -- "$RES_RUTA"
      RES_NOTA="$RES_RUTA no existía antes: se eliminó el que generó la corrida de evals."
    fi
    return 0
  fi
  if [ -n "$RES_COPIA" ] && cmp -s -- "$RES_COPIA" "$RES_RUTA" 2>/dev/null; then
    return 0   # la corrida no lo cambió
  fi
  if [ "$RES_MODO" = git ]; then
    git checkout -- "$RES_RUTA" >/dev/null 2>&1
    RES_NOTA="$RES_RUTA se restauró con git checkout (la corrida de evals lo reescribe)."
  elif [ -n "$RES_COPIA" ]; then
    RES_NOTA="$RES_RUTA tenía cambios locales o no está versionado: se devolvió a su contenido anterior (la corrida de evals lo reescribe)."
  else
    RES_NOTA="ATENCIÓN: $RES_RUTA tenía cambios locales y no se pudo guardar una copia; la corrida de evals lo reescribió."
    return 0
  fi
  if [ -n "$RES_COPIA" ] && ! cmp -s -- "$RES_COPIA" "$RES_RUTA" 2>/dev/null; then
    cp -p -- "$RES_COPIA" "$RES_RUTA" 2>/dev/null   # si git no lo dejó idéntico, manda la copia
    cmp -s -- "$RES_COPIA" "$RES_RUTA" 2>/dev/null ||
      RES_NOTA="ATENCIÓN: no se pudo devolver $RES_RUTA a su estado anterior; revise git diff $RES_RUTA."
  fi
}

al_salir() {
  restaurar_resultados
  [ -z "$RES_NOTA" ] || printf '%s\n' "$RES_NOTA" >&2   # solo si salió sin restaurar (por ejemplo, Ctrl+C)
  rm -rf -- "$TMP"
}
trap al_salir EXIT
trap 'exit 129' HUP    # cerrar la terminal
trap 'exit 130' INT    # Ctrl+C
trap 'exit 141' PIPE   # salida cortada (por ejemplo, | head)
trap 'exit 143' TERM

# ---------- presentación ----------

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  EN_TERMINAL=1
  C_OK=$'\033[32m'; C_MAL=$'\033[31m'; C_AVISO=$'\033[33m'; C_TENUE=$'\033[2m'; C_NEGRITA=$'\033[1m'; C_FIN=$'\033[0m'
else
  EN_TERMINAL=0
  C_OK=""; C_MAL=""; C_AVISO=""; C_TENUE=""; C_NEGRITA=""; C_FIN=""
fi

n_ok=0; n_mal=0; n_aviso=0
fallas=()
trabajando_ahora=0

# Mientras corre algo lento, en la terminal se muestra qué es (en un archivo o tubería no imprime nada).
trabajando() {
  [ "$EN_TERMINAL" = 1 ] || return 0
  printf '%s… %s%s' "$C_TENUE" "$1" "$C_FIN"
  trabajando_ahora=1
}
quitar_trabajando() {
  if [ "$trabajando_ahora" = 1 ]; then printf '\r\033[K'; trabajando_ahora=0; fi
}

ok()       { quitar_trabajando; n_ok=$((n_ok + 1)); printf '%s✔%s %s\n' "$C_OK" "$C_FIN" "$1"; }
mal()      { quitar_trabajando; n_mal=$((n_mal + 1)); fallas+=("$1"); printf '%s✘%s %s\n' "$C_MAL" "$C_FIN" "$1"; }
aviso()    { quitar_trabajando; n_aviso=$((n_aviso + 1)); printf '%s⚠%s %s\n' "$C_AVISO" "$C_FIN" "$1"; }
omitido()  { quitar_trabajando; printf '%s–%s %s\n' "$C_TENUE" "$C_FIN" "$1"; }
nota()     { printf '    %s\n' "$1"; }
sangrar()  { sed 's/^/    /'; }

# ---------- utilidades ----------

ultima_linea() {   # última línea con texto del archivo, sin espacios sobrantes
  awk 'NF { ultima = $0 } END { print ultima }' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

cola() {   # cola <archivo> <n>: las últimas n líneas, sangradas
  tail -n "$2" "$1" | sangrar
}

lista_corta() {   # lista_corta <archivo> <máximo>: las primeras líneas, sangradas, y cuántas faltan
  local total
  total=$(( $(wc -l <"$1") ))
  head -n "$2" "$1" | sangrar
  if [ "$total" -gt "$2" ]; then nota "… y $((total - $2)) más"; fi
}

titulos_md() {   # titulos_md <archivo>: títulos de markdown (# …) fuera de los bloques de código
  awk '
    /^[[:space:]]*(```|~~~)/ { dentro = !dentro; next }
    !dentro && /^#+[[:space:]]/ { print }
  ' "$1"
}

# ---------- 1. Pruebas ----------

chequeo_pruebas() {
  local nombre="1. Pruebas" salida="$TMP/pytest.txt" estado
  if [ "$RAPIDO" = 1 ]; then omitido "$nombre: omitidas (--rapido)"; return; fi
  if [ ! -x .venv/bin/python ]; then
    mal "$nombre: no existe .venv/bin/python (cree el entorno: python -m venv .venv && .venv/bin/pip install -r requirements.txt)"
    return
  fi
  trabajando "Corriendo las pruebas (pytest)"
  .venv/bin/python -m pytest -q -p no:cacheprovider >"$salida" 2>&1 </dev/null
  estado=$?
  if [ "$estado" -eq 0 ]; then
    ok "$nombre: $(ultima_linea "$salida")"
  else
    mal "$nombre: fallan (pytest terminó con código $estado)"
    cola "$salida" 15
  fi
}

# ---------- 2. Evals ----------

chequeo_evals() {
  local nombre="2. Evals" salida="$TMP/evals.txt" estado linea
  if [ "$RAPIDO" = 1 ]; then omitido "$nombre: omitidos (--rapido)"; return; fi
  if [ ! -x .venv/bin/python ]; then
    mal "$nombre: no existe .venv/bin/python (cree el entorno: python -m venv .venv && .venv/bin/pip install -r requirements.txt)"
    return
  fi
  guardar_resultados
  trabajando "Corriendo los evals"
  .venv/bin/python -m evals.correr >"$salida" 2>&1 </dev/null
  estado=$?
  restaurar_resultados
  # "-w": que "no_satisfactoria" (corrida fallida) no cuente como "satisfactoria".
  linea=$(grep -iw 'satisfactoria' "$salida" | head -n 1)
  if [ "$estado" -eq 0 ] && [ -n "$linea" ]; then
    ok "$nombre: $linea"
  else
    mal "$nombre: la corrida no fue satisfactoria (código de salida $estado)"
    cola "$salida" 15
  fi
  if [ -n "$RES_NOTA" ]; then nota "$RES_NOTA"; fi
  RES_NOTA=""
}

# ---------- 3. Frontend ----------

chequeo_frontend() {
  local nombre="3. Frontend compila" salida="$TMP/build.txt" estado
  if [ ! -f frontend/package.json ]; then mal "$nombre: no existe frontend/package.json"; return; fi
  if [ ! -d frontend/node_modules ]; then
    aviso "$nombre: corra npm ci en frontend (no hay frontend/node_modules); no se pudo comprobar"
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    aviso "$nombre: no se encontró npm; no se pudo comprobar"
    return
  fi
  trabajando "Compilando el frontend (npm run build)"
  # La compilación sale a una carpeta temporal: no toca frontend/dist ni nada que esté sirviendo la demo.
  (cd frontend && npm run build -- --outDir "$TMP/dist" --emptyOutDir) >"$salida" 2>&1 </dev/null
  estado=$?
  if [ "$estado" -eq 0 ]; then
    ok "$nombre: npm run build sin errores ($(ultima_linea "$salida"))"
  else
    mal "$nombre: npm run build falla (código de salida $estado)"
    cola "$salida" 15
  fi
}

# ---------- 4. Marcas de IA ----------

# Los términos se escriben partidos para que este archivo no se detecte a sí mismo
# cuando se busque en el repositorio (este script también se copia al oficial).
TERMINOS_IA=(cla""ude anthr""opic open""ai chat""gpt gpt-""4 gpt-""5 copi""lot open""code co-authored""-by "generated"" with")
TERMINOS_COMMIT=(co-authored""-by "generated"" with" cla""ude anthr""opic)
RE_IA=$(IFS='|'; printf '%s' "${TERMINOS_IA[*]}")
RE_COMMIT=$(IFS='|'; printf '%s' "${TERMINOS_COMMIT[*]}")
MODELO_PRODUCTO=open""ai/gpt-oss-120b   # modelo de Groq: es parte del producto, no una marca del asistente
NO_VAN_AL_OFICIAL=(CLA""UDE.md AGENTS.md AVISOS.md TAREAS.md preparacion)

chequeo_marcas() {
  local nombre="4. Marcas de IA" archivos=() f excluir=() e cuantas_marcas cuantas_modelo total_commits con_marcas
  local coincidencias="" excluidos_texto=""
  for e in "${NO_VAN_AL_OFICIAL[@]}"; do
    excluir+=(":(exclude)$e")
    excluidos_texto+="${excluidos_texto:+, }$e"
  done
  while IFS= read -r -d '' f; do archivos+=("$f"); done < <(git ls-files -z -- . "${excluir[@]}")

  if [ "${#archivos[@]}" -gt 0 ]; then
    coincidencias=$(grep -IHniE -e "$RE_IA" -- "${archivos[@]}" 2>/dev/null)
  fi
  : >"$TMP/marcas.txt"
  : >"$TMP/modelo.txt"
  if [ -n "$coincidencias" ]; then
    # Cada línea llega como archivo:línea:texto. Sin el modelo del producto, si ya no queda
    # ningún término, la línea era solo el modelo (aviso); si queda alguno, es una marca.
    printf '%s\n' "$coincidencias" | awk -v marcas="$RE_IA" -v modelo="$MODELO_PRODUCTO" \
      -v f_marcas="$TMP/marcas.txt" -v f_modelo="$TMP/modelo.txt" '
      {
        if (!match($0, /:[0-9]+:/)) next
        ref = substr($0, 1, RSTART + RLENGTH - 2)
        texto = tolower(substr($0, RSTART + RLENGTH))
        gsub(modelo, "", texto)
        if (match(texto, marcas)) print ref "  (" substr(texto, RSTART, RLENGTH) ")" > f_marcas
        else print ref > f_modelo
      }'
  fi
  cuantas_marcas=$(( $(wc -l <"$TMP/marcas.txt") ))
  cuantas_modelo=$(( $(wc -l <"$TMP/modelo.txt") ))

  if [ "$cuantas_marcas" -eq 0 ]; then
    ok "$nombre · archivos: sin coincidencias en los ${#archivos[@]} archivos versionados (se excluyen $excluidos_texto/: no se copian al oficial)"
  else
    mal "$nombre · archivos: $cuantas_marcas línea(s) con marcas del asistente"
    lista_corta "$TMP/marcas.txt" 20
  fi
  if [ "$cuantas_modelo" -gt 0 ]; then
    aviso "$nombre · modelo del producto: $MODELO_PRODUCTO aparece en $cuantas_modelo línea(s); es parte del producto, no una marca del asistente: el equipo decide si se queda"
    lista_corta "$TMP/modelo.txt" 20
  fi

  total_commits=$(( $(git rev-list --count HEAD 2>/dev/null || echo 0) ))
  con_marcas=$(( $(git log --regexp-ignore-case --extended-regexp --grep="$RE_COMMIT" --format=%h 2>/dev/null | wc -l) ))
  if [ "$con_marcas" -eq 0 ]; then
    ok "$nombre · mensajes de commit: ninguno de los $total_commits commits lleva marcas"
  else
    aviso "$nombre · mensajes de commit: $con_marcas de $total_commits commits llevan marcas en el mensaje (el historial viejo no se puede cambiar sin reescribirlo; solo se informa)"
  fi
}

# ---------- 5. Higiene del repositorio ----------

chequeo_higiene() {
  local nombre="5. Higiene del repo" indebidos cuantos=0 problemas=""
  indebidos=$(git -c core.quotePath=false ls-files |
    grep -E '(^|/)\.env$|\.db$|\.db-wal$|\.db-shm$|(^|/)node_modules/|^frontend/dist/|(^|/)__pycache__(/|$)')
  if [ -n "$indebidos" ]; then
    printf '%s\n' "$indebidos" >"$TMP/indebidos.txt"
    cuantos=$(( $(wc -l <"$TMP/indebidos.txt") ))
    problemas="$cuantos archivo(s) versionado(s) que no deben estarlo (.env, *.db, *.db-wal, *.db-shm, node_modules/, frontend/dist/, __pycache__)"
  fi
  if ! git ls-files --error-unmatch -- .env.example >/dev/null 2>&1; then
    problemas+="${problemas:+; }falta .env.example en el repositorio (no está versionado)"
  fi
  if [ -z "$problemas" ]; then
    ok "$nombre: nada indebido versionado y .env.example está en el repositorio"
  else
    mal "$nombre: $problemas"
    if [ "$cuantos" -gt 0 ]; then lista_corta "$TMP/indebidos.txt" 20; fi
  fi
}

# ---------- 6. Entregables del reglamento ----------

P6="6. Entregables"
HALLADO=""
VACIO=""

# hallar_en_docs <glob>...: HALLADO = primer archivo con contenido de docs/ cuyo nombre
# coincide (sin distinguir mayúsculas); VACIO = el primero que coincide pero está vacío.
hallar_en_docs() {
  local expr=(-iname "$1") g
  shift
  for g in "$@"; do expr+=(-o -iname "$g"); done
  HALLADO=""
  VACIO=""
  [ -d docs ] || return 0
  HALLADO=$(find docs -type f \( "${expr[@]}" \) -size +0c 2>/dev/null | LC_ALL=C sort | head -n 1)
  VACIO=$(find docs -type f \( "${expr[@]}" \) ! -size +0c 2>/dev/null | LC_ALL=C sort | head -n 1)
}

# entregable_en_docs <título> <palabra para el mensaje> <glob>...
entregable_en_docs() {
  local titulo=$1 palabra=$2
  shift 2
  hallar_en_docs "$@"
  if [ -n "$HALLADO" ]; then ok "$P6 · $titulo: $HALLADO"
  elif [ -n "$VACIO" ]; then mal "$P6 · $titulo: $VACIO está vacío"
  elif [ ! -d docs ]; then mal "$P6 · $titulo: falta la carpeta docs/ (debe haber ahí un archivo con \"$palabra\" en el nombre)"
  else mal "$P6 · $titulo: no hay ningún archivo en docs/ con \"$palabra\" en el nombre"
  fi
}

# contar_casos <archivo.json>...: cuántos casos hay en total; sin salida si no se puede saber.
contar_casos() {
  local py=.venv/bin/python
  [ -x "$py" ] || py=$(command -v python3 || true)
  [ -n "$py" ] || return 1
  "$py" -c '
import json, sys
total = 0
for ruta in sys.argv[1:]:
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    if isinstance(datos, dict):
        if isinstance(datos.get("casos"), list):
            datos = datos["casos"]
        else:
            listas = [v for v in datos.values() if isinstance(v, list)]
            if len(listas) != 1:
                sys.exit(1)
            datos = listas[0]
    if not isinstance(datos, list):
        sys.exit(1)
    total += sum(1 for caso in datos if isinstance(caso, dict))
print(total)
' "$@" 2>/dev/null
}

chequeo_entregables() {
  local titulos par patron etiqueta faltan="" casos=() n_casos problemas="" n_datos

  # README.md con sus secciones (títulos de cualquier nivel; las raíces van sin tilde)
  if [ ! -s README.md ]; then
    mal "$P6 · README.md: no existe o está vacío"
  else
    titulos=$(titulos_md README.md)
    for par in "problema|problema" "arquitectura|arquitectura" "tecnolog|tecnologías" \
               "fuentes de datos|fuentes de datos" "instalaci|instalación" "credenciales|credenciales"; do
      patron=${par%%|*}
      etiqueta=${par#*|}
      printf '%s\n' "$titulos" | grep -qi -- "$patron" || faltan+="${faltan:+, }$etiqueta"
    done
    if [ -z "$faltan" ]; then
      ok "$P6 · README.md: tiene las secciones problema, arquitectura, tecnologías, fuentes de datos, instalación y credenciales"
    else
      mal "$P6 · README.md: faltan las secciones: $faltan"
    fi
  fi

  # Diagrama de arquitectura: un archivo en docs/ o un bloque mermaid en el README
  hallar_en_docs '*arquitectura*' '*diagrama*'
  if [ -n "$HALLADO" ]; then
    ok "$P6 · Diagrama de arquitectura: $HALLADO"
  elif [ -f README.md ] && grep -qiE '^[[:space:]]*(```|~~~)[[:space:]]*mermaid' README.md; then
    ok "$P6 · Diagrama de arquitectura: en el README (bloque mermaid)"
  elif [ -n "$VACIO" ]; then
    mal "$P6 · Diagrama de arquitectura: $VACIO está vacío"
  else
    mal "$P6 · Diagrama de arquitectura: ningún archivo en docs/ con \"arquitectura\" o \"diagrama\" en el nombre ni bloque mermaid en el README"
  fi

  # Evals: reporte y al menos 15 casos
  if [ ! -s "$RES_RUTA" ]; then
    problemas="falta $RES_RUTA o está vacío"
  elif grep -q 'EN CURSO / INCOMPLETA' "$RES_RUTA"; then
    problemas="$RES_RUTA quedó marcado EN CURSO / INCOMPLETA (una corrida de evals se interrumpió; corra python -m evals.correr)"
  fi
  casos=(evals/casos/*.json)
  [ -e "${casos[0]}" ] || casos=()
  n_casos=""
  if [ "${#casos[@]}" -gt 0 ]; then n_casos=$(contar_casos "${casos[@]}"); fi
  if [ "${#casos[@]}" -eq 0 ]; then
    problemas+="${problemas:+; }no hay casos en evals/casos/*.json (se necesitan al menos 15)"
  elif [ -n "$n_casos" ] && [ "$n_casos" -lt 15 ]; then
    problemas+="${problemas:+; }solo hay $n_casos casos en evals/casos/ (se necesitan al menos 15)"
  fi
  if [ -n "$problemas" ]; then
    mal "$P6 · Evals: $problemas"
  elif [ -z "$n_casos" ]; then
    aviso "$P6 · Evals: $RES_RUTA existe, pero no se pudieron contar los casos (${#casos[@]} archivos JSON en evals/casos/; se necesitan al menos 15 casos)"
  else
    ok "$P6 · Evals: $RES_RUTA existe y hay $n_casos casos en ${#casos[@]} archivos de evals/casos/ (mínimo 15)"
  fi

  entregable_en_docs "Bitácora de IA" "bitacora" '*bit*cora*'
  entregable_en_docs "Documento de metodología" "metodolog" '*metodolog*'

  if [ -s .env.example ]; then ok "$P6 · .env.example: existe"; else mal "$P6 · .env.example: no existe o está vacío"; fi

  if [ -d datos ]; then
    n_datos=$(( $(find datos -type f -size +0c 2>/dev/null | wc -l) ))
    if [ "$n_datos" -gt 0 ]; then
      ok "$P6 · Datos con fuentes: datos/ tiene $n_datos archivo(s)"
    else
      mal "$P6 · Datos con fuentes: datos/ no tiene ningún archivo con contenido (los datos de demo de scripts/demo/ son ilustrativos)"
    fi
  else
    mal "$P6 · Datos con fuentes: falta datos/ con al menos un archivo (los datos de demo de scripts/demo/ son ilustrativos)"
  fi
}

# ---------- 7. Tag de congelamiento ----------

chequeo_tag() {
  local nombre="7. Tag final-24h" tag_sha head_sha detalle_tag delante atras
  tag_sha=$(git rev-parse -q --verify 'refs/tags/final-24h^{commit}' 2>/dev/null)
  if [ -z "$tag_sha" ]; then
    aviso "$nombre: todavía no existe el tag final-24h (se crea al terminar: git tag final-24h && git push origin final-24h)"
    return
  fi
  head_sha=$(git rev-parse HEAD 2>/dev/null)
  detalle_tag=$(git log -1 --format='%h %s' "$tag_sha")
  if [ "$tag_sha" = "$head_sha" ]; then
    aviso "$nombre: existe y apunta al HEAD actual ($detalle_tag)"
    return
  fi
  delante=$(git rev-list --count "$tag_sha..HEAD" 2>/dev/null || echo 0)
  atras=$(git rev-list --count "HEAD..$tag_sha" 2>/dev/null || echo 0)
  if [ "$atras" -eq 0 ]; then
    aviso "$nombre: existe y apunta a $detalle_tag; no es el HEAD actual: HEAD tiene $delante commit(s) posteriores, que no cuentan"
  elif [ "$delante" -eq 0 ]; then
    aviso "$nombre: existe y apunta a $detalle_tag; no es el HEAD actual: el tag está $atras commit(s) adelante de HEAD"
  else
    aviso "$nombre: existe y apunta a $detalle_tag; no es el HEAD actual: HEAD y el tag se separaron ($delante commit(s) solo en HEAD, $atras solo en el tag)"
  fi
}

# ---------- 8. Pendientes en AVISOS.md ----------

chequeo_avisos() {
  local nombre="8. Pendientes en AVISOS.md" secciones cuantas
  if [ ! -f AVISOS.md ]; then ok "$nombre: no hay AVISOS.md"; return; fi
  secciones=$(titulos_md AVISOS.md | grep -E '^##[[:space:]]')
  if [ -z "$secciones" ]; then
    ok "$nombre: AVISOS.md no tiene secciones pendientes"
    return
  fi
  printf '%s\n' "$secciones" >"$TMP/avisos.txt"
  cuantas=$(( $(wc -l <"$TMP/avisos.txt") ))
  aviso "$nombre: $cuantas sección(es) sin atender"
  sed 's/^##[[:space:]]*/- /' "$TMP/avisos.txt" | sangrar
}

# ---------- resumen ----------

resumen() {
  local f
  printf '\n%sResumen%s: %s%d ✔%s · %s%d ✘%s · %s%d ⚠%s\n' "$C_NEGRITA" "$C_FIN" \
    "$C_OK" "$n_ok" "$C_FIN" "$C_MAL" "$n_mal" "$C_FIN" "$C_AVISO" "$n_aviso" "$C_FIN"
  if [ "$RAPIDO" = 1 ]; then
    printf 'Modo rápido: las pruebas y los evals no se corrieron.\n'
  fi
  if [ "$n_mal" -gt 0 ]; then
    printf 'Falta corregir:\n'
    for f in "${fallas[@]}"; do printf '  %s✘%s %s\n' "$C_MAL" "$C_FIN" "$f"; done
  fi
}

# ---------- programa ----------

rama=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
commit=$(git rev-parse --short HEAD 2>/dev/null || echo "sin commits")
printf '%sVerificación de entrega%s · %s · rama %s · %s\n\n' "$C_NEGRITA" "$C_FIN" "$raiz" "$rama" "$commit"

chequeo_pruebas
chequeo_evals
chequeo_frontend
chequeo_marcas
chequeo_higiene
chequeo_entregables
chequeo_tag
chequeo_avisos
resumen

if [ "$n_mal" -eq 0 ]; then exit 0; else exit 1; fi
