# Resultados de los evals del agente Perfil

- Estado de la corrida: **SATISFACTORIA**
- Generado por `agentes/perfil/evals/correr.py`: 2026-10-17 14:05:09 UTC
- Commit: `e043092` · Python 3.14.4 · sin red (LLM simulado o ausente)
- Casos de reglas: **35** · cumplen: **35** · casos de medición (no cuentan para el estado): **8**

Cada caso se corrió dos veces y se compararon las salidas para verificar que sea determinista.

## Métricas

| Métrica | Valor | Qué mide |
|---|---|---|
| Precisión sin LLM, frases reales | 88.9 % | En 8 frases escritas sin pensar en las palabras clave: de lo que encontró el respaldo, cuánto era correcto |
| Exhaustividad sin LLM, frases reales | 72.7 % | En esas frases: de lo que tenía que salir, cuánto encontró (lo que se pierde aquí lo cubre el LLM; ver modo en vivo) |
| Extracción en casos de reglas | 100.0 % / 100.0 % | Precisión / exhaustividad en los 12 casos «oro» que fijan el comportamiento esperado |
| Garantía de evidencia | 36/36 casos | Toda habilidad aceptada tiene su cita en el texto original |
| Guardrails | 13/13 | Inyección (texto y voz), delimitador, entradas vacías, enormes, dañadas o de formato no admitido |

## Modo en vivo (openai/gpt-oss-120b, 2026-10-17 14:05:09 UTC)

No cuenta para el estado de la corrida: un modelo de lenguaje no es determinista.

- Precisión: **100.0 %** · Exhaustividad: **100.0 %**
- Garantía de evidencia: **20/20** casos (el código descarta toda cita que no esté en el texto)

| id | esperado | obtenido | método |
|---|---|---|---|
| perfil_oro_01 | atencion_cliente, manejo_caja | atencion_cliente, manejo_caja | llm |
| perfil_oro_02 | atencion_cliente, redes_sociales, ventas | atencion_cliente, redes_sociales, ventas | llm |
| perfil_oro_03 | logistica_bodega, reposicion_inventario | logistica_bodega, reposicion_inventario | llm |
| perfil_oro_04 | manipulacion_alimentos | manipulacion_alimentos | llm |
| perfil_oro_05 | soporte_tecnico | soporte_tecnico | llm |
| perfil_oro_06 | excel_basico | excel_basico | llm |
| perfil_oro_07 | ingles_conversacional | ingles_conversacional | llm |
| perfil_oro_08 | servicio_mesa | servicio_mesa | llm |
| perfil_oro_09 | logistica_bodega | logistica_bodega | llm |
| perfil_oro_10 | manipulacion_alimentos, redes_sociales, ventas | manipulacion_alimentos, redes_sociales, ventas | llm |
| perfil_oro_11 | — | — | llm |
| perfil_oro_12 | — | — | llm |
| perfil_medicion_01 | manejo_caja | manejo_caja | llm |
| perfil_medicion_02 | atencion_cliente, manejo_caja | atencion_cliente, manejo_caja | llm |
| perfil_medicion_03 | logistica_bodega, reposicion_inventario | logistica_bodega, reposicion_inventario | llm |
| perfil_medicion_04 | soporte_tecnico | soporte_tecnico | llm |
| perfil_medicion_05 | redes_sociales | redes_sociales | llm |
| perfil_medicion_06 | excel_basico | excel_basico | llm |
| perfil_medicion_07 | atencion_cliente, manejo_caja | atencion_cliente, manejo_caja | llm |
| perfil_medicion_08 | ingles_conversacional | ingles_conversacional | llm |

## Casos

| id | categoría | naturaleza | resultado | detalle |
|---|---|---|---|---|
| perfil_oro_01 | extraccion | determinista | cumple | ['atencion_cliente', 'manejo_caja'] |
| perfil_oro_02 | extraccion | determinista | cumple | ['atencion_cliente', 'redes_sociales', 'ventas'] |
| perfil_oro_03 | extraccion | determinista | cumple | ['logistica_bodega', 'reposicion_inventario'] |
| perfil_oro_04 | extraccion | determinista | cumple | ['manipulacion_alimentos'] |
| perfil_oro_05 | extraccion | determinista | cumple | ['soporte_tecnico'] |
| perfil_oro_06 | extraccion | determinista | cumple | ['excel_basico'] |
| perfil_oro_07 | extraccion | determinista | cumple | ['ingles_conversacional'] |
| perfil_oro_08 | extraccion | determinista | cumple | ['servicio_mesa'] |
| perfil_oro_09 | extraccion | determinista | cumple | ['logistica_bodega'] |
| perfil_oro_10 | extraccion | determinista | cumple | ['manipulacion_alimentos', 'redes_sociales', 'ventas'] |
| perfil_oro_11 | extraccion | determinista | cumple | ninguna |
| perfil_oro_12 | extraccion | determinista | cumple | ninguna |
| perfil_validacion_cita_01 | validacion | determinista | cumple | ['atencion_cliente'] |
| perfil_validacion_tildes_01 | validacion | determinista | cumple | ['atencion_cliente'] |
| perfil_validacion_inventada_01 | validacion | determinista | cumple | ninguna; descartadas ['ingles_conversacional'] |
| perfil_validacion_taxonomia_01 | validacion | determinista | cumple | ninguna; descartadas ['piloto_avion'] |
| perfil_validacion_duplicado_01 | validacion | determinista | cumple | ['manejo_caja'] |
| perfil_validacion_tope_informal_01 | validacion | determinista | cumple | ['logistica_bodega'] |
| perfil_validacion_fuera_de_tema_01 | validacion | determinista | cumple | ['logistica_bodega']; descartadas ['ingles_conversacional'] |
| perfil_validacion_esquema_01 | validacion | determinista | cumple | ['manejo_caja'] |
| perfil_validacion_llm_caido_01 | validacion | determinista | cumple | ['atencion_cliente', 'manejo_caja'] |
| perfil_validacion_pregunta_inexistente_01 | validacion | determinista | cumple | ninguna |
| perfil_guardrail_inyeccion_01 | guardrails | determinista | cumple | ninguna; descartadas ['piloto_avion'] |
| perfil_guardrail_delimitador_01 | guardrails | determinista | cumple | ['manejo_caja'] |
| perfil_guardrail_texto_normal_01 | guardrails | determinista | cumple | ['atencion_cliente', 'manejo_caja'] |
| perfil_guardrail_cv_vacio_01 | guardrails | determinista | cumple | ninguna |
| perfil_guardrail_cv_enorme_01 | guardrails | determinista | cumple | ninguna |
| perfil_guardrail_pdf_danado_01 | guardrails | revision_humana | cumple | error controlado: «No se pudo leer el PDF» |
| perfil_guardrail_imagen_formato_01 | guardrails | revision_humana | cumple | error controlado: «Formato de imagen no admitido (use JPG, PNG o WEBP)» |
| perfil_guardrail_foto_sin_llm_01 | guardrails | revision_humana | cumple | error controlado: «La lectura de fotos no está disponible; escriba el texto» |
| perfil_guardrail_audio_formato_01 | guardrails | revision_humana | cumple | error controlado: «Formato de audio no admitido (use una nota de voz de WhatsApp, MP3, M4A o WAV)» |
| perfil_guardrail_audio_largo_01 | guardrails | revision_humana | cumple | error controlado: «La nota de voz es muy larga: grabe menos de 2 minutos» |
| perfil_guardrail_audio_vacio_01 | guardrails | revision_humana | cumple | error controlado: «La grabación quedó vacía; intente de nuevo» |
| perfil_guardrail_audio_sin_llm_01 | guardrails | revision_humana | cumple | error controlado: «Las notas de voz no están disponibles ahora; escriba su respuesta» |
| perfil_guardrail_voz_inyeccion_01 | guardrails | determinista | cumple | ['ventas']; descartadas ['ingles_conversacional'] |
| perfil_medicion_01 | medicion | determinista | acierta | ['manejo_caja'] |
| perfil_medicion_02 | medicion | determinista | acierta | ['atencion_cliente', 'manejo_caja'] |
| perfil_medicion_03 | medicion | determinista | acierta | ['logistica_bodega', 'reposicion_inventario'] |
| perfil_medicion_04 | medicion | determinista | acierta | ['soporte_tecnico'] |
| perfil_medicion_05 | medicion | determinista | no acierta | códigos [] ≠ ['redes_sociales'] |
| perfil_medicion_06 | medicion | determinista | no acierta | códigos [] ≠ ['excel_basico'] |
| perfil_medicion_07 | medicion | determinista | no acierta | códigos ['manejo_caja', 'manipulacion_alimentos'] ≠ ['atencion_cliente', 'manejo_caja'] |
| perfil_medicion_08 | medicion | determinista | acierta | ['ingles_conversacional'] |

## Alcance

- Ejercita el agente directamente (sin API ni frontend); el endpoint `/perfil/transcribir` lo cubren las pruebas de `tests/test_perfil.py`.
- Sin red, el LLM se simula con respuestas fijas (incluidas respuestas maliciosas o rotas) para medir la validación determinística del código; la calidad del modelo real se mide con `--en-vivo`.
- La extracción «oro» sin LLM mide el respaldo por palabras clave, que es lo que usa el sistema cuando no hay servicio.
