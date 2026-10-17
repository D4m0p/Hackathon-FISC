# Bitácora de uso de asistentes de programación de IA

**Proyecto:** Empleo Joven — sistema multiagente para la inserción laboral juvenil.
**Evento:** Hackathon FISC 2026, Reto 3 (Empleabilidad), Universidad Tecnológica de Panamá.
**Equipo:** LarpeoIntenso.
**Días de trabajo documentados:** 2026-10-16 y 2026-10-17 (según las fechas de los commits del repositorio).

Este documento registra el uso de **asistentes de programación de IA** durante el desarrollo y el
estado verificable del proyecto. Se apoya en la evidencia del repositorio: historial de Git, código,
pruebas automáticas, evaluaciones y los documentos de `datos/` y `evals/`. Al final se enumeran los
datos que solo el equipo puede confirmar; no se incluyen suposiciones.

> **Estado:** versión final de la entrega (17-10-2026), revisada por el equipo.

---

## 1. Objetivo y alcance del proyecto

El proyecto aborda el problema de información de la transición al primer empleo en Panamá, en tres
frentes: los jóvenes no saben qué pide el mercado ni cómo traducir su experiencia informal; las
empresas reciben postulaciones que no encajan; y la geografía (tiempos y costos de traslado) hace
inviables vacantes que los portales muestran igual.

La solución es un mercado de tres lados tipo «deslizar» donde **la decisión la toma código
determinístico** (matching, ruta de cursos, factibilidad de traslado y auditoría) y una persona (el
orientador) aprueba cada decisión importante. Un modelo de lenguaje participa **solo** para extraer
datos de texto o imagen y para redactar; nunca decide. Los cinco agentes (Inteligencia de mercado,
Perfil, Matching, Ruta de formación y Auditor) se comunican con modelos tipados de `contrato/` y
cada decisión queda en la tabla `trazas`.

**Alcance de este documento:** el uso de asistentes de programación de IA y el resultado verificable
del desarrollo. El detalle del método técnico se reserva para `docs/metodologia.md`.

## 2. Organización del equipo y uso de asistentes de programación de IA

El equipo (tres integrantes) trabajó con asistentes de programación de IA como apoyo. Antes de
programar se acordaron reglas comunes, que quedaron en los documentos de coordinación del equipo
—archivos internos que, por decisión del propio equipo, **no** se copian al repositorio de
entrega—:

- Cada cambio se sube **a nombre de la persona** que lo hace. No se admiten firmas, atribuciones ni
  marcas de agua de los asistentes (líneas de coautoría, frases que atribuyan la autoría del código a
  un asistente, enlaces a herramientas, emojis de robot o nombres de herramientas o modelos) en commits, código, comentarios,
  documentación ni nombres de archivo.
- Antes de cada envío (`push`) se comprueba, con una búsqueda automática sobre los archivos
  versionados y los mensajes de commit, que no queden esas marcas. Esa verificación es una
  herramienta interna del equipo y no forma parte del repositorio de entrega.
- El asistente **no** hace commits ni `push`: eso lo decide cada integrante.
- Un cambio no se considera terminado hasta que pasan las pruebas automáticas.
- Para reducir conflictos, cada integrante es responsable de carpetas concretas.

Esta bitácora no inventa sesiones, indicaciones dadas al asistente ni porcentajes de contribución.
Describe lo que el repositorio permite comprobar; lo que solo el equipo conoce queda en la sección 11.

## 2.1 Herramientas usadas y para qué

| Quién | Herramienta | Para qué se usó |
|---|---|---|
| A (núcleo) | Asistente de programación de IA de línea de comandos | Diseñar y programar el contrato, el orquestador, Matching, Ruta de formación y la API; escribir pruebas (incluidas las de casos aleatorios) y la prueba de carga; revisar el trabajo de los demás y buscar errores. |
| B (Perfil y frontend) | Asistente de programación de IA de línea de comandos | Agente Perfil (CV, entrevista, voz, foto), toda la página React, la app instalable para teléfonos y la revisión de los entregables contra el reglamento. |
| C (Mercado, Auditor, datos) | OpenCode con modelos gratuitos | Detector de discriminación, agente de Mercado, contrafactuales, evaluaciones (`evals/`), búsqueda y documentación de fuentes de datos, y documentos. |
| El producto (en ejecución) | Groq, modelo `openai/gpt-oss-120b` | Solo extraer datos de CV, ofertas, voz e imágenes, y redactar. Nunca decide: si falla o no hay clave, hay un respaldo por reglas. |

**Cómo se validó lo que propuso cada asistente.** Nada se aceptó sin pruebas: cada cambio se
subió solo con la suite de `pytest` en verde. Los errores que los asistentes no vieron los
encontraron las pruebas de casos aleatorios (Hypothesis), la prueba de carga y la revisión cruzada
entre integrantes, que quedó por escrito en un canal interno de avisos. Ejemplos de propuestas
corregidas o descartadas: el solver CP-SAT del matching (se reemplazó por flujo de costo mínimo
cuando falló con miles de pares), la evidencia textual del CV que llegaba a la empresa (fuga de
privacidad, se corrigió con pruebas) y una prueba de carga que fallaba por una carrera de conexiones
del cliente, no del servidor.

## 3. Reparto de áreas de trabajo

La responsabilidad se repartió por carpetas para que cada integrante pudiera avanzar sin pisar el
trabajo de los demás. La tabla resume el reparto verificado en el repositorio.

| Área | Responsabilidad | Carpetas principales |
|---|---|---|
| Núcleo | Contrato compartido, orquestador, Matching, Ruta de formación, API y scripts | `contrato/`, `orquestador/`, `api/`, `agentes/matching/`, `agentes/formacion/`, `scripts/`, `README.md` |
| Perfil y experiencia | Agente Perfil y frontend | `agentes/perfil/`, `frontend/` |
| Mercado, Auditor y evidencia | Agente de Mercado, Auditor, datos con fuentes, evaluaciones y documentos | `agentes/mercado/`, `agentes/auditor/`, `datos/`, `evals/`, `docs/` |

El historial de Git conserva, commit por commit, a quién corresponde cada cambio; por eso no se
atribuye a una sola persona el trabajo colectivo.

## 4. Etapas de desarrollo y actividades documentadas

La reconstrucción se basa en las fechas y los mensajes de los commits del repositorio (127 al cierre).

**Día 2026-10-16 — base y núcleo decisorio**

1. Se crea el repositorio con las utilidades de aviso al equipo y `.gitignore` (`6a558ae`), el
   contrato de modelos compartidos y el esqueleto de paquetes con pruebas (`b336cf6`), y los
   documentos de tareas y acuerdos (`2d153a2`, `99bd4d5`). El contrato se congela temprano; después
   solo se le agregan **campos opcionales**.
2. Se implementan las piezas que deciden con código: Matching con factibilidad y asignación con
   cupos (`ff67b02`), Ruta de formación con restricciones (`d6eb887`), el orquestador con almacén
   SQLite, trazas y aviso por Telegram (`5b09d4c`), y la API HTTP (`24cde02`).
3. Se cargan los datos de demostración, el catálogo de habilidades y el script de siembra
   (`6626064`), y se redacta el README (`97a9770`, `f353632`).
4. Se agregan el reacomodo de asignaciones (`21edbdd`), «casi califica» (`71d78e4`), la historia por
   joven (`154a5d4`), los pesos ajustables con simulación (`54a32fb`, `6bf4332` es del área de
   frontend) y los roles y permisos por token (`babf90d`).
5. El área de Perfil entrega el agente que lee el CV y hace la entrevista (`72084b8`) y el área de
   frontend el esqueleto de la página con las vistas por rol (`6bf4332` y siguientes).
6. El área de Mercado y Auditor entrega el detector de ofertas discriminatorias (`edd4eba`),
   corrige tres casos acordados con el equipo (`d0243be`), y suma el agente de Mercado, los
   contrafactuales y las evaluaciones (`8f51fbb`), junto con los datos de investigación y las
   muestras (`9ce236a`).
7. Se optimiza el Matching (`f915324`) y se endurece la API y la concurrencia (`fb97fcf`,
   `1f12156`, `499b436`).

**Día 2026-10-17 — integración, datos y pulido**

8. El área de datos amplía la tabla de transporte (`94372bc`) y corrige las coincidencias en zonas
   ambiguas (`1c578ea`), y agrega las ubicaciones de los corregimientos desde OpenStreetMap
   (`504e9c0`).
9. El área de Perfil y frontend agrega la entrada por nota de voz y foto de volante (`8dcbb06`) y el
   rediseño de la página (`0c0ee6f`, `17dad2f`).
10. El núcleo agrega los centros de formación como tercer actor (`6ceb048`), la cifra de impacto
    (`84022b9`), el matching automático al publicar, registrar o haber interés mutuo (`2942781`) y el
    límite de peticiones para anónimos (`c1b257b`).
11. Se atienden avisos internos del equipo y se limpian los ya resueltos (`5f52eab`, `e5fe6df`).

## 5. Evolución técnica comprobable

- **Matching:** pasó de CP-SAT a un **flujo de costo mínimo** (`f915324`). El motivo queda en el
  README: con miles de pares el solver de CP-SAT agotaba su límite de tiempo sin solución; el flujo
  de costo mínimo es exacto y polinomial.
- **Contrato:** a lo largo del evento solo se **agregaron campos opcionales** (por ejemplo
  `motivo_orientador` y `entrevista` en `2a8e7d1`; `vigente`, `tipo_cierre` y `motivo_cierre` en
  `c5417e5`; los modelos nuevos `Incumplimiento` y `CasiCalifica` en `cedae65`; `Pesos` en
  `4220791`; y los límites de forma y tamaño en `7055663`), sin renombrar ni borrar campos ya
  existentes.
- **Autonomía:** el sistema pasó a correr el matching solo, al publicar una vacante, registrar un
  joven o detectar interés mutuo (`2942781`), dejando siempre la aprobación al orientador.
- **Datos:** la tabla de transporte creció en varias rondas (de 15 a 20, a 21 y a 24 corregimientos),
  como deja constancia `datos/FUENTES_TRANSPORTE.md`.
- **Evaluaciones:** los casos pasaron de un bloque inicial a **40 casos** distribuidos por asunto
  (`8f51fbb`, `9ce236a`).

## 6. Preparación de datos y fuentes consultadas

El trabajo de datos buscó que cada dato verificable tuviera **fuente y fecha**. La fecha de consulta
de las fuentes de ofertas y cursos es **2026-10-16**; la de las ubicaciones de corregimientos,
**2026-10-17**.

- **Ofertas (`datos/ofertas_empleo.csv`):** 30 ofertas reales de portales panameños, con URL
  individual, empresa, ubicación, jornada, salario, experiencia, educación y requisitos. Los estados
  de verificación (verificada / parcial / pendiente) y los portales utilizados o descartados están en
  `datos/FUENTES_OFERTAS.md`.
- **Cursos (`datos/cursos.csv`):** 28 cursos y recursos gratuitos o de bajo costo de INADEH, Cisco
  Networking Academy y Oracle, con su ficha y estado. El detalle y las correcciones de la auditoría
  están en `datos/FUENTES.md`.
- **Transporte (`datos/transporte.csv`):** 24 corregimientos de Panamá, San Miguelito, La Chorrera y
  Arraiján, en 1 104 filas (552 pares dirigidos × dos franjas horarias). Las **tarifas** se respaldan
  en fuentes oficiales (MiBus, Metro); los **tiempos** son estimaciones del equipo, marcadas como
  tales. Los pares sin evidencia quedan `desconocido`. El método está en
  `datos/FUENTES_TRANSPORTE.md`.
- **Ubicaciones (`datos/corregimientos.csv`):** 21 puntos, uno por corregimiento, obtenidos de
  OpenStreetMap vía Nominatim, con su elemento OSM y fecha. El método y los límites están en
  `datos/FUENTES_CORREGIMIENTOS.md`.

### 6.1 Los CSV de investigación no son convertibles al contrato (hallazgo)

`datos/normalizar_demo.py` intenta convertir `datos/ofertas_empleo.csv` y `datos/cursos.csv` a los
modelos `Vacante` y `Curso` del contrato. El resultado actual es **0 de 30 ofertas y 0 de 28 cursos
convertidos**; los 58 registros quedan registrados, con su motivo y su URL de origen, en
`datos/demo/exclusiones.json`. No es un fallo del conversor: **a todos los registros les falta al
menos un campo obligatorio del modelo**, y el conversor no los rellena con valores inventados ni con
los valores por defecto del modelo.

Motivos, verificados en los datos:

- **Ofertas:** la fuente trae el **nombre** de la empresa (no un identificador), **provincia o
  ubicación textual** («Ciudad Panamá») y no un corregimiento, la **jornada** como texto («Tiempo
  completo») y no los turnos del contrato, y el **salario** como texto o rango, sin periodo
  confirmado. Faltan `empresa_id`, `corregimiento`, `turnos` y `salario_mensual`.
- **Cursos:** las columnas `corregimiento`, `turnos`, `sesiones_por_semana`, `semanas` y
  `cupos_disponibles` están **vacías** en los 28 registros, y las habilidades vienen como códigos
  **sin nivel**, mientras el modelo exige nivel 1–3.

Estos huecos ya estaban advertidos en `datos/FUENTES_OFERTAS.md` y `datos/FUENTES.md`. La decisión de
proyecto fue **excluir antes que inventar**: rellenarlos exigiría fabricar datos.

### 6.2 El mecanismo de demostración que sí funciona

La excepción anterior es solo sobre los CSV de investigación. El sistema cuenta con mecanismos de
demostración **completos y probados**, separados de esos CSV:

- **Demo ilustrativa** (`scripts/demo/datos_demo.json`): empresas, personas, cursos y traslados
  ficticios, cargados por `scripts/semilla_demo.py`. Es la que alimenta la página con un solo comando
  (`scripts/demo.sh`).
- **Muestra sintética** (`datos/demo_muestra/datos_muestra.json`): conjunto aparte, **rotulado como
  ficticio**, cargado con `datos/cargar_muestra.py` (reutiliza las funciones de siembra sin modificar
  `scripts/`). Recorre el flujo completo: publicar vacantes, registrar jóvenes, deslizar, correr el
  matching y generar un plan de formación.
- **Referencia real de transporte** (`datos/transporte.csv`), que se puede **complementar** con la
  demo sin reemplazarla ni inventar datos, mediante `datos/cargar_transporte.py` y
  `datos/sembrar_transporte.py`.

**Conclusión de esta sección:** la conversión directa de `ofertas_empleo.csv` y `cursos.csv` a los
agentes **no está hecha y no se presenta como terminada**. Los CSV se conservan intactos como
referencia verificable; el flujo que sí funciona es el de la demo y la muestra sintética descritos
arriba.

## 7. Decisiones técnicas, problemas y justificaciones

- **El código decide; el modelo de lenguaje no.** Matching, ruta de cursos, factibilidad de traslado
  y auditoría son determinísticos. El modelo de lenguaje solo extrae datos y redacta, sobre esquema
  estricto validado antes de usarse.
- **Datos personales separados.** `Joven` no contiene nombre, género ni edad; viven en
  `DatosPersonales`. Los solvers reciben solo `Joven`, y la empresa nunca ve la evidencia textual del
  CV (que puede traer datos personales). Hay pruebas que lo verifican.
- **Lo geográfico se separa del resto del puntaje.** El corregimiento solo puede mover los
  componentes de traslado y salario neto; el de habilidades no depende del lugar. Así el Auditor
  puede distinguir una diferencia legítima (vivir lejos) de un sesgo.
- **Zonas ambiguas no se traducen.** `san_miguelito` es un **distrito** (nueve corregimientos), no un
  punto; no se traduce a un corregimiento para no presentar una ubicación genérica como exacta. El
  matching lo trata como `sin_datos`. La decisión y su justificación están en
  `datos/FUENTES_TRANSPORTE.md`.
- **Datos ausentes no se inventan.** Los pares de transporte sin evidencia quedan `desconocido` y los
  registros de los CSV sin campos obligatorios se excluyen, en ambos casos con constancia.
- **Correcciones de auditoría acordadas.** Tres casos del detector se corrigieron con acuerdo del
  equipo (por ejemplo, una negación ya no oculta un requisito real; excluir a menores de edad es
  legal), y quedaron fijados en pruebas. El detalle está en `AVISOS.md` (documento interno).

## 8. Pruebas y evaluaciones ejecutadas

**Pruebas automáticas (pytest).** Al cierre se recolectan y pasan **487 pruebas**
(`python -m pytest`; Python 3.14). Cubren contrato, matching, ruta de formación, orquestador,
perfil, mercado, auditor, pesos, reacomodo, «casi califica», historia por joven, permisos por rol,
API, fotos, ubicaciones, transporte, datos de demo y muestra sintética.

**Casos aleatorios (Hypothesis).** `tests/test_propiedades.py` y `tests/test_estados.py` generan
miles de mercados y recorridos al azar; en instancias pequeñas se comparan contra búsqueda
exhaustiva. Encontraron errores que los ejemplos fijos no veían; cada uno quedó corregido y fijado
en `tests/test_regresiones.py`.

**Evaluaciones (`evals/`).** 40 casos, corrida **SATISFACTORIA** sin red y sin clave de modelo:
factibilidad de asignaciones 100 %, 0 violaciones de cupos, precisión y exhaustividad del detector
100 %, contrafactuales y guardrails cumplidos.

**Carga y concurrencia.** `scripts/prueba_carga.py`: más de 1000 peticiones en ráfagas de cientos de
simultáneas, con 0 errores 5xx, todas las acciones sin token rechazadas, ninguna vacante por encima
de sus cupos y ninguna decisión aplicada dos veces.

## 9. Estado final del proyecto

| Componente | Estado |
|---|---|
| Contrato de datos | Implementado; ampliaciones solo opcionales |
| Matching (factibilidad, puntaje, cupos, viajes estimados por distancia) | Implementado y probado |
| Ruta de formación y centros de formación con reservas | Implementado y probado |
| Orquestador, trazas, reacomodo, matching automático | Implementado y probado |
| API, permisos por rol y límites para anónimos | Implementada y probada |
| Agente Perfil (texto, PDF, voz, foto) | Implementado y probado |
| Agente de Mercado y tendencias | Implementado y probado |
| Auditor (detector y contrafactuales) | Implementado y probado |
| Frontend por rol, app instalable para teléfonos, fotos y logos | Implementado |
| Datos con fuentes (`datos/`) | Preparados y documentados |
| Evaluaciones (`evals/`) | 40 casos; reporte satisfactorio |
| Documentos de entrega (`README.md`, `docs/`) | Terminados |
| Video demostrativo | Grabado de la aplicación real, sin voz (`docs/video_demo.webm`) |
| Integración directa de los CSV de investigación con los agentes | **No realizada** (ver sección 6) |

## 10. Lo que queda fuera de esta entrega

1. Convertir las ofertas y cursos reales a los agentes requiere fuentes con los campos obligatorios
   (corregimiento, turnos, salario mensual, cupos); hoy no es posible sin inventar datos.
2. Medir la calidad de la extracción del LLM con más casos reales (hoy se evalúa sobre todo la parte
   determinística, que es la que decide).

## 11. Límites de esta bitácora

No se estiman porcentajes de código escrito con o sin asistente ni se reconstruyen indicaciones
concretas: el historial de Git conserva, commit por commit, quién subió cada cambio.
