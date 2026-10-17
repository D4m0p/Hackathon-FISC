# Evals del agente Perfil

Casos en JSON que ejercitan el agente Perfil de punta a punta (texto del CV, entrevista, PDF, foto
y nota de voz) y generan `resultados.md`. Siguen el mismo formato que `evals/` (de C): cada caso
tiene `id`, `categoria`, `naturaleza`, `entrada` y `esperado`, y se corre dos veces para verificar
que sea determinista.

## Cómo correr

```bash
.venv/bin/python agentes/perfil/evals/correr.py            # sin red: escribe resultados.md
.venv/bin/python agentes/perfil/evals/correr.py --en-vivo  # además mide los casos «oro» con Groq real
.venv/bin/python -m pytest tests/test_perfil_evals.py -q    # el arnés en las pruebas del repo
```

La corrida normal retira `GROQ_API_KEY`: el LLM se **simula** con respuestas fijas del caso
(incluidas respuestas maliciosas o rotas) para medir lo que decide el código. El modo `--en-vivo`
mide la calidad del modelo real y **no** cuenta para el estado de la corrida.

## Categorías

- `extraccion` (casos «oro»): textos con la respuesta correcta conocida; fijan el comportamiento.
- `medicion` (`solo_metrica`): frases reales escritas sin pensar en las palabras clave. Cuentan
  para precisión y exhaustividad, pero no hacen fallar la corrida (miden calidad, no una regla).
- `validacion`: lo que el código hace con lo que propone el LLM: citas literales o sin tildes,
  citas inventadas, códigos fuera de la taxonomía, duplicados, tope de nivel 2 en la entrevista,
  respuestas fuera de tema, JSON fuera de esquema y LLM caído.
- `guardrails`: inyección por texto y por voz, intento de cerrar el delimitador `</cv>`, CV vacío
  o gigante, PDF dañado, formatos de imagen y audio no admitidos, audio vacío o muy largo, y
  servicios no disponibles.

## Métricas del reporte

- **Precisión y exhaustividad** de la extracción, sin LLM (respaldo por palabras clave) y en vivo.
- **Garantía de evidencia:** toda habilidad aceptada tiene su cita en el texto original.
- **Guardrails** cumplidos.

## Cómo agregar un caso

1. Agregue el objeto a `casos.json` (para un texto nuevo con respuesta conocida, `"oro": true`).
2. Verifique la expectativa contra el comportamiento real; no ajuste el sistema para que el caso
   pase. Si es una frase "de la vida real" que mide calidad, márquela `"solo_metrica": true`.
3. Corra el ejecutor y confirme el caso en `resultados.md`.
