#!/usr/bin/env bash
# Uso: bash instalar.sh /ruta/al/repo [claude|opencode]
# Copia las reglas del equipo y el aviso de commits a un clon del repositorio.
# Las reglas y la configuración de los asistentes quedan fuera de git.
set -eu

origen=$(cd "$(dirname "$0")" && pwd)
repo=${1:?Indique la ruta del repositorio}
herramienta=${2:-claude}
cd "$repo"
git rev-parse --is-inside-work-tree >/dev/null

# 1. Excluir de git todo lo que es de los asistentes (sin tocar .gitignore).
exclude=$(git rev-parse --git-path info/exclude)
mkdir -p "$(dirname "$exclude")"
for p in CLAUDE.md AGENTS.md .claude/ .opencode/; do
  grep -qxF "$p" "$exclude" 2>/dev/null || echo "$p" >> "$exclude"
done

# 2. Reglas del equipo (mismo texto para los dos asistentes).
cp "$origen/CLAUDE.md" CLAUDE.md
cp "$origen/CLAUDE.md" AGENTS.md

# 3. Script de novedades (este sí va en el repo; solo lo sube A).
mkdir -p scripts
[ -f scripts/novedades.sh ] || cp "$origen/scripts/novedades.sh" scripts/novedades.sh
chmod +x scripts/novedades.sh

# 4. Aviso automático según la herramienta.
case "$herramienta" in
  claude)
    mkdir -p .claude
    cp "$origen/para_claude/settings.local.json" .claude/settings.local.json ;;
  opencode)
    mkdir -p .opencode/plugins
    cp "$origen/para_opencode/plugins/novedades.js" .opencode/plugins/novedades.js ;;
  *) echo "Herramienta desconocida: $herramienta (use claude u opencode)"; exit 1 ;;
esac

scripts/novedades.sh --ya || true
echo "Listo. Comprobación (no debe listar CLAUDE.md, AGENTS.md, .claude ni .opencode):"
git status --short
