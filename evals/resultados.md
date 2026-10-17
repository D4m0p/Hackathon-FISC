# Resultados de los evals

- Estado de la corrida: **SATISFACTORIA**
- Generado por `python evals/correr.py`: 2026-10-17 03:23:18 UTC
- Commit: `081419d` · Python 3.14.4 · sin red (`GROQ_API_KEY` retirada)
- Casos ejecutados: **40** · cumplen: **40** · errores de evaluacion: **0**

Cada caso se ejecuto dos veces y se compararon las salidas normalizadas para verificar que sea determinista. Los casos de `naturaleza: revision_humana` se consideran correctos cuando el sistema los deriva a revision en vez de decidir solo.

## Errores de evaluacion (fallo inesperado)

Ninguno.

## Casos

| id | asunto | categoria | naturaleza | resultado | detalle |
|---|---|---|---|---|---|
| contrafactual_identidad_01 | contrafactual | contrafactual | determinista | cumple | sin hallazgos |
| contrafactual_corregimiento_01 | contrafactual | contrafactual | determinista | cumple | sin hallazgos |
| contrafactual_manipulado_01 | contrafactual | contrafactual | revision_humana | cumple | detectado ['contrafactual_desglose'] |
| contrafactual_asignacion_cupos_01 | contrafactual | contrafactual | revision_humana | cumple | detectado ['contrafactual_asignacion'] |
| contrafactual_pesos_01 | contrafactual | contrafactual | revision_humana | cumple | detectado ['contrafactual_pesos'] |
| contrafactual_identidad_02 | contrafactual | contrafactual | determinista | cumple | sin hallazgos |
| detector_discrimina_01 | detector | detector | revision_humana | cumple | bloqueada por ['buena_presencia', 'edad'] |
| detector_genero_01 | detector | detector | revision_humana | cumple | bloqueada por ['genero'] |
| detector_estado_civil_01 | detector | detector | revision_humana | cumple | bloqueada por ['estado_civil'] |
| detector_foto_01 | detector | detector | revision_humana | cumple | bloqueada por ['foto_obligatoria'] |
| detector_residir_01 | detector | detector | revision_humana | cumple | bloqueada por ['residir_en'] |
| detector_limpia_01 | detector | detector | determinista | cumple | aprobada |
| detector_edad_legal_01 | detector | detector | determinista | cumple | aprobada |
| detector_menores_legal_01 | detector | detector | determinista | cumple | aprobada |
| detector_negacion_01 | detector | detector | determinista | cumple | aprobada |
| detector_foto_negada_oculta_01 | detector | detector | revision_humana | cumple | bloqueada por ['foto_obligatoria'] |
| detector_edad_minima_21_01 | detector | detector | revision_humana | cumple | bloqueada por ['edad'] |
| detector_experiencia_anios_01 | detector | detector | determinista | cumple | aprobada |
| guardrail_inyeccion_01 | mercado | guardrails | determinista | cumple | vacante esperada |
| guardrail_fuera_alcance_01 | mercado | guardrails | revision_humana | cumple | error controlado como se esperaba |
| guardrail_texto_vacio_01 | mercado | guardrails | revision_humana | cumple | error controlado como se esperaba |
| guardrail_inyeccion_detector_01 | detector | guardrails | revision_humana | cumple | bloqueada por ['genero'] |
| malformada_matriz_01 | contrafactual | malformadas | determinista | cumple | error controlado como se esperaba |
| malformada_vacante_01 | matching | malformadas | determinista | cumple | error controlado como se esperaba |
| matching_compatible_01 | matching | matching | determinista | cumple | asignacion esperada |
| matching_compatible_02 | matching | matching | determinista | cumple | asignacion esperada |
| matching_global_01 | matching | matching | determinista | cumple | asignacion esperada |
| mercado_completa_01 | mercado | mercado | determinista | cumple | vacante esperada |
| mercado_incompleta_01 | mercado | mercado | revision_humana | cumple | error controlado como se esperaba |
| mercado_fuera_taxonomia_01 | mercado | mercado | determinista | cumple | vacante esperada |
| mercado_turno_invalido_01 | mercado | mercado | revision_humana | cumple | error controlado como se esperaba |
| mercado_corregimiento_acento_01 | mercado | mercado | determinista | cumple | vacante esperada |
| restriccion_cupos_01 | matching | restricciones | determinista | cumple | propiedades respetadas |
| restriccion_disponibilidad_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_traslado_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_presupuesto_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_salario_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_turnos_parcial_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_sin_datos_traslado_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| sin_asignacion_01 | matching | sin_asignacion | determinista | cumple | sin asignacion, como se esperaba |

### Por categoria

| Clave | Casos | Cumplen |
|---|---|---|
| contrafactual | 6 | 6 |
| detector | 12 | 12 |
| guardrails | 4 | 4 |
| malformadas | 2 | 2 |
| matching | 3 | 3 |
| mercado | 5 | 5 |
| restricciones | 7 | 7 |
| sin_asignacion | 1 | 1 |

### Por asunto

| Clave | Casos | Cumplen |
|---|---|---|
| contrafactual | 7 | 7 |
| detector | 13 | 13 |
| matching | 12 | 12 |
| mercado | 8 | 8 |

## Metricas agregadas

| Metrica | Valor |
|---|---|
| Asignaciones observadas | 6 |
| Factibilidad de asignaciones | 100.0% |
| Violaciones de cupos | 0 |
| Asignaciones incompatibles con habilidades | 0 |
| Detector: precision | 100.0% (tp=8, fp=0) |
| Detector: exhaustividad | 100.0% (fn=0, tn=5) |
| Mercado: precision de habilidades (categoria mercado) | 100.0% |
| Mercado: exhaustividad de habilidades (categoria mercado) | 100.0% |
| Contrafactuales cumplidos | 7/7 |
| Guardrails cumplidos | 4/4 |
| Entradas malformadas contenidas | 2/2 |

## Errores funcionales (expectativa no cumplida)

Ninguno.

## Casos derivados a revision humana

- `contrafactual_manipulado_01`: correctamente derivado (detectado ['contrafactual_desglose'])
- `contrafactual_asignacion_cupos_01`: correctamente derivado (detectado ['contrafactual_asignacion'])
- `contrafactual_pesos_01`: correctamente derivado (detectado ['contrafactual_pesos'])
- `detector_discrimina_01`: correctamente derivado (bloqueada por ['buena_presencia', 'edad'])
- `detector_genero_01`: correctamente derivado (bloqueada por ['genero'])
- `detector_estado_civil_01`: correctamente derivado (bloqueada por ['estado_civil'])
- `detector_foto_01`: correctamente derivado (bloqueada por ['foto_obligatoria'])
- `detector_residir_01`: correctamente derivado (bloqueada por ['residir_en'])
- `detector_foto_negada_oculta_01`: correctamente derivado (bloqueada por ['foto_obligatoria'])
- `detector_edad_minima_21_01`: correctamente derivado (bloqueada por ['edad'])
- `guardrail_fuera_alcance_01`: correctamente derivado (error controlado como se esperaba)
- `guardrail_texto_vacio_01`: correctamente derivado (error controlado como se esperaba)
- `guardrail_inyeccion_detector_01`: correctamente derivado (bloqueada por ['genero'])
- `mercado_incompleta_01`: correctamente derivado (error controlado como se esperaba)
- `mercado_turno_invalido_01`: correctamente derivado (error controlado como se esperaba)

## Determinismo

Todas las salidas fueron reproducibles.

## Limitaciones

- Los evals ejercitan los agentes directamente (matching, auditor, mercado); no cubren
  la API ni el frontend.
- La ruta de formacion queda fuera del alcance inicial.
- El agente de Mercado corre sin red: cuando el caso no inyecta una respuesta simulada,
  usa su respaldo por palabras clave, asi que no mide calidad del modelo de lenguaje real.
- Las metricas sin ejemplos suficientes se reportan como N/A.
