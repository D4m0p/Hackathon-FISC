# Avisos para el equipo

El asistente de cada integrante lee la sección que le corresponde y se la dice al
usuario al empezar. Cuando un aviso ya se atendió, su dueño lo borra.

---

## Para C (Diego) — 17/10/2026 — de B: evals del agente Perfil (para sumarlos a los suyos)

B armó evals para Perfil con **su mismo formato** en `agentes/perfil/evals/` (43 casos: extracción,
validación de lo que propone el LLM, guardrails de texto, foto y voz; cada caso dos veces para
verificar determinismo). Resultado actual: 35/35 casos de reglas cumplen; sin LLM, precisión 88,9 %
y exhaustividad 72,7 % en frases reales; en vivo con Groq 96,4 % / 100 %; 100 % de habilidades
aceptadas con su cita en el texto.

- ¿Puede nombrarlos en `evals/LEEME.md` (sección Alcance: "Perfil tiene sus evals en
  `agentes/perfil/evals/`") y, si arma un resumen de evals para la metodología o la bitácora,
  incluir esas cifras?
- No toca su carpeta: si prefiere integrarlos a `evals/correr.py` como asunto `perfil`, el
  ejecutor está en `agentes/perfil/evals/correr.py` (`correr()` devuelve la lista de resultados).

---

## Para A (Damo) — 17/10/2026 — de B: PROPUESTA (para que opine, no es pedido): agente de Postulación acotado

Ya cumplimos los 3 agentes mínimos con 5, así que esto es opcional; B prefiere seguir mejorando
lo que existe. Se lo dejamos por si cree que suma en "Diseño agéntico".

El reto sugiere un agente de **Postulación** ("adapta CV y carta por oferta, agenda entrevistas y
envía listas cortas a la empresa"). La agenda ya la hace el orquestador; faltarían dos piezas:
1. **CV para esta vacante:** cuando la entrevista está confirmada, el código elige las habilidades
   del joven que pide la vacante (primero las obligatorias) con su cita real, más horario y
   traslado; el LLM solo redacta, con la misma validación de Perfil (lo que agregue fuera de lo
   elegido se descarta). El joven lo revisa e imprime. Viviría en `agentes/perfil/` (B).
2. **Lista corta para la empresa:** `GET /vacantes/{id}/lista-corta` con los aprobados y su
   resumen; sin datos personales salvo el nombre cuando la entrevista está confirmada (regla en
   la API, de A). B haría la vista.

¿Le parece que vale la pena? Si sí, B lo arma; si no, lo dejamos.

---

## Para A (Damo) — 17/10/2026 — de B: evals de Perfil en la verificación de entrega

¿Puede agregar `agentes/perfil/evals/correr.py` a `scripts/verificar_entrega.sh` (junto a
`evals/correr.py`)? Sale con código 1 si algún caso de reglas falla; corre sin red en ~2 s.
Ya hay `tests/test_perfil_evals.py`, así que `pytest` también lo cubre.

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
