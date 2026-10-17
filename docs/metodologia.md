# Documento de metodología

**Empleo Joven — sistema de agentes para la inserción laboral juvenil**
Hackathon FISC 2026 · Reto 3: Empleabilidad · Equipo LarpeoIntenso

Este documento explica cómo está construido el sistema (arquitectura), cómo trabaja de punta a
punta (funcionamiento) y cómo se instala y se pone en marcha (despliegue). Complementa al
`README.md`, que tiene la referencia de la API y los comandos.

---

## 1. Enfoque

El reto pide un mercado de tres lados (jóvenes, empresas y centros de formación) donde los
agentes asignen, agenden y reacomoden con datos sucios y restricciones reales de transporte,
tiempo y dinero. Partimos de la regla de oro del reto: si algo se puede reemplazar con un buen
prompt, no califica. Por eso separamos dos tipos de trabajo:

- **Lo que se entiende** (leer un CV, una oferta, una nota de voz): lo hace un modelo de
  lenguaje, siempre con esquema estricto y con validación en código de lo que propone.
- **Lo que se decide** (qué es factible, cómo se puntúa, quién va a qué vacante, qué cursos
  tomar, qué oferta se bloquea): lo hace código determinístico, reproducible y probado.

Encima de eso, una persona (el **orientador**) aprueba las decisiones que afectan a alguien, y
cada decisión queda trazada con el agente que la tomó y su motivo.

---

## 2. Arquitectura

### 2.1 Capas

| Capa | Carpeta | Qué hace |
|---|---|---|
| Contrato | `contrato/` | Modelos de datos compartidos (Pydantic) con validación de forma y tamaño. Es el idioma común de todos los agentes. |
| Agentes | `agentes/` | Perfil, Inteligencia de mercado, Matching, Ruta de formación y Auditor. |
| Orquestador | `orquestador/` | Conecta los agentes, aplica las reglas del flujo, guarda en SQLite y registra trazas. |
| API | `api/` | FastAPI: permisos por rol, límites de peticiones, manejo de errores. |
| Página | `frontend/` | React + Vite: una vista por rol (joven, empresa, orientador y centro). |
| Datos | `datos/`, `scripts/demo/` | Datos reales con fuentes y datos de demostración ilustrativos. |
| Evaluación | `evals/`, `agentes/perfil/evals/`, `tests/` | Evals del reto y pruebas automáticas. |

### 2.2 Los cinco agentes

| Agente | Entrada → salida | Cómo decide |
|---|---|---|
| **Perfil** | CV (PDF, foto o texto), entrevista corta o nota de voz → habilidades con evidencia | El modelo propone habilidades con una cita; el código acepta una habilidad solo si existe en la taxonomía y la cita aparece en el texto original. La experiencia informal llega como máximo a nivel 2. Sin modelo, funciona con palabras clave. |
| **Inteligencia de mercado** | Oferta en texto libre o foto de volante → vacante normalizada; tendencias por zona | El modelo extrae campos con esquema estricto; el código valida contra la taxonomía y el contrato. Si faltan datos obligatorios, responde qué falta en lugar de inventarlo. |
| **Matching** | Jóvenes, vacantes, traslados, interés mutuo → asignaciones explicadas | Reglas de factibilidad, puntaje explicable y un **flujo de costo mínimo** (OR-Tools) que da la asignación de puntaje total máximo respetando cupos. |
| **Ruta de formación** | Joven sin vacante a su alcance, cursos → plan de cursos | Modelo de optimización (OR-Tools CP-SAT) con cupos, turnos, traslado y presupuesto. |
| **Auditor** | Vacante → aprobada o bloqueada; resultado del matching → revisión de sesgo | Solo reglas en código (sin modelo de lenguaje): patrones de discriminación con manejo de negaciones y contexto; pruebas contrafactuales recalculadas con el código real del Matching. |

### 2.3 Flujo y punto de intervención humana

```
Empresa ──oferta──▶ Mercado ──vacante──▶ Auditor ──▶ publicada / bloqueada
                                                        │            │
Joven ──CV/entrevista──▶ Perfil ──▶ registro            │      Orientador decide
                                       │                ▼
                         deslizar ◀────┴──────▶ deslizar (empresa)
                              │ interés mutuo
                              ▼
                     Matching (flujo de costo mínimo) ──▶ Auditor (contrafactuales)
                              │
                              ▼
                     ORIENTADOR aprueba / rechaza ──▶ agenda entrevista y avisa
                              │
          sin vacante a su alcance ──▶ Ruta de formación ──▶ Centro reserva cupo
```

El diagrama completo con todas las conexiones está en el `README.md` (sección "Arquitectura de
agentes").

**El humano decide en estos puntos:** aprobar o rechazar cada asignación (rechazar exige motivo),
publicar una oferta que el Auditor bloqueó (exige motivo), registrar inasistencias, cambiar los
pesos del puntaje (después de simular su efecto, con motivo) y, en el caso del centro de
formación, a quién reservarle un cupo.

### 2.4 Autonomía

El sistema no espera un clic para reaccionar:

- Al publicarse una vacante, el Auditor la revisa y, si queda publicada, el matching corre solo.
- Al haber interés mutuo, el matching corre solo y la propuesta aparece al instante (pendiente
  del orientador).
- A un joven nuevo sin ninguna vacante a su alcance se le arma su ruta de formación al
  registrarse.
- Si un joven cancela, no se presenta, la empresa lo retira o la vacante se cierra, el cupo se
  libera y el sistema propone el reemplazo (**reacomodo**).

Cada reacción queda en la tabla de trazas (por ejemplo, `auto_matching` o `reacomodar`).

### 2.5 Trazabilidad

Cada decisión se guarda con el agente, la acción, la entrada, la salida, el motivo y la fecha.
Se consultan por agente (`GET /trazas`) o por joven de punta a punta
(`GET /jovenes/{id}/historia`), con una frase del estado actual lista para mostrar.

---

## 3. Funcionamiento

### 3.1 Recorrido de un joven

1. **Registro.** Sube su CV, responde cinco preguntas sobre experiencia informal (negocio
   familiar, comida, tecnología, bodega, inglés) o graba una nota de voz. El agente Perfil
   devuelve sus habilidades, cada una con la frase que la justifica. El joven confirma, indica
   dónde vive, en qué turnos puede trabajar, cuánto puede gastar en pasaje y su salario mínimo,
   y recibe su código de acceso.
2. **Tarjetas.** Ve solo las vacantes que de verdad le sirven, de mejor a peor. Cada tarjeta dice
   por qué aparece: habilidades que coinciden, minutos y costo del traslado y salario neto del
   pasaje.
3. **Casi califica.** Ve aparte las vacantes donde le falta una sola cosa, con cuánto le falta
   ("le faltan B/.1.00 por semana para el pasaje") y, si es una habilidad, el curso que la cubre
   y que cabe en su horario y presupuesto.
4. **Match y entrevista.** Cuando joven y empresa se dicen que sí, el sistema propone la
   asignación; el orientador la aprueba y el sistema agenda la entrevista sin chocar horarios y
   envía el aviso.
5. **Ruta de formación.** Si ninguna vacante le queda a su alcance, recibe un plan de cursos y
   el centro de formación puede reservarle un cupo.

### 3.2 Factibilidad y puntaje

Un par joven–vacante es **factible** si cumple todo esto: el traslado existe y no supera los
minutos que el joven acepta; el pasaje semanal (ida y vuelta, todos los días de trabajo) cabe en
su presupuesto; tiene disponibles todos los turnos de la vacante; el salario alcanza su mínimo; y
tiene todas las habilidades obligatorias con el nivel pedido.

Para los pares factibles, el **puntaje** (de 0 a 1) combina tres componentes:

- **Habilidades:** proporción de requisitos cumplidos (las obligatorias pesan el doble).
- **Traslado:** más cerca, más puntaje.
- **Salario:** salario neto del costo de transporte.

Los pesos por defecto son 60 %, 25 % y 15 %. El orientador puede ajustarlos (cada uno entre 5 % y
80 %, sumando 100 %), simular antes qué propuestas entrarían y saldrían, y el cambio queda trazado.

**Separación clave:** el corregimiento solo puede mover los componentes de traslado y salario; el
de habilidades no depende del lugar. Esto permite al Auditor distinguir una diferencia legítima
(vive lejos) de un sesgo.

### 3.3 Asignación óptima

El Matching resuelve la asignación como un **flujo de costo mínimo**:

```
fuente ─(1)─▶ joven ─(−puntaje)─▶ vacante ─(cupos)─▶ sumidero
                │
                └──────────(0)──────────────────────▶ sumidero   (quedarse sin vacante)
```

El resultado es la asignación de **puntaje total máximo** respetando que cada joven recibe como
máximo una vacante y ninguna vacante supera sus cupos. Es exacto y de tiempo polinomial. El arco
"quedarse sin vacante" es necesario: sin él, el flujo maximizaría la cantidad de asignaciones en
vez del puntaje total.

Una primera versión usaba CP-SAT. Al medirla con miles de pares, agotaba su límite de tiempo sin
encontrar solución; por eso se cambió al flujo. Con 2000 jóvenes y 200 vacantes, el ciclo de
matching tarda unos 0,3 s; con todos los pares posibles de 5000 × 300, unos 7 s.

Asignar en orden ("a cada uno su mejor opción") puede dejar a alguien sin trabajo cuando el
óptimo coloca a todos; hay una prueba que lo demuestra (`test_optimo_global_gana_al_voraz`).

### 3.4 Ruta de formación

Para un joven sin vacante a su alcance, el agente busca las vacantes que solo le fallan por
habilidades y elige cursos que cierran esa brecha, sujeto a cupos, a que no haya dos cursos en el
mismo turno, a su horario, al traslado y a su presupuesto semanal de transporte. Minimiza costo
(matrícula más transporte) y tiempo. Si varios jóvenes compiten por un cupo escaso, va primero a
quien tiene menos opciones.

### 3.5 Auditor

- **Ofertas:** detecta género, edad (respetando que excluir a menores de edad es legal), estado
  civil, foto obligatoria, "buena presencia" y "residir en". Maneja negaciones ("no se requiere
  foto") sin dejar que una negación oculte un requisito real más adelante. Cada hallazgo trae el
  fragmento, el motivo y una sugerencia de redacción.
- **Contrafactuales:** en cada matching, mueve a cada joven a los demás corregimientos y verifica
  que el componente de habilidades no cambie. Nombre, género y edad nunca llegan al Matching:
  viven aparte, en `DatosPersonales` (garantía estructural).

### 3.6 Centros de formación

El centro ve, por curso, quiénes lo necesitan (jóvenes con el curso en su plan o a los que solo
les falta una habilidad que el curso otorga), en orden: primero quienes pueden asistir (horario y
traslado), luego a quién le abre más vacantes. Al reservar un cupo, se descuenta en una sola
operación atómica, queda la traza y se avisa al joven.

### 3.7 Cifra de impacto

`GET /impacto` cuenta, de todas las combinaciones joven–vacante, cuántas son viables y cuántas se
descartan por cada motivo. Con los datos de demostración: de 121 combinaciones, 13 son viables;
los descartes por traslado (33), pasaje (42), horario (34), salario (5) y habilidad (103) muestran
por qué un portal que ignora la geografía manda a los jóvenes a trabajos a los que no pueden llegar.

---

## 4. Datos

- **Reales** (`datos/`, consultados el 16/10/2026, cada registro con fuente, URL y fecha):
  30 ofertas de portales panameños (22 verificadas y 8 parciales), 28 cursos (INADEH, Cisco
  Networking Academy y Oracle) y una tabla de transporte de 1104 filas entre 24 corregimientos.
  Las fuentes y los criterios de verificación están en `datos/FUENTES*.md`.
- **De demostración** (`scripts/demo/datos_demo.json`): ilustrativos. 12 vacantes, 11 jóvenes y
  8 cursos pensados para que cada escena de la demo ocurra; personas y empresas ficticias.

---

## 5. Validación y calidad

| Qué | Resultado |
|---|---|
| Pruebas automáticas (pytest) | 465 |
| Evals de Matching, Auditor y Mercado (`evals/`) | 40 casos en 8 categorías, todos cumplen |
| Evals del agente Perfil (`agentes/perfil/evals/`) | 35 casos de reglas, todos cumplen |
| Casos aleatorios (Hypothesis) | El Matching y la Ruta de formación se comparan contra búsqueda exhaustiva en instancias pequeñas, con cualquier combinación válida de pesos: el solver nunca pierde |
| Máquina de estados | Recorridos aleatorios completos (registrar, deslizar, aprobar, cancelar, cerrar, reprogramar, editar), con y sin matching automático, verificando las reglas del negocio después de cada paso |
| Carga y concurrencia | Más de 1000 peticiones en ráfagas de cientos simultáneas: sin errores 5xx, sin cupos excedidos, sin decisiones aplicadas dos veces |

**Las pruebas encontraron errores reales**, todos corregidos y fijados en pruebas de regresión.
Algunos ejemplos: una propuesta seguía viva después de que la empresa cambió su respuesta a "no";
dos aprobaciones simultáneas de la misma asignación pasaban las dos; una edición de la vacante
podía dejar más personas aprobadas que cupos; la tarjeta "anónima" de un candidato podía mostrar
su nombre si este aparecía en la misma frase del CV que una habilidad.

Para comprobar que las pruebas sirven, se quitaron a propósito restricciones del código (cupos,
turnos, presupuesto, el arco "quedarse sin vacante") y se verificó que alguna prueba fallara.

---

## 6. Seguridad y privacidad

- **Roles con token** (joven, empresa, centro, orientador): cada actor solo toca lo suyo; las
  decisiones clave son del orientador. En la base solo se guarda el hash del token.
- **Anonimato:** la empresa ve habilidades y niveles, nunca nombre, género, edad, contacto ni la
  evidencia textual del CV.
- **Entradas:** límites de forma y tamaño en todo el contrato; el texto de CVs y ofertas se trata
  como dato, nunca como instrucción; límite de peticiones por minuto para quien no tiene token en
  las rutas que usan el modelo de lenguaje.
- **Concurrencia:** las operaciones que cambian el estado se ejecutan de a una; la decisión del
  orientador es atómica en la base aunque haya varios procesos; los avisos se envían fuera del
  candado para que un canal lento no frene al sistema.
- **Errores:** un error inesperado responde con un código para rastrearlo en el registro, sin
  exponer detalles internos.

---

## 7. Despliegue

### 7.1 Requisitos

- Python 3.12 o superior, Node.js 18 o superior y npm.
- Opcional: clave de Groq (`GROQ_API_KEY`) para que Perfil y Mercado usen el modelo de lenguaje
  (sin ella, funcionan con palabras clave); token de un bot de Telegram para el envío real de
  avisos.

### 7.2 Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm ci && cd ..
cp .env.example .env        # opcional: claves de Groq y Telegram
```

### 7.3 Puesta en marcha

**Con un solo comando** (carga los datos de demostración, levanta la API en el puerto 8010 y la
página en el 5173; Ctrl+C apaga todo):

```bash
scripts/demo.sh
```

**Paso a paso:**

```bash
.venv/bin/python scripts/semilla_demo.py --reiniciar --matching
.venv/bin/uvicorn api.main:app --port 8010 --timeout-keep-alive 30
cd frontend && npm run dev
```

Accesos de demostración: orientador `demo-orientador`, joven para deslizar en vivo `demo-j11`,
empresa `demo-e_super`, centro de formación `demo-inadeh`. La documentación interactiva de la API
está en `http://localhost:8010/docs`.

### 7.4 Variables de entorno

| Variable | Para qué | Por defecto |
|---|---|---|
| `RUTA_BASE_DATOS` | Archivo SQLite | `datos_app.db` |
| `GROQ_API_KEY` | Modelo de lenguaje para Perfil y Mercado | Sin modelo: palabras clave |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID_DEMO` | Envío real de avisos; si el envío al joven falla, el aviso va al chat de la demo | El aviso queda registrado sin enviarse |
| `CLAVE_ORIENTADOR` | Token del orientador fuera de la demo | — |
| `ORIGENES_PERMITIDOS` | Orígenes de la página (CORS) | `http://localhost:5173` |
| `LIMITE_ANONIMO_POR_MINUTO` | Tope por IP sin token | 30 |

### 7.5 Consideraciones

- Levantar la API con **un solo proceso**: la decisión del orientador es atómica entre procesos,
  pero el límite de peticiones y algunas cachés son por proceso.
- Detrás de un proxy, usar `--proxy-headers` para que el límite use la IP real del cliente.
- La base es SQLite en modo WAL; para la demo basta un archivo local.

---

## 8. Limitaciones y trabajo futuro

- Los tokens no vencen; el límite de peticiones es por proceso.
- Los datos de demostración son ilustrativos; los reales cubren 30 ofertas y 24 corregimientos.
  Con pocas vacantes, las tendencias del mercado son orientativas.
- Un bot de Telegram solo puede escribir a quien ya le habló; en un despliegue real haría falta
  que el joven inicie la conversación con el bot al registrarse.
- **Trabajo futuro:** un agente de Postulación que arme un CV por vacante usando solo evidencia
  real del joven (validada igual que en Perfil) y envíe la lista corta a la empresa; límite de
  deslizamientos por día para que cada "sí" tenga más valor; alianzas con centros de formación
  como puerta de entrada a las empresas.
