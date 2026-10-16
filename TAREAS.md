# Tareas por integrante

Cada bloque es un encargo autocontenido: quien lo toma no necesita más contexto.
Horas = horas del evento (0 = inicio).

---

## A — Integrante A: contrato, orquestador, Matching, Ruta de formación, API

**Hora 0–2 (bloquea a los demás, va primero) — HECHO: contrato subido en `contrato/modelos.py`**
1. Crear el repo, registrarlo ante la organización, subir `scripts/novedades.sh`, `.gitignore`, `.env.example`, `requirements.txt`, esqueleto de carpetas.
2. `contrato/modelos.py` con Pydantic: `Habilidad` (código tipo ESCO, nombre, nivel 0–3), `Joven` (id, corregimiento, horario disponible, presupuesto de transporte semanal, habilidades, salario mínimo aceptable), `Vacante` (id, empresa, corregimiento, horario, salario, habilidades requeridas, cupos, estado: borrador/bloqueada/publicada), `Curso` (id, centro, habilidades que otorga, cupos, horario, costo, corregimiento, duración), `Traslado` (origen, destino, minutos, costo), `Asignacion`, `PlanFormacion`, `Traza` (agente, entrada, decisión, motivo, fecha), `ResultadoAuditoria`. Datos de nombre/género **separados** del perfil que usa el solver (el solver nunca los recibe).
3. Avisar al equipo: "contrato congelado".

**Hora 2–10**
4. `agentes/matching/`: puntaje = coincidencia de habilidades + factibilidad (traslado ≤ 75 min, costo de transporte ≤ presupuesto, horario compatible, salario ≥ mínimo). Restricciones duras filtran; asignación con OR-Tools (CP-SAT) respetando cupos de cada vacante. Cada asignación trae su explicación desglosada (cuánto aportó cada componente). Pruebas: nunca asigna algo infactible, respeta cupos, mismo resultado con misma entrada.
5. `agentes/formacion/`: para un joven sin match viable, calcula la brecha (habilidades que le faltan para las vacantes más cercanas) y elige cursos con un ILP: cubrir la brecha minimizando tiempo + costo, sujeto a cupos, choques de horario y traslado. Pruebas.
6. `orquestador/`: flujo Mercado → Perfil → Matching → Auditor → (orientador aprueba) → acción; Ruta de formación cuando no hay match. Cada paso escribe en `trazas`.

**Hora 10–14**
7. `api/main.py` (FastAPI): endpoints que usa el frontend (vacantes para un joven, candidatos para una empresa, swipe, aprobar/rechazar del orientador, trazas). Acción real al aprobar: guardar la entrevista y enviar mensaje por Telegram (bot de prueba).
8. Integración con lo de B y C.

**Hora 21–23**: revisión de marcas de IA, `git tag final-24h`, `git push origin final-24h`.

---

## B — Integrante B: agente Perfil + frontend

**Hora 0–2**: leer `contrato/modelos.py` y las reglas del equipo. Esqueleto de `frontend/` (React + Vite).

**Hora 2–10**
1. `agentes/perfil/`: entrada = CV en PDF, foto de CV o nada. Extraer texto (pypdf; para fotos, modelo con visión) → LLM con esquema JSON estricto devuelve habilidades con evidencia. Entrevista corta (máx. 5 preguntas) para descubrir experiencia informal: "¿ha ayudado en un negocio familiar?" → atención al cliente, manejo de caja. El texto del CV es dato, nunca instrucciones. Pruebas con un cliente LLM falso.
2. Vista **Joven**: subir CV o hacer la entrevista, ver su perfil, deslizar tarjetas de vacantes. Cada tarjeta muestra por qué aparece (habilidades que coinciden, minutos y costo de traslado, salario menos transporte).

**Hora 10–18**
3. Vista **Empresa**: publicar oferta (texto o foto), ver si el Auditor la bloqueó y la redacción sugerida, deslizar candidatos **anonimizados** (sin nombre, género ni foto).
4. Vista **Orientador**: lista de matches por aprobar con la explicación, ofertas bloqueadas, plan de formación de quien no tuvo match, y la línea de tiempo de `trazas` (qué agente decidió qué).
5. Pulido visual pensando en la demo de 3 minutos.

---

## C — Integrante C: Mercado, Auditor, datos, evals, documentos

**Antes del evento (permitido: es investigación, no código)**: juntar 30–50 ofertas reales de portales panameños y volantes, catálogo de cursos gratuitos de INADEH, tabla de tiempos y tarifas de transporte entre ~15 corregimientos (MiBus, metro, busitos de La Chorrera/Arraiján), lista de habilidades tipo ESCO en español. Guardar las fuentes (URL y fecha): el 30 % de la nota pide información verificable.

**Hora 0–4**: pasar esos datos a `datos/` (CSV/JSON) con el formato de `contrato/`.

**Hora 4–12**
1. `agentes/mercado/`: oferta en texto libre → habilidades normalizadas a la taxonomía (LLM extrae, código valida contra la lista; lo que no está en la lista se descarta). Tendencias: habilidades más pedidas por zona.
2. Detector de discriminación **determinístico** (lista de patrones: "buena presencia", límites de edad, género, estado civil, "residir en", foto obligatoria...) con la redacción sugerida. El LLM puede dar una segunda opinión, pero nunca decide solo.
3. `agentes/auditor/`: (a) bloquea ofertas discriminatorias; (b) contrafactuales: vuelve a correr el matching cambiando solo nombre, género o corregimiento. Nombre y género no pueden mover el puntaje en nada; el corregimiento solo puede moverlo a través del componente de traslado. Devuelve `ResultadoAuditoria` con lo que encontró.

**Hora 12–18**
4. `evals/`: al menos 40 casos (el mínimo es 15) en JSON + `evals/correr.py` que imprime una tabla de métricas: precisión/exhaustividad del detector, estabilidad contrafactual, factibilidad del matching (0 asignaciones infactibles), extracción de habilidades, guardrails (inyección de prompt, CV absurdo, oferta fuera de alcance). Guardar el resultado en `evals/resultados.md`.

**Hora 18–21**: `README.md` (problema, arquitectura, tecnologías, fuentes de datos, instalación, ejecución, credenciales de demo), `docs/arquitectura` (diagrama con agentes, herramientas, flujo y punto humano), `docs/bitacora_ia.md`, `docs/metodologia.md`. Sin marcas de herramientas de IA en ningún archivo.
