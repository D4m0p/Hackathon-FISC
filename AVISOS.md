# Avisos para el equipo

El asistente de cada integrante lee la sección que le corresponde y se la dice al
usuario al empezar. Cuando un aviso ya se atendió, su dueño lo borra.

---

## Para A (Damo) — 17/10/2026 — pedido de B: centros de formación como tercer actor

**Por qué.** Evaluamos el proyecto contra la rúbrica y el punto más flojo de "Impacto" es que el
reto pide un mercado de **tres lados** (jóvenes, empresas y **centros de formación**) y los
centros hoy solo son datos: no ven nada ni deciden nada. El reto dice que quieren "llenar
cursos con quien los aprovecha". Proponemos una sola pantalla con una sola decisión, sin
inventar lógica nueva: reutiliza lo que ya calculan Formación (`PlanFormacion`) y
`casi_califica`. Suma a la vez orden determinístico, acción real (descontar cupo, traza,
aviso) y humano en el ciclo (el centro decide). En la demo son ~20 s.

**Lo que le pedimos (backend; B hace todo el frontend contra este formato):**

1. **Rol `centro`** en `api/seguridad.py` (`Rol = Literal["joven","empresa","orientador","centro"]`),
   con `sujeto` = el valor de `Curso.centro` (p. ej. `"INADEH"`). `/yo` → `{rol: "centro", sujeto: "INADEH"}`.
   En la semilla, token de demo **`demo-inadeh`** (rol centro, sujeto `INADEH`).
2. **`GET /centros/{centro}/demanda`** (ese centro u orientador) →
   ```
   [{curso: Curso,
     reservas: [{joven_id, fecha}],
     interesados: [{joven_id, corregimiento, en_plan: bool,
                    vacantes_que_abre: [{vacante_id, titulo}],
                    minutos: int | null, costo_semanal: float | null,
                    cabe_en_horario: bool, motivo: str}]}]
   ```
   - Interesados = jóvenes cuyo `PlanFormacion` incluye el curso **∪** jóvenes con un
     `CasiCalifica` de tipo `habilidad` cuyo código está en `habilidades_otorgadas`.
     Sin los que ya tienen reserva en ese curso.
   - `vacantes_que_abre`: vacantes que el joven pasaría a cumplir con ese curso
     (las de su plan o su casi-califica).
   - `minutos` / `costo_semanal`: traslado del joven al corregimiento del curso (null si no hay dato).
   - **Orden determinístico**: primero quienes **pueden asistir** (`cabe_en_horario` y traslado
     dentro de su `max_minutos_traslado`), luego más `vacantes_que_abre`, luego `en_plan`, luego
     menos `minutos`, luego `joven_id`. (Lo probamos con datos de demo: sin el primer criterio,
     el #1 de "Marketing digital" era un joven al que el curso le choca con el horario.)
   - `motivo`: frase lista para mostrar, p. ej. "Le abre 1 vacante; 15 min de su casa".
   - Sin datos personales (igual que las tarjetas de empresa).
3. **`POST /cursos/{curso_id}/reservas`** `{joven_id, motivo}` (el centro dueño del curso u
   orientador) → `{curso, reserva: {joven_id, curso_id, fecha}}`. Descuenta
   `cupos_disponibles`, registra traza (agente `formacion`, acción `reservar_cupo`, motivo
   "Centro INADEH reservó cupo en «…» para j07: …") y notifica al joven
   ("Tiene un cupo reservado en «Marketing digital…»"). 400 si no hay cupos o ya está
   reservado; 403 si el curso es de otro centro.
4. **Que el joven vea su reserva:** agregar a `HistoriaJoven` un campo
   `reservas: [{curso_id, fecha}]` (opcional, no rompe nada).

Si algo del formato le complica, cámbielo y avísenos: lo ajustamos en el frontend. Cuando esté,
quiten esta sección.

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
