# Fuentes: ubicaciones de los corregimientos (`datos/corregimientos.csv`)

Un punto por corregimiento para el mapa (tablero del orientador y mapa del joven). Ninguna
coordenada es inventada: todas provienen de OpenStreetMap.

## Fuente

- **OpenStreetMap vía Nominatim** (`https://nominatim.openstreetmap.org/search`).
- Servicio de geocodificación de OpenStreetMap. Datos abiertos bajo **licencia ODbL**
  (Open Database License). Atribución obligatoria: **© colaboradores de OpenStreetMap**.
- Cada fila lleva `fuente_url` con el elemento OSM exacto
  (`https://www.openstreetmap.org/relation/<id>` o `.../node/<id>`) y `fecha_consulta`.

## Cómo se obtiene

1. Para cada zona de `datos/transporte.csv` se prueban, **en orden**, hasta dos consultas
   (con una pausa de al menos 1,2 s entre cada petición):
   - (a) `"<nombre>, <distrito>, Panamá"`;
   - (b) `"<nombre>, Distrito de <distrito>, Panamá"`.
   Se usa la **primera** que devuelva un candidato válido.
2. **Emparejamiento del distrito.** Un componente del texto casa con el distrito si es igual
   al distrito o a `"Distrito de <distrito>"` (sin acentos, mayúsculas ni el país). Así
   `"Distrito de Panamá"` casa con `"Panamá"`, pero `"Provincia de Panamá"` y `"Panamá Oeste"`
   **no**. Se excluye el último tramo del texto, que es el país.
3. **Prioridad de candidatos:**
   - **Relación OSM** `boundary` / `administrative` (frontera administrativa). Es la opción
     preferida. Se elige la cuyo primer tramo coincide con el corregimiento pedido; si
     ninguna coincide, la primera por relevancia. Confianza **ALTA** o **REVISAR** según las
     reglas de abajo.
   - **Nodo OSM** `place` con tipo en `city`, `town`, `village`, `suburb`, `neighbourhood` o
     `quarter`, cuyo primer tramo del texto sea el corregimiento pedido y cuyo distrito casa
     como en el punto 2. Solo se usa si no hay relación. Confianza **REVISAR** siempre.
   - Nunca se aceptan edificios, comercios, vías (`way`) ni cualquier otro elemento.
4. Se comprueba que el punto caiga en la caja aproximada de las 24 zonas
   (lat 8.75–9.25, lon -79.95–-79.20).

### Valores de `tipo_punto`

- **`punto_osm`**: punto de una frontera administrativa (relación OSM).
- **`nodo_lugar_osm`**: punto de un nodo "lugar" de OpenStreetMap (último recurso).

En ambos casos es el punto que devuelve Nominatim para el elemento, no una coordenada de
cabecera levantada aparte.

## Confianza

- **ALTA**: el distrito aparece en el texto (sin contar el país) y hay **una sola** frontera
  candidata; no es el distrito genérico "Panamá".
- **REVISAR**: hubo **varios** candidatos; el distrito es **"Panamá"** (nombre que también
  designa al país y a la provincia); o el punto vino de un **nodo "lugar"** en vez de una
  frontera administrativa.

## Lo que queda fuera

No se escribe nada si falta alguna zona, salvo que se use `--forzar`. Una zona queda fuera,
y se lista al final, cuando:

- no hay frontera administrativa que coincida con el distrito
  ("sin frontera administrativa que coincida con el distrito");
- el punto devuelto cae fuera de la zona esperada ("punto fuera de zona");
- la consulta falla ("error de consulta").

## Uso

```bash
python datos/obtener_corregimientos.py --contacto tu_correo@ejemplo.com          # escribe el CSV
python datos/obtener_corregimientos.py --contacto ... --seco                     # solo imprime
python datos/obtener_corregimientos.py --contacto ... --forzar                   # escribe aunque falten zonas
```

Nominal: máximo 1 petición por segundo y un User-Agent que identifique a quien consulta
(por eso `--contacto` es obligatorio).

## Límites conocidos

- El CSV cubre las **24 zonas de `datos/transporte.csv`**. Los ids de la demo que no son
  corregimientos (`san_miguelito`, que es un distrito, y `la_chorrera`) no producen un punto
  propio: un distrito de 9 corregimientos no tiene una ubicación única que no sea inventada.
- Cuando varias fronteras comparten el nombre del distrito, o el punto es un nodo "lugar", la
  elección se marca **REVISAR** para que una persona la confirme.
