# Evals

Pruebas de extremo a extremo, con casos en JSON, que ejercitan el sistema real
(matching, auditor y mercado) y generan un reporte reproducible. No reemplazan las
pruebas unitarias de `tests/`: aquí cada caso es un escenario completo y el reporte
agrega métricas.

## Cómo correr

```bash
python evals/correr.py            # escribe evals/resultados.md
python evals/correr.py --json     # además imprime el resumen en JSON
python -m pytest evals/test_evals.py -q   # pruebas del arnés
```

`correr.py` retira `GROQ_API_KEY` para ejecutarse sin red y sin costo. Como cada caso
se corre dos veces y se comparan las salidas normalizadas, también verifica que el
resultado sea determinista. Termina con código 1 si algún caso no cumple.

Al empezar, `correr.py` escribe en `resultados.md` una marca **EN CURSO / INCOMPLETA**:
así, si el proceso se interrumpe, nunca queda un reporte viejo presentado como el
resultado actual. El reporte final indica el **estado de la corrida**:
`SATISFACTORIA` solo si todos los casos cumplen y no hubo errores. Un fallo inesperado
de un caso no aborta la evaluación: queda registrado como error de evaluación.


## Estructura

- `casos/*.json`: un archivo por asunto; cada archivo es una lista de casos.
- `mundo.py`: traduce los datos del caso a modelos del contrato. No decide nada.
- `metricas.py`: compara lo esperado con lo observado y agrega métricas.
- `correr.py`: ejecuta los casos, verifica determinismo y escribe `resultados.md`.
- `test_evals.py`: pruebas del arnés (no del sistema): errores que no abortan, estado
  de la corrida, reporte que no se confunde con uno anterior.
- `resultados.md`: reporte generado (no se edita a mano).

## Estructura de un caso

```json
{
  "id": "matching_compatible_01",
  "asunto": "matching",
  "categoria": "matching",
  "naturaleza": "determinista",
  "descripcion": "Qué verifica este caso.",
  "entrada": { },
  "esperado": { "tipo": "asignacion_exacta", "asignaciones": [["j1", "v1"]], "sin_asignar": [] }
}
```

- `asunto`: `matching`, `detector`, `contrafactual` o `mercado` (elige el ejecutor).
- `categoria`: `matching`, `restricciones`, `sin_asignacion`, `contrafactual`,
  `detector`, `mercado`, `guardrails` o `malformadas`.
- `naturaleza`: `determinista` (el sistema decide) o `revision_humana` (lo correcto es
  derivar a una persona y no decidir solo).
- `etiqueta` (opcional, en detector): `discriminatoria` o `limpia`, para las métricas.
- `entrada`: datos del escenario, en el formato que espera cada ejecutor.
- `esperado.tipo`: `asignacion_exacta`, `sin_asignacion`, `propiedades`, `sin_hallazgo`,
  `hallazgo`, `bloquea`, `aprueba`, `vacante` o `error_controlado`. `sin_hallazgo` exige
  que no aparezca ningún hallazgo y que la auditoría global apruebe (`reglas` queda como
  documentación de lo que no debe aparecer).

Los tipos de salida que produce cada ejecutor están en `correr.py`; las comparaciones,
en `metricas.py`. Las métricas sin ejemplos suficientes se reportan como `N/A`.

## Alcance

- Cubre los agentes directamente; la API y el frontend quedan fuera.
- La ruta de formación no entra en esta primera entrega.
- Mercado corre sin red: mide la validación determinística y el respaldo por palabras
  clave, no la calidad del modelo de lenguaje real.

## Cómo agregar un caso

1. Añada el objeto JSON al archivo del asunto en `casos/`.
2. Verifique la expectativa contra el comportamiento real del sistema (leyendo el
   código o ejecutándolo); no ajuste el sistema para que el caso pase.
3. Corra `python evals/correr.py` y confirme que el caso queda en `resultados.md`.
