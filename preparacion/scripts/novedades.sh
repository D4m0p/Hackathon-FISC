#!/usr/bin/env bash
# Muestra los commits nuevos de los compañeros en origin/<rama>.
# Imprime nada si no hay novedades. Se puede correr a mano en cualquier momento.
set -u

raiz=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$raiz" || exit 0
gitdir=$(git rev-parse --absolute-git-dir)
marca="$gitdir/novedades_visto"
ultimo_fetch="$gitdir/novedades_fetch"
rama=${NOVEDADES_RAMA:-main}

# git fetch como máximo una vez por minuto (o siempre con --ya).
ahora=$(date +%s)
antes=$(cat "$ultimo_fetch" 2>/dev/null || echo 0)
if [ "${1:-}" = "--ya" ] || [ $((ahora - antes)) -ge 60 ]; then
  timeout 15 git fetch -q origin "$rama" 2>/dev/null
  echo "$ahora" > "$ultimo_fetch"
fi

remoto=$(git rev-parse -q --verify "origin/$rama") || exit 0
visto=$(cat "$marca" 2>/dev/null || true)

# Primera vez: el estado actual queda como punto de partida.
if [ -z "$visto" ] || ! git cat-file -e "$visto^{commit}" 2>/dev/null; then
  echo "$remoto" > "$marca"
  exit 0
fi
[ "$visto" = "$remoto" ] && exit 0

yo=$(git config user.email)
salida=""
for sha in $(git log --reverse --format='%H' "$visto..$remoto"); do
  correo=$(git log -1 --format='%ae' "$sha")
  [ "$correo" = "$yo" ] && continue
  linea=$(git log -1 --format='- %an · %ar · %s (%h)' "$sha")
  archivos=$(git show --name-only --format= "$sha" | head -15 | sed 's/^/    /')
  salida+="$linea"$'\n'"$archivos"$'\n'
done
echo "$remoto" > "$marca"

[ -z "$salida" ] && exit 0
echo "NOVEDADES DEL EQUIPO en origin/$rama (avísele al usuario antes de seguir):"
printf '%s' "$salida"
if ! git merge-base --is-ancestor "$remoto" HEAD 2>/dev/null; then
  echo "Su copia local no los tiene todavía: git pull --rebase"
fi
