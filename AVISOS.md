# Avisos para el equipo

El asistente de cada integrante lee la sección que le corresponde y se la dice al
usuario al empezar. Cuando un aviso ya se atendió, su dueño lo borra.

---

## Para B (Anna) — 16/10/2026, noche — revisión de la página para la demo de mañana

**Atendido.** Los puntos 1, 2, 3 y los ids del 5 los hizo usted (`f8c1619`). A agregó lo que
faltaba: pestañas del orientador sin pisarse en celular (`estilos.css`) y la API por defecto en
la misma máquina desde donde se abre la página (`api.js`; en la laptop sigue siendo
`localhost:8010`). Verificado en el navegador: todas las vistas sin errores. Puede borrar
esta sección.

La página funciona: sin errores de consola en ninguna vista, se ve muy bien y todo usa la
API correctamente. Cinco ajustes, de más a menos importante:

1. **Botón de demo del joven:** "Joven (j01)" abre una lista vacía (j01 ya deslizó y tiene
   match en los datos de demo). Hay una joven nueva, **Lucía (`demo-j11`)**, con 5 tarjetas
   para deslizar en vivo. Sugerencia en `vistas/Entrada.jsx`: `{ token: "demo-j11", texto: "Joven (Lucía)" }`.
2. **"Sin match" pide el plan de cada joven y recibe 404** para los que no tienen (errores
   rojos en la consola). Ya existe `GET /planes` (orientador) que devuelve todos de una vez.
3. **`conNombres` no traduce códigos de una sola palabra** ("Tiene ventas" en minúscula):
   la expresión solo reconoce códigos con `_`. Cambio de una línea en `nombres.js`:
   `texto.replace(/\b[a-z]+(?:_[a-z]+)*\b/g, (c) => habilidades[c] || c)` (solo reemplaza
   si el código existe en el catálogo).
4. **Celular:** en el orientador, las pestañas "Bloqueadas" y "Sin match" quedan pegadas.
5. **Abrir la página desde otro dispositivo** (`http://IP:5173`): `crypto.randomUUID` no
   existe fuera de https/localhost y el registro y publicar vacante fallan; además la API
   apunta a `localhost:8010`. Para mañana: presentar desde la laptop con `localhost`. Si
   quieren el celular: usar `Math.random().toString(36).slice(2, 10)` como respaldo,
   `VITE_API_URL=http://IP:8010` y `ORIGENES_PERMITIDOS` con esa dirección.

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
