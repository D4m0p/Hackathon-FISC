# Empleo Joven — sistema de agentes para la inserción laboral juvenil

Hackathon FISC 2026 · Reto 3: Empleabilidad · Universidad Tecnológica de Panamá

> **Estado:** versión de trabajo. Las secciones marcadas *(en desarrollo)* se completan
> durante el evento.

## El problema

La transición del estudio al primer empleo es uno de los momentos más difíciles para los
jóvenes panameños, y el problema es de información en tres lados:

- **Jóvenes:** no saben qué habilidades pide el mercado, cómo traducir su experiencia
  informal (el negocio familiar, un voluntariado) al lenguaje de una empresa, ni qué curso
  gratuito cierra su brecha. Envían CVs de forma masiva sin respuesta.
- **Empresas:** reciben cientos de postulaciones que no encajan y a veces publican ofertas
  con requisitos discriminatorios ("buena presencia", límites de edad).
- **Centros de formación:** sus cursos no siempre llegan a quien más los necesita.

Y la geografía: una vacante en Tocumen puede ser inviable para alguien de La Chorrera por
las horas de traslado y el costo del pasaje, algo que los portales de empleo ignoran.

## La solución

Un mercado de tres lados con la mecánica de "deslizar": el joven ve vacantes y la empresa
ve candidatos anonimizados; cada uno dice sí o no. **Pero quien decide no es un modelo de
lenguaje: son solvers y reglas en código**, y una persona (el orientador) aprueba cada
decisión importante.

- Cada tarjeta explica por qué aparece: habilidades que coinciden, minutos y costo de
  traslado, y salario neto del transporte.
- Las vacantes imposibles para un joven (por distancia, presupuesto, horario o salario)
  ni siquiera se le muestran, y el sistema dice por qué.
- **Casi califica:** las vacantes donde le falta una sola cosa se le muestran aparte, con
  cuánto le falta ("le faltan B/.1.00 por semana para el pasaje") y qué hacer; si lo que
  falta es una habilidad, el curso que la cubre y que cabe en su horario y presupuesto.
- Cuando hay interés mutuo, un solver de optimización asigna respetando los cupos.
- **Pesos ajustables:** el orientador decide cuánto pesan habilidades, traslado y salario
  (con límites: ninguno puede anularse ni dominar del todo). Antes de cambiarlos puede
  simular qué propuestas entrarían y cuáles saldrían; cada cambio queda trazado con su motivo.
- El orientador aprueba; el sistema agenda la entrevista y avisa por Telegram.
- **Reacomodo:** si un joven cancela o no se presenta, si la empresa lo retira o si cierra
  la vacante, el cupo se libera y el solver propone de inmediato al siguiente candidato
  (o reubica al joven en otra vacante), siempre con aprobación del orientador. Las
  entrevistas se pueden reprogramar y cada cambio se avisa.
- Quien no tiene ninguna vacante posible recibe una ruta de cursos que cabe en su horario,
  su presupuesto y su transporte.
- Un auditor bloquea ofertas discriminatorias y mide si el resultado cambia al cambiar
  solo el nombre, el género o el corregimiento de una persona.

## Arquitectura

```mermaid
flowchart LR
    E[Empresa] -->|oferta en texto o foto| M[Inteligencia de mercado]
    M -->|vacante normalizada| AU[Auditor]
    AU -->|discriminatoria| B[(Bloqueada)]
    B -->|corrección o motivo| O
    AU -->|limpia| P[(Publicada)]

    J[Joven] -->|CV, foto o entrevista| PE[Perfil]
    PE -->|habilidades con evidencia| R[(Jóvenes)]

    P --> D{Deslizar}
    R --> D
    D -->|interés mutuo| MA[Matching<br/>flujo de costo mínimo]
    MA -->|asignaciones explicadas| AU2[Auditor<br/>contrafactuales]
    AU2 --> O[Orientador humano]
    O -->|aprueba| AC[Agenda entrevista<br/>y envía Telegram]
    O -->|rechaza con motivo| MA
    R -->|sin vacante factible| RF[Ruta de formación<br/>solver CP-SAT]

    T[(Trazas)]
    M -.-> T
    PE -.-> T
    MA -.-> T
    AU -.-> T
    RF -.-> T
    O -.-> T
```

El **orquestador** (`orquestador/flujo.py`) conecta los agentes. Se comunican con modelos
tipados (`contrato/modelos.py`) y cada decisión queda registrada en la tabla `trazas`
(qué agente, qué acción, entrada, salida y motivo).

### Agentes

| Agente | Qué hace | Cómo decide | Estado |
|---|---|---|---|
| **Inteligencia de mercado** | Normaliza ofertas a una taxonomía de habilidades y extrae tendencias | El LLM extrae; el código valida contra la taxonomía | *(en desarrollo)* |
| **Perfil** | Lee el CV (PDF, foto o texto) y hace una entrevista corta para descubrir habilidades no declaradas | El LLM solo propone; el código acepta una habilidad solo si existe en la taxonomía y su cita aparece en el texto original; la experiencia informal llega como máximo a nivel 2; sin LLM funciona con palabras clave | Listo |
| **Matching** | Filtra pares imposibles, puntúa y asigna con cupos | Reglas + OR-Tools (flujo de costo mínimo: óptimo exacto en tiempo polinomial) | Listo |
| **Ruta de formación** | Elige cursos que cierran la brecha de habilidades | OR-Tools CP-SAT con cupos, turnos, traslado y presupuesto | Listo |
| **Auditor** | Bloquea ofertas discriminatorias y hace pruebas contrafactuales de sesgo | Reglas determinísticas; el LLM solo como segunda opinión | *(en desarrollo)* |

### Requisitos mínimos del reto

| Requisito | Cómo se cumple |
|---|---|
| Arquitectura multiagente (≥3) | 5 agentes con roles distintos, coordinados por el orquestador |
| Herramientas que actúan | Escriben en SQLite, agendan entrevistas y envían mensajes por Telegram |
| Componente determinístico | Factibilidad, puntaje, asignación y ruta de cursos son código (`agentes/matching`, `agentes/formacion`) |
| Humano en el ciclo | El orientador aprueba o rechaza cada asignación (rechazar exige motivo), decide sobre ofertas bloqueadas y ajusta los pesos del puntaje después de simular su efecto |
| Explicabilidad | Cada asignación trae su desglose (habilidades, traslado, salario) y sus motivos en texto |
| Trazabilidad | Tabla `trazas`, `GET /trazas?agente=` y la historia de cada joven de punta a punta (`GET /jovenes/{id}/historia`) |
| Evals (≥15 casos) | *(en desarrollo)* en `evals/` |
| Guardrails | Límites de forma y tamaño en todo el contrato (ids sin caracteres que rompan la URL, nombres, textos y listas con tope); tokens por rol: cada actor solo toca lo suyo y las decisiones clave son del orientador; validación estricta de toda entrada; textos de más de 5000 caracteres se rechazan antes del LLM; el texto de CVs y ofertas se trata como dato, nunca como instrucción; la empresa nunca recibe datos personales |

### Decisiones de diseño

- **Los datos personales viven aparte.** `Joven` no tiene nombre, género ni edad; esos
  campos están en `DatosPersonales`. Los solvers reciben solo `Joven`, así que no pueden
  usarlos aunque quisieran.
- **El puntaje separa lo geográfico.** El corregimiento solo puede mover los componentes
  de traslado y salario neto; el de habilidades no depende del lugar. Así el Auditor puede
  distinguir una diferencia legítima (vive lejos) de un sesgo.
- **Óptimo global, no voraz.** Asignar a cada joven su mejor opción en orden puede dejar a
  alguien sin trabajo; el solver maximiza el total respetando cupos (hay una prueba que lo
  demuestra: `test_optimo_global_gana_al_voraz`).
- **Resultados reproducibles.** Los modelos se construyen siempre en el mismo orden y CP-SAT corre con semilla fija y un solo hilo.
- **Los avisos no frenan al sistema.** Los mensajes de Telegram se envían después de soltar
  el candado del orquestador; un canal lento o caído no bloquea las demás operaciones ni
  deshace la aprobación ya guardada.
- **Rendimiento.** El Matching es un flujo de costo mínimo (exacto y polinomial; antes CP-SAT,
  que con miles de pares agotaba su límite de tiempo sin solución). El solver trabaja solo con
  el puntaje numérico y la explicación se arma únicamente para los pares elegidos. Con 2000
  jóvenes y 200 vacantes, el ciclo completo de matching tarda unos 0,3 s, y la asignación
  con todos los pares posibles (5000 × 300) unos 7 s.

## Tecnologías

- **Backend:** Python 3.12+, FastAPI, Pydantic 2, SQLite.
- **Optimización:** Google OR-Tools: flujo de costo mínimo para el Matching y CP-SAT para la Ruta de formación.
- **Modelo de lenguaje:** Groq (`openai/gpt-oss-120b`), solo para extraer datos de texto e
  imágenes *(en desarrollo)*.
- **Mensajería:** API de bots de Telegram.
- **Frontend:** React + Vite *(en desarrollo)*.
- **Pruebas:** pytest.

## Fuentes de datos

- **Datos de demostración** (`scripts/demo/datos_demo.json`): **ilustrativos**. Tiempos y
  tarifas de traslado aproximados entre 8 corregimientos; cursos inspirados en la oferta de
  INADEH; personas y empresas ficticias.
- **Datos reales** *(en desarrollo)* en `datos/`: ofertas de portales panameños, catálogo de
  cursos de INADEH y tarifas de transporte, cada uno con su fuente y fecha de consulta.

## Instalación y ejecución

```bash
git clone <url-del-repositorio> && cd <carpeta>
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env            # opcional: claves de Groq y Telegram

# Datos de demostración (10 vacantes, 10 jóvenes, 8 cursos) y primera corrida del matching
.venv/bin/python scripts/semilla_demo.py --reiniciar --matching

# API en http://localhost:8010 (documentación interactiva en /docs)
.venv/bin/uvicorn api.main:app --reload --port 8010 --timeout-keep-alive 30

# Pruebas
.venv/bin/python -m pytest
```

### Credenciales de demo

La API usa tokens por rol (`Authorization: Bearer <token>`). El script de datos de
demostración crea estos, **predecibles a propósito y solo para la demo**:

| Rol | Token | Qué puede hacer |
|---|---|---|
| Orientador | `demo-orientador` (o el valor de `CLAVE_ORIENTADOR`) | Todo: matching, aprobar o rechazar, inasistencias, ofertas bloqueadas, trazas |
| Joven | `demo-j01` … `demo-j11` (`demo-j11` = Lucía, sin deslizar nada: para la demo en vivo) | Solo lo suyo: perfil, tarjetas, plan, casi califica, deslizar, cancelar, reprogramar |
| Empresa | `demo-e_super`, `demo-e_call`, `demo-e_logis`, `demo-e_resto`, `demo-e_tienda`, `demo-e_tec`, `demo-e_agencia`, `demo-e_hotel` | Solo sus vacantes: publicar, ver candidatos anonimizados, deslizar, retirar, cerrar |

Un joven nuevo que se registra con `POST /jovenes` recibe su propio token aleatorio en la
respuesta. Los tokens de empresa nuevos los emite el orientador con `POST /credenciales`.
En la base solo se guarda el hash SHA-256 de cada token. En `/docs`, el botón
**Authorize** permite probar la API con cualquiera de estos tokens.

Las claves de servicios externos son opcionales y van en `.env` (nunca en el repositorio;
ver `.env.example`):

| Variable | Para qué | Sin ella |
|---|---|---|
| `GROQ_API_KEY` | Extracción de CVs y ofertas | Mercado y Perfil no procesan texto libre |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID_DEMO` | Envío real del aviso de entrevista | El mensaje queda registrado en la base pero no se envía |
| `CLAVE_ORIENTADOR` | Token del orientador fuera de la demo | Solo existe `demo-orientador` si se cargaron los datos de demo |
| `RUTA_BASE_DATOS` | Archivo SQLite | Usa `datos_app.db` |
| `ORIGENES_PERMITIDOS` | Orígenes del frontend (CORS) | `http://localhost:5173` |
| `LIMITE_ANONIMO_POR_MINUTO` | Tope por IP para el registro y el Perfil sin token | 30 |

**Un solo proceso.** Levante uvicorn con un solo worker (como en los comandos de arriba). La
decisión del orientador es atómica en la base aunque haya varios procesos, pero el candado del
orquestador, el límite de peticiones y la caché de traslados son por proceso. Detrás de un proxy,
agregue `--proxy-headers` para que el límite use la IP real del cliente.

## API

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/perfil/preguntas` | Preguntas de la entrevista corta (público) |
| `POST` | `/perfil/cv` | CV en PDF, foto o texto → habilidades con evidencia (público, no guarda nada) |
| `POST` | `/perfil/entrevista` | Respuestas de la entrevista → habilidades con evidencia (público, no guarda nada) |
| `POST` | `/jovenes` | Registra un joven y sus datos personales |
| `GET` | `/jovenes/{id}/tarjetas` | Vacantes factibles para deslizar, con explicación |
| `GET` | `/jovenes/{id}/plan` | Ruta de formación |
| `GET` | `/jovenes/{id}/historia` | Todo lo que el sistema hizo con el joven: estado actual y qué agente decidió qué, en orden |
| `GET` | `/jovenes/{id}/casi-califica` | Vacantes donde le falta una sola cosa, con sugerencia y cursos |
| `POST` | `/ofertas` | Publica una oferta en texto libre (Mercado → Auditor) |
| `POST` | `/vacantes` | Publica una vacante estructurada (Auditor) |
| `GET` | `/vacantes/{id}/tarjetas` | Candidatos factibles, sin datos personales |
| `POST` | `/vacantes/{id}/publicar-bloqueada` | El orientador publica una oferta bloqueada, con motivo |
| `POST` | `/deslizar` | Registra un sí o un no; responde si hay interés mutuo |
| `POST` | `/matching` | Corre el matching y la ruta de formación |
| `GET` | `/asignaciones` | Filtra por `pendiente`, `aprobada`, `rechazada` o `cerrada` |
| `POST` | `/asignaciones/{joven}/{vacante}/decision` | El orientador aprueba o rechaza |
| `POST` | `/asignaciones/{joven}/{vacante}/liberar` | Cancelación, inasistencia o retiro: libera el cupo y propone reemplazo |
| `POST` | `/asignaciones/{joven}/{vacante}/reprogramar` | Mueve la entrevista al siguiente espacio libre |
| `POST` | `/vacantes/{id}/cerrar` | Cierra la vacante y reubica a los afectados |
| `GET` | `/pesos` | Pesos actuales del puntaje (público) |
| `POST` | `/pesos/simular` | Qué propuestas entrarían y saldrían con otros pesos, sin guardar nada (orientador) |
| `PUT` | `/pesos` | El orientador cambia los pesos, con motivo |
| `GET` | `/planes` | Todos los planes de formación de una vez (orientador) |
| `GET` | `/trazas` | Qué agente decidió qué, filtrable por agente |
| `GET` | `/mensajes` | Mensajes enviados o registrados |
| `GET` | `/salud` | Qué agentes están conectados |
| `GET` | `/yo` | Rol y sujeto del token |
| `POST` | `/credenciales` | El orientador emite un token de empresa, joven u orientador |

Cada respuesta trae `X-Id-Peticion`; un error inesperado responde `500` con `id_error` (el mismo
id queda en el log con la traza completa, sin exponer detalles al cliente). Errores: `429` si un
cliente sin token se pasa del límite (con `Retry-After`), `401` sin token o token inválido, `403` sin permiso para esa acción, `404` si algo
no existe, `400` si una regla del flujo no lo permite (con el motivo en `detail`), `422` si
los datos no son válidos. Públicas (sin token): `/salud`, `/habilidades`, `/cursos`,
`/traslados`, vacantes publicadas y el registro de un joven nuevo.

## Estructura

```
contrato/       modelos de datos compartidos por todos los agentes
orquestador/    flujo, almacenamiento SQLite, trazas, agenda y notificaciones
agentes/        matching/, formacion/ (y mercado/, perfil/, auditor/)
api/            API HTTP (FastAPI)
scripts/        datos de demostración y utilidades
tests/          pruebas automáticas
```

## Pruebas

275 pruebas automáticas cubren el contrato, el Matching, la Ruta de formación, el
orquestador, el agente Perfil, los pesos ajustables, el reacomodo, "casi califica", la historia por joven, los permisos por rol, la API y la historia de los datos de demostración. Además, cada restricción
de los solvers se verificó quitándola a propósito y comprobando que alguna prueba falla.

**Casos aleatorios** (Hypothesis, `tests/test_propiedades.py` y `tests/test_estados.py`):
miles de mercados, perfiles y cursos generados al azar verifican propiedades que deben
cumplirse siempre. En instancias pequeñas, el Matching y la Ruta de formación se comparan
contra una búsqueda exhaustiva de todas las combinaciones: el solver nunca pierde. Una
máquina de estados inventa recorridos completos (registrar, deslizar, matching, aprobar,
cancelar, cerrar, reprogramar, editar) y revisa las reglas del negocio después de cada
paso. Estas pruebas encontraron 6 errores que los ejemplos fijos no veían (por ejemplo,
una propuesta que seguía viva después de que la empresa cambió su respuesta a "no"); cada
uno quedó corregido y fijado en `tests/test_regresiones.py`.

**Carga y concurrencia** (`scripts/prueba_carga.py`, contra la API en ejecución): más de
1000 peticiones en ráfagas de hasta 378 simultáneas, mezclando registros, deslizamientos,
10 corridas de matching a la vez, decisiones del orientador enviadas dos veces en paralelo
entradas maliciosas (inyección de prompt, SQL, textos gigantes, datos inválidos) y acciones
sin token. Resultado: 0 errores 5xx; todas las acciones sin token rechazadas; ninguna vacante supera sus cupos, ningún joven queda con dos
asignaciones y ninguna decisión se aplica dos veces.

```bash
.venv/bin/python scripts/semilla_demo.py --reiniciar --base carga.db
RUTA_BASE_DATOS=carga.db .venv/bin/uvicorn api.main:app --port 8010 --timeout-keep-alive 30
.venv/bin/python scripts/prueba_carga.py --url http://localhost:8010 --jovenes 300
```

## Equipo

**LarpeoIntenso**
