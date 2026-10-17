# Resultados de los evals

- Estado de la corrida: **SATISFACTORIA**
- Generado por `python evals/correr.py`: 2026-10-16 22:56:45 UTC
- Commit: `eac0a63` · Python 3.14.4 · sin red (`GROQ_API_KEY` retirada)
- Casos ejecutados: **28** · cumplen: **28** · errores de evaluacion: **0**

Cada caso se ejecuto dos veces y se compararon las salidas normalizadas para verificar que sea determinista. Los casos de `naturaleza: revision_humana` se consideran correctos cuando el sistema los deriva a revision en vez de decidir solo.

## Errores de evaluacion (fallo inesperado)

Ninguno.

## Casos

| id | asunto | categoria | naturaleza | resultado | detalle |
|---|---|---|---|---|---|
| contrafactual_identidad_01 | contrafactual | contrafactual | determinista | cumple | sin hallazgos |
| contrafactual_corregimiento_01 | contrafactual | contrafactual | determinista | cumple | sin hallazgos |
| contrafactual_manipulado_01 | contrafactual | contrafactual | revision_humana | cumple | detectado ['contrafactual_desglose'] |
| detector_discrimina_01 | detector | detector | revision_humana | cumple | bloqueada por ['buena_presencia', 'edad'] |
| detector_genero_01 | detector | detector | revision_humana | cumple | bloqueada por ['genero'] |
| detector_estado_civil_01 | detector | detector | revision_humana | cumple | bloqueada por ['estado_civil'] |
| detector_foto_01 | detector | detector | revision_humana | cumple | bloqueada por ['foto_obligatoria'] |
| detector_residir_01 | detector | detector | revision_humana | cumple | bloqueada por ['residir_en'] |
| detector_limpia_01 | detector | detector | determinista | cumple | aprobada |
| detector_edad_legal_01 | detector | detector | determinista | cumple | aprobada |
| detector_menores_legal_01 | detector | detector | determinista | cumple | aprobada |
| detector_negacion_01 | detector | detector | determinista | cumple | aprobada |
| guardrail_inyeccion_01 | mercado | guardrails | determinista | cumple | vacante esperada |
| guardrail_fuera_alcance_01 | mercado | guardrails | revision_humana | cumple | error controlado como se esperaba |
| malformada_matriz_01 | contrafactual | malformadas | determinista | cumple | error controlado como se esperaba |
| malformada_vacante_01 | matching | malformadas | determinista | cumple | error controlado como se esperaba |
| matching_compatible_01 | matching | matching | determinista | cumple | asignacion esperada |
| matching_compatible_02 | matching | matching | determinista | cumple | asignacion esperada |
| matching_global_01 | matching | matching | determinista | cumple | asignacion esperada |
| mercado_completa_01 | mercado | mercado | determinista | cumple | vacante esperada |
| mercado_incompleta_01 | mercado | mercado | revision_humana | cumple | error controlado como se esperaba |
| mercado_fuera_taxonomia_01 | mercado | mercado | determinista | cumple | vacante esperada |
| restriccion_cupos_01 | matching | restricciones | determinista | cumple | propiedades respetadas |
| restriccion_disponibilidad_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_traslado_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_presupuesto_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| restriccion_salario_01 | matching | restricciones | determinista | cumple | sin asignacion, como se esperaba |
| sin_asignacion_01 | matching | sin_asignacion | determinista | cumple | sin asignacion, como se esperaba |

### Por categoria

| Clave | Casos | Cumplen |
|---|---|---|
| contrafactual | 3 | 3 |
| detector | 9 | 9 |
| guardrails | 2 | 2 |
| malformadas | 2 | 2 |
| matching | 3 | 3 |
| mercado | 3 | 3 |
| restricciones | 5 | 5 |
| sin_asignacion | 1 | 1 |

### Por asunto

| Clave | Casos | Cumplen |
|---|---|---|
| contrafactual | 4 | 4 |
| detector | 9 | 9 |
| matching | 10 | 10 |
| mercado | 5 | 5 |

## Metricas agregadas

| Metrica | Valor |
|---|---|
| Asignaciones observadas | 6 |
| Factibilidad de asignaciones | 100.0% |
| Violaciones de cupos | 0 |
| Asignaciones incompatibles con habilidades | 0 |
| Detector: precision | 100.0% (tp=5, fp=0) |
| Detector: exhaustividad | 100.0% (fn=0, tn=4) |
| Mercado: precision de habilidades (categoria mercado) | 100.0% |
| Mercado: exhaustividad de habilidades (categoria mercado) | 100.0% |
| Contrafactuales cumplidos | 4/4 |
| Guardrails cumplidos | 2/2 |
| Entradas malformadas contenidas | 2/2 |

## Errores funcionales (expectativa no cumplida)

Ninguno.

## Casos derivados a revision humana

- `contrafactual_manipulado_01`: correctamente derivado (detectado ['contrafactual_desglose'])
- `detector_discrimina_01`: correctamente derivado (bloqueada por ['buena_presencia', 'edad'])
- `detector_genero_01`: correctamente derivado (bloqueada por ['genero'])
- `detector_estado_civil_01`: correctamente derivado (bloqueada por ['estado_civil'])
- `detector_foto_01`: correctamente derivado (bloqueada por ['foto_obligatoria'])
- `detector_residir_01`: correctamente derivado (bloqueada por ['residir_en'])
- `guardrail_fuera_alcance_01`: correctamente derivado (error controlado como se esperaba)
- `mercado_incompleta_01`: correctamente derivado (error controlado como se esperaba)

## Determinismo

Todas las salidas fueron reproducibles.

## Limitaciones

- Los evals ejercitan los agentes directamente (matching, auditor, mercado); no cubren
  la API ni el frontend.
- La ruta de formacion queda fuera del alcance inicial.
- El agente de Mercado corre sin red: cuando el caso no inyecta una respuesta simulada,
  usa su respaldo por palabras clave, asi que no mide calidad del modelo de lenguaje real.
- Las metricas sin ejemplos suficientes se reportan como N/A.
