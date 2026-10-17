# Fuentes y método de la tabla de transporte (`datos/transporte.csv`)

Fecha de consulta de las fuentes oficiales: **2026-10-16**.
Generado por `datos/construir_transporte.py` (determinístico); cargado por
`datos/cargar_transporte.py`.

## Qué es y qué no es

Esta tabla reúne **21 corregimientos** de los distritos de Panamá, San Miguelito y Panamá
Oeste (La Chorrera y Arraiján) con un tiempo y una tarifa por par **dirigido**
(origen → destino), en hora pico y hora valle.

- **Las tarifas** se derivan de las tarifas oficiales de MiBus y del Metro (ver abajo).
- **Los tiempos son estimaciones del equipo** (`tipo_dato = estimado`). Ni MiBus ni el
  Metro publican tiempos entre corregimientos: sus mapas de rutas son imágenes y el
  listado de rutas es dinámico. Por eso **no hay tiempos oficiales por par** y esta tabla
  **no** debe presentarse como un dato oficial de tiempos ni declarar cobertura completa.
- **Los pares sin datos verificables** quedan como `desconocido` (`tipo_dato = desconocido`,
  `tiempo_min` vacío). El cargador los omite, de modo que el matching usa su mecanismo
  `sin_datos`. No se inventan paradas, conexiones ni tiempos para completarlos.

No sustituye a `scripts/demo/datos_demo.json` (datos de la demo) ni a
`datos/demo_muestra/datos_muestra.json` (muestra sintética). Es un conjunto de referencia
aparte y rotulado.

## Fuentes oficiales consultadas

| Proveedor | Fuente | URL | Estado |
|---|---|---|---|
| MiBus | Guía del usuario (tarifas) | https://www.mibus.com.pa/guia-del-usuario/ | Accesible. Tarifas: corredor B/. 0.75; troncal B/. 0.25; transbordo troncal→corredor B/. 0.50; escolar troncal B/. 0.10 |
| MiBus | Preguntas frecuentes (transbordos) | https://www.mibus.com.pa/preguntas-frecuentes/ | Accesible. Transbordos: 150 min totales, 2 gratis, ≤40 min entre tramos, mismo sentido |
| MiBus | Mapas/estructura de rutas | https://www.mibus.com.pa/red-de-rutas/ · https://www.mibus.com.pa/mapa-de-rutas/ | Accesibles pero **dinámicos** (no exponen rutas ni tiempos en el HTML) |
| Metro de Panamá | Tarifa del Metro | https://elmetrodepanama.com/tarifa-del-metro/ | Accesible. Tarifa B/. 0.35 (estudiante B/. 0.17) |
| Metro de Panamá | Parámetros de operación | https://elmetrodepanama.com/parametros/ | Accesible. Albrook–San Isidro 28:30 min; velocidad comercial 35 km/h; frecuencia pico 3:20 min |
| MiAmbiente / cartografía oficial | División Política de Panamá 2024 (shapefile de corregimientos) | https://geoportal.miambiente.gob.pa/server/rest/services/Hosted/Division_Politica_Panama/FeatureServer/2 | Accesible. Usado para **verificar los nombres y los distritos** de las 21 zonas |
| INEC | División política por distritos y corregimientos | https://www.inec.gob.pa/mapa/Default2.aspx?ID_IDIOMA=1&ID_PROVINCIA=8&ID_TIPO=5 | Accesible (índice de la división política) |
| IGN Tommy Guardia | División política administrativa (2024/2025) | https://ignpanama.anati.gob.pa/index.php/divisionpolitica-administrativa | Accesible. Límites oficiales (escala 1:25 000) de provincias, distritos y corregimientos |
| MUPA / Municipio de Panamá | Informe de zonificación del corregimiento de San Francisco (2025) | https://dpu.mupa.gob.pa/wp-content/uploads/2025/05/080525_INFORME-PARA-CAMBIO-DE-ZONIFICACION_SF-WEB.pdf | Accesible. Confirma que San Francisco es corregimiento del distrito de Panamá y sus límites (Bella Vista, Parque Lefevre, Pueblo Nuevo y la Bahía) |
| OpenStreetMap (vía Mapcarta) | Ubicación de la estación Fernández de Córdoba (L1) dentro del corregimiento de San Francisco | https://mapcarta.com/es/N2694590414 | Accesible. **Fuente secundaria**; solo se usa para ubicar el nodo de acceso de San Francisco |
| ATTT | Portal institucional | https://transito.gob.pa/ | **No accesible** en la consulta (tiempo de espera agotado). No se usó |

Fuente de terceros usada solo como referencia de tarifa Metro L1+L2 (marcada parcial en
la tabla): https://www.expatfocus.com/panama/guide/panama-buses-and-trams

## Verificación de nombres (hallazgos)

Los nombres y la pertenencia a distrito se verificaron contra la **División Política de
Panamá 2024** (cartografía oficial del geoportal del MiAmbiente). Hallazgos:

1. **"Omar Torrijos Herrera" (San Miguelito):** la cartografía oficial de 2024 lo denomina
   **"Omar Torrijos"** (sin "Herrera"). Se usa el nombre oficial **"Omar Torrijos"** (mismo
   sector; no es un cambio de área).
2. **"Calidonia" (Panamá):** la denominación oficial completa es **"Calidonia o La
   Exposición"**. Se conserva "Calidonia", que es el uso común, y se deja constancia aquí.
3. **Distrito de Panamá:** los 9 corregimientos propuestos existen (Ancón, Bella Vista,
   Calidonia, Betania, San Francisco, Juan Díaz, Tocumen, 24 de Diciembre, Las Cumbres).
   San Francisco está confirmado como corregimiento del distrito de Panamá por el informe
   de zonificación de la MUPA (2025): limita con Bella Vista, Parque Lefevre, Pueblo Nuevo
   y la Bahía de Panamá.
4. **San Miguelito:** el distrito tiene 9 corregimientos; los 6 propuestos existen (Amelia
   Denis de Icaza, Belisario Porras, José Domingo Espinar, Rufina Alfaro, Belisario Frías,
   Omar Torrijos).
5. **La Chorrera:** Barrio Balboa, Barrio Colón y Guadalupe existen (el distrito tiene 18
   corregimientos; la ciudad de La Chorrera la forman Barrio Balboa y Barrio Colón).
6. **Arraiján:** Arraiján (cabecera), Vista Alegre y Burunga existen (el distrito tiene 9
   corregimientos).

**Cambios respecto a la tabla anterior de 15 zonas:** se retiran Parque Lefevre, Río Abajo
y Ernesto Córdoba Campos (no estaban en la selección) y se reemplaza la zona
`la_chorrera` por `barrio_colon` y `barrio_balboa`. Si se integra con la demo, que usa el
identificador `la_chorrera`, hay que mapearlo (Barrio Colón/Barrio Balboa son la ciudad de
La Chorrera).

**Cambio respecto a la tabla anterior de 20 zonas:** se **agrega San Francisco** (de 20 a 21
zonas). Las 20 zonas previas no se renombran ni se eliminan; San Francisco se usa con su
identificador `san_francisco`, que **es exactamente el que emplea la demo** (no necesita
alias).

## Compatibilidad con la demo y los identificadores antiguos

Los datos de demostración (`scripts/demo/datos_demo.json` y
`datos/demo_muestra/datos_muestra.json`) usan sus propios corregimientos. El cargador
`datos/cargar_transporte.py` los clasifica (`cobertura()`, y `--cobertura` en la CLI):

| Id de la demo | Situación | Cómo se resuelve |
|---|---|---|
| `arraijan`, `bella_vista`, `betania`, `juan_diaz`, `san_francisco`, `tocumen` | **cubiertos** | Existen tal cual en la tabla |
| `la_chorrera` | **alias** | Se traduce a `barrio_colon` (la ciudad de La Chorrera = Barrios Colón y Balboa) |
| `san_miguelito` | **faltante** | En la tabla es un **distrito** (6 corregimientos), no un corregimiento; queda en `sin_datos` |

Para conectar sin tocar agentes ni matching, `cargar_para_demo()` (o `--para-demo`) devuelve
los traslados con los alias aplicados: mantiene los ids de la tabla y añade las variantes con
el id de la demo, de modo que un joven en `la_chorrera` encuentra su par. `san_francisco` ya
es una zona de la tabla, así que no necesita alias. El único id **faltante** (`san_miguelito`,
que es un distrito y no un corregimiento) **no se inventa**: el matching, sin cambios, lo
trata como `sin_datos`.

La demo estándar **no se ve afectada** porque carga sus traslados desde `datos_demo.json`
(no desde esta tabla). La incompatibilidad solo aparecería si se reemplazaran esos traslados
por los de `transporte.csv`; para ese caso, usar `cargar_para_demo()`.

### Integración complementaria (recomendada)

La forma de usar esta tabla con la demo **sin degradar sus asignaciones** es **complementar**,
nunca reemplazar. Al reemplazar, la demo pierde asignaciones por los ids que la tabla no cubre
(`san_miguelito`); al complementar, se mantienen las 5 asignaciones originales y se agregan
**397 pares nuevos** (total **425**, sin duplicados). La integración tampoco inventa datos para
`san_miguelito` ni cambia su tratamiento.

- `datos/cargar_transporte.py::cargar_en(almacen, complementar=True)` combina los traslados
  que ya tenga el almacén con los de `cargar_para_demo()` usando `(origen, destino)` como
  clave. Es **determinista** (orden por clave) e **idempotente** (repetirlo no cambia nada).
- **Prioridad:** si un par ya existe en el almacén (p. ej. los 28 traslados curados de la
  demo), se **conserva el original**; la tabla solo aporta pares nuevos.
- `datos/sembrar_transporte.py` aplica esto tras sembrar la demo, reutilizando
  `scripts/semilla_demo.py` sin modificarlo (mismo patrón que `datos/cargar_muestra.py`):
  ```bash
  .venv/bin/python datos/sembrar_transporte.py --base datos_app.db --reiniciar --matching
  ```
  Alternativa sin código nuevo (orientador), para la base ya sembrada:
  ```bash
  curl -X POST $API/traslados -H "Authorization: Bearer demo-orientador" \
    -d "$(python datos/cargar_transporte.py --para-demo --franja valle)"
  ```
- **Limitaciones:** la integración no inventa datos para `san_miguelito` (en la tabla es un
  distrito, no un corregimiento; sigue con sus traslados de la demo o en `sin_datos`); los
  pares nuevos son **estimados** (no oficiales); no cambia el matching ni el puntaje.

## Estados de verificación

- **verificada**: el nombre y el distrito constan en la cartografía oficial; las tarifas
  de MiBus y Metro y las reglas de transbordo constan en fuentes oficiales.
- **estimada**: cálculo del equipo. Aplica a **todos** los `tiempo_min` calculables.
- **desconocida**: no hay evidencia de un nodo troncal que sirva la zona. Aplica a los
  pares que involucran a **Omar Torrijos**.
- **pendiente**: dato no confirmado (ver "Cobertura pendiente").

**La existencia de una ficha o de una ruta no implica que sus tiempos estén verificados.**
Cada columna se respalda por separado.

## Método de estimación de tiempos (no oficial)

El modelo está en `datos/construir_transporte.py`. Resumen:

1. A cada corregimiento se le asigna un **nodo de acceso** real (una estación del Metro o
   una zona paga/parada de MiBus) y un **tiempo de acceso** estimado desde el
   corregimiento al nodo.
2. Los nodos se conectan en un grafo:
   - **Metro Línea 1** y **Línea 2**: cada segmento cuesta `28.5 min / 13 ≈ 2.19 min`
     (parámetro oficial del Metro); el transbordo L1↔L2 en San Miguelito suma **7 min**.
   - **Corredores de bus**: los tramos al oeste (Arraiján, La Chorrera) y al norte
     (Chilibre) usan tiempos estimados; el transbordo bus↔Metro suma **8 min**.
3. El tiempo del par es `acceso_origen + ruta_más_corta + acceso_destino`.
4. La **hora pico** multiplica el tiempo valle por **1.3** (supuesto del equipo).
5. Si un corregimiento **no tiene nodo** (ver abajo), todos sus pares quedan `desconocido`.

Todas las constantes marcadas como estimadas son supuestos documentados aquí y
centralizados en el generador; no provienen de una fuente oficial.

### Asignación de nodos (estimada)

| Corregimiento | Distrito | Nodo de acceso |
|---|---|---|
| Ancón | Panamá | Albrook |
| Bella Vista | Panamá | Vía Argentina |
| Calidonia | Panamá | 5 de Mayo |
| Betania | Panamá | Fernández de Córdoba |
| San Francisco | Panamá | Fernández de Córdoba (L1) |
| Juan Díaz | Panamá | Villa Lucre (L2) |
| Tocumen | Panamá | Altos de Tocumen (L2) |
| 24 de Diciembre | Panamá | 24 de Diciembre (L2) |
| Las Cumbres | Panamá | Corredor norte (Chilibre) |
| Amelia Denis de Icaza | San Miguelito | San Miguelito |
| Belisario Porras | San Miguelito | Pan de Azúcar |
| José Domingo Espinar | San Miguelito | Pan de Azúcar |
| Rufina Alfaro | San Miguelito | Cerro Viento (L2) |
| Belisario Frías | San Miguelito | San Miguelito |
| **Omar Torrijos** | San Miguelito | **(ninguno: sin evidencia)** |
| Barrio Colón | La Chorrera | Corredor oeste (La Chorrera) |
| Barrio Balboa | La Chorrera | Corredor oeste (La Chorrera) |
| Guadalupe | La Chorrera | Corredor oeste (La Chorrera) |
| Arraiján cabecera | Arraiján | Corredor oeste (Arraiján) |
| Vista Alegre | Arraiján | Corredor oeste (Arraiján) |
| Burunga | Arraiján | Corredor oeste (Arraiján) |

**Omar Torrijos** (sector de Torrijos Carter, al norte de San Miguelito) queda sin nodo:
el único enlace ferroviario previsto para ese sector (el teleférico/Metrocable) **no está
operativo** y no se encontró evidencia accesible de una zona paga/troncal que lo sirva.
Sus pares se marcan `desconocido` en lugar de forzar una asignación.

**San Francisco** se asigna a la estación **Fernández de Córdoba (L1)**: el informe de
zonificación de la MUPA confirma el corregimiento y sus límites, y fuentes de OpenStreetMap
etiquetan esa estación dentro del corregimiento de San Francisco. El tiempo de acceso (7 min)
es una **estimación del equipo**, distinta de la de Bella Vista (que usa Vía Argentina). Como
San Francisco y Betania comparten el nodo Fernández de Córdoba, su par mutuo se modela como
viaje local (mismo nodo); es una **limitación del modelo de un nodo por corregimiento**, no un
dato oficial. La estación exacta de acceso de San Francisco queda como punto a verificar en
campo.

## Tarifas y su respaldo

| Caso | Tarifa (B/.) | Respaldo |
|---|---|---|
| Solo Metro (una línea) | 0.35 | Oficial (`tarifa-del-metro`) |
| Solo Metro (L1+L2) | 0.85 | Terceros (parcial); el transbordo interno del Metro no está confirmado en fuente oficial |
| Solo corredor de bus | 0.75 | Oficial (`guia-del-usuario`) |
| Corredor + Metro | 1.10 | **Supuesto** del equipo (suma de tarifas); no confirmado como tarifa integrada |
| Viaje local (mismo nodo) | 0.25 | Tarifa troncal oficial usada como supuesto de viaje local |

## Cobertura

- **21 corregimientos** en 4 distritos: Panamá (9), San Miguelito (6), La Chorrera (3) y
  Arraiján (3).
- **420 pares dirigidos** (21 × 20), cada uno en franja pico y valle → **840 filas**.
- De esos pares, **380 tienen datos estimados** y **40 quedan desconocidos** (los que
  involucran a Omar Torrijos).
- **San Francisco** aporta **76 filas con datos estimados** (frente a las 19 zonas con nodo,
  en ambos sentidos y franjas) y **4 filas desconocidas** (frente a Omar Torrijos).

## Cobertura pendiente (no verificada)

- **Tiempos oficiales por par**: no existen en fuentes oficiales accesibles; todo tiempo
  es estimado. Quedan **pendientes** los tiempos reales medidos en campo.
- **Zona Omar Torrijos**: pendiente confirmar qué nodo (si alguno) la sirve.
- **Nodo de acceso de San Francisco**: pendiente verificar en campo la estación exacta
  (Fernández de Córdoba vs. otra del corredor L1); el tiempo de acceso es estimado.
- **Tarifa integrada Metro+bus**: pendiente de confirmar; la fila combinada usa un supuesto.
- **Transbordo interno L1↔L2 del Metro**: pendiente de confirmar en fuente oficial.
- **Corregimientos no incluidos**: la tabla cubre 21 corregimientos; el resto de Panamá,
  San Miguelito y Panamá Oeste queda sin datos.
- **Franjas horarias**: solo pico y valle; no se detallan sábados, domingos ni feriados.

## Diccionario de columnas

- `origen`, `destino`: identificadores del corregimiento (dirigido; no se asume que el
  viaje inverso sea idéntico, aunque el modelo calcule ambos sentidos).
- `nombre_origen`, `nombre_destino`: nombre oficial legible.
- `distrito_origen`, `distrito_destino`: distrito al que pertenece cada corregimiento.
- `modo`: `metro`, `corredor`, `corredor+metro`, `bus_local` o `desconocido`.
- `ruta`: líneas/corredores usados (p. ej. `L1+L2`, `corredor_oeste`). Vacío si es desconocido.
- `tiempo_min`: minutos estimados (entero). **Vacío** si es desconocido.
- `tarifa_usd`: tarifa en B/. (dólares). **Vacío** si es desconocido.
- `transbordos`: número de transbordos estimados. **Vacío** si es desconocido.
- `franja_horaria`: `pico` o `valle`.
- `tipo_dato`: origen del **tiempo** (`estimado` o `desconocido`). No se usa `oficial`
  porque ningún tiempo por par es oficial.
- `confianza`: `alta` (tarifa oficial de un modo), `media` (dato de terceros), `baja`
  (supuesto) o `desconocida` (sin datos).
- `fuente_url`: página oficial que respalda el modo/tarifa. Vacío si es desconocido.
- `fuente_tiempo`: página oficial usada como parámetro del tiempo (vacío si el tramo es de
  bus y no hay fuente de tiempo).
- `fecha_consulta`: fecha de consulta de las fuentes. Vacío si es desconocido.
- `nota`: aclaración de la fila.

## Nota sobre datos ausentes

En el código de matching, un par **sin fila** en la matriz se marca explícitamente como
incumplimiento de tipo `sin_datos` (`agentes/matching/puntaje.py`), no como una tarifa
infinita ni un viaje imposible. Esta tabla **no** cambia ese comportamiento: los pares
desconocidos se omiten al cargar, de modo que el matching usa `sin_datos`. Los datos
personales (nombre, género, edad) no intervienen en el transporte ni en la puntuación.
