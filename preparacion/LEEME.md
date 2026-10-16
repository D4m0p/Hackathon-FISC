# Preparación del equipo (esta carpeta NO va al repositorio)

## Contenido
- `CLAUDE.md`: reglas del equipo. Se instala como `CLAUDE.md` (Claude Code) y `AGENTS.md` (OpenCode).
- `scripts/novedades.sh`: avisa de los commits de los compañeros. Este sí va al repo (lo sube A).
- `para_claude/settings.local.json`: hook que corre el aviso al abrir sesión y en cada mensaje.
- `para_opencode/plugins/novedades.js`: lo mismo para OpenCode (aviso en pantalla + contexto del asistente).
- `instalar.sh`: deja todo en su lugar y excluye de git los archivos de los asistentes.
- `TAREAS.md`, `GUION_DEMO.md`.

## Instalación (cada integrante, una sola vez)
```bash
unzip preparacion.zip
git clone git@github.com:D4m0p/Hackathon-FISC.git ~/Hackathon-FISC
bash preparacion/instalar.sh ~/Hackathon-FISC claude     # si usa Claude Code
bash preparacion/instalar.sh ~/Hackathon-FISC opencode   # si usa OpenCode
```
En Windows, correrlo desde Git Bash o WSL.
Luego, reiniciar el asistente dentro del repo. Al terminar, `git status` no debe mostrar
`CLAUDE.md`, `AGENTS.md`, `.claude/` ni `.opencode/`.

## Modelo para OpenCode (gratis)
Probado el 2026-10-16 con OpenCode 2.0.14: **`opencode/deepseek-v4.1-flash-free`**
(OpenCode Zen, gratis, sin clave). Leyó las reglas, recibió el aviso de commits y lo explicó bien.
Para dejarlo fijo, en `~/.config/opencode/opencode.json`:
```json
{ "$schema": "https://opencode.ai/config.json", "model": "opencode/deepseek-v4.1-flash-free" }
```
Si se satura o cambia la lista de gratuitos: `opencode models | grep free` y probar
`opencode/glm-5.3-flash-free`. No usar para el asistente la misma clave de Groq que usa la app,
para no gastar el límite por minuto de la demo.
