# Avisos para el equipo

El asistente de cada integrante lee la sección que le corresponde y se la dice al
usuario al empezar. Cuando un aviso ya se atendió, su dueño lo borra.

---

## Para A (Damo) — 17/10/2026 — pedido de B: que el matching se dispare solo (autonomía)

**Por qué.** La rúbrica de "Diseño agéntico" (25 %) evalúa **autonomía** y la regla de oro pide
agentes que "perciben, deciden y actúan". Hoy casi todo ya reacciona solo (Auditor al publicar,
reacomodo al liberar un cupo, aviso al aprobar), pero el **matching solo corre cuando el
orientador toca el botón**: una vacante nueva, un joven nuevo o un interés mutuo no generan
propuestas hasta ese clic. Queremos que el sistema tome la iniciativa y el humano siga
aprobando (las propuestas quedan pendientes como hoy).

**Lo que le pedimos (orquestador):**
1. Un ayudante tipo `_reacomodar`, p. ej. `_matching_automatico(disparador, objeto_id)`, que
   corra `ejecutar_matching()`, calcule las propuestas **nuevas** pendientes y registre traza:
   agente `matching`, **acción `auto_matching`**, `entrada = {disparador, objeto_id}`,
   `salida = {nuevas: ["j03|v05", ...]}` y un `motivo` listo para mostrar, p. ej.
   *"Se publicó «Asistente de ventas»: el sistema buscó candidatos solo. Propuestas nuevas: j11→v05"*
   o *"…Propuestas nuevas: ninguna"*.
2. Llamarlo en tres momentos (`disparador`):
   - `vacante_publicada`: al final de `publicar_vacante` cuando queda **publicada** (y en
     `orientador_publicar_bloqueada`).
   - `joven_nuevo`: al final de `registrar_joven` cuando el joven es nuevo.
   - `interes_mutuo`: en `deslizar` cuando devuelve `True`.
3. Que la semilla pueda apagarlo durante la carga masiva (p. ej. `Orquestador(..., automatico=False)`
   o un parámetro), para no correr 20 matchings al sembrar. En la API, encendido.
4. Opcional (si sobra tiempo): un "vigía" que, al correr, deje trazas `auto_aviso` para el
   orientador ("vacante sin candidatos", "joven sin opciones y el curso X tiene cupo").

**Frontend (B):** la pestaña Propuestas del orientador ya tiene el panel "Lo que el sistema hizo
solo", que lee `/trazas` y muestra las acciones automáticas (auditoría al publicar, reacomodo,
interés mutuo, rutas de formación, revisión de sesgo). Las trazas `auto_matching` y `auto_aviso`
aparecerán solas apenas existan; no hace falta otro endpoint.

---

## Para B (Anna) — 17/10/2026 — sus pedidos a A ya están en `main`

- **`GET /impacto`** y **`GET /jovenes/{id}/impacto`** con el formato que pidió. En la demo:
  de 121 pares joven–vacante, 13 viables; descartes: traslado 33, pasaje 42, horario 34,
  salario 5, habilidad 103 (un par cuenta en cada motivo que incumple).
- **Límite para anónimos en `POST /perfil/transcribir`**.
- **Centros de formación:** rol `centro` (token `demo-inadeh`, sujeto `INADEH`),
  `GET /centros/{centro}/demanda` y `POST /cursos/{curso_id}/reservas` con su formato y el orden
  determinístico que propuso (primero quienes pueden asistir). La reserva descuenta el cupo en
  una sola operación atómica, deja traza (`formacion · reservar_cupo`) y avisa al joven; 400 si
  no hay cupos o ya está reservado, 403 si el curso es de otro centro. `HistoriaJoven.reservas`
  ya viene. En la demo, "Marketing digital y redes sociales" tiene 1 cupo y 3+ interesados (j07
  primero).

Formato exacto en la sección 7 de `AGENTS.md`. Puede borrar esta sección cuando lo vea.

---

## Para C (Diego) — 16/10/2026, 6 p. m. — sus dos pedidos ya están hechos

**A. Pesos al Auditor (lo que pidió de `flujo.py`).** El orquestador ahora llama
`auditar_matching(resultado, jovenes, datos, vacantes, matriz, pesos=...)` con los MISMOS
pesos que usó el matching. Agregue el parámetro `pesos: Pesos | None = None` a su
`auditar_matching` (o `**kwargs`) y úselo al recalcular el `Desglose`. Mientras su
versión no lo tenga, se le sigue llamando sin él, así que nada se rompe.
Prueba de integración: `tests/test_integracion_c.py`.

**B. `OfertaIncompleta` del Mercado → HTTP 422.** `POST /ofertas` responde 422 con
`{"detail": "...", "faltantes": [...]}`. La clase oficial está en
`orquestador/interfaces.py`:

```python
from orquestador.interfaces import OfertaIncompleta
raise OfertaIncompleta(["salario_mensual", "turnos"])   # queda en .faltantes
```

Lo ideal es que su `OfertaIncompleta` herede de esa (`class OfertaIncompleta(interfaces.OfertaIncompleta)`)
o la importe directamente. Por si no alcanza, la API también reconoce una clase propia
con ese nombre y lee la lista de `faltantes`, `campos`, `campos_faltantes` o `pendientes`.
La oferta incompleta queda en la traza del Mercado (`oferta_incompleta`).

**C. Suba su Mercado y los contrafactuales** (`git pull --rebase --autostash` antes y
revise que no haya conflictos; ver la sección 1 de `AGENTS.md`). Clase `Mercado` exportada
en `agentes/mercado/__init__.py` con constructor sin argumentos: la API la conecta sola.

---

## Para C (Diego) — 16/10/2026

**1. Haga `git pull` antes de seguir con el Auditor.** A corrigió tres casos en
`agentes/auditor/detector.py`, con acuerdo del equipo (commit `d0243be`):

| Texto de la oferta | Antes | Ahora |
|---|---|---|
| "No se requiere foto obligatoria. Enviar CV con foto al correo." | Aprobaba | Bloquea (una negación ya no oculta un requisito real más adelante) |
| "No se aceptan menores de 18 años." | Bloqueaba | Aprueba (excluir menores de edad es legal) |
| "No se exige buena presencia ni excelente presentación." | — | Aprueba ("ni" continúa la negación; también se reconocen "pide", "exigimos"…) |

Sus 51 pruebas siguen igual; las nuevas están al final de `tests/test_auditor_ofertas.py`.
Su trabajo ya está conectado: `GET /salud` muestra `"auditor": "Auditor"` y la oferta
v10 de la demo queda bloqueada. Buen trabajo.

**2. Configure su nombre en git.** Sus commits salen como `root <root@Diego-Laptop.localdomain>`
y así se verían en el repositorio que evalúa el jurado:

```bash
git config --global user.name "Su nombre"
git config --global user.email "su@correo.com"
```

**3. Lo que falta de su parte (ver `TAREAS.md`, bloque C):**
- Contrafactuales en `Auditor.auditar_matching`: el corregimiento solo puede mover los
  componentes `traslado` y `salario` del `Desglose`; `habilidades` nunca (ya está probado
  en `tests/test_propiedades.py`). Nombre y género no pueden mover nada.
- Agente de Mercado (`agentes/mercado/`, clase `Mercado` con `normalizar_oferta`; la API
  lo conecta sola). Ver `orquestador/interfaces.py`.
- Datos con fuentes en `datos/`, evals en `evals/` (mínimo 15 casos, obligatorio) y
  documentos en `docs/`.
