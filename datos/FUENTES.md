# Fuentes del catálogo de cursos (`datos/cursos.csv`)

Fecha de consulta de las fuentes: **2026-10-16**.
Fecha de la auditoría de verificación: **2026-10-16** (se revisaron de nuevo las fuentes de
Cisco y Oracle con la misma fecha).

Este catálogo reúne cursos y recursos de formación gratuitos o de bajo costo útiles para
cerrar brechas de habilidades del matching: **INADEH**, **Cisco Networking Academy** y
**Oracle**. Sirve como referencia del agente de Ruta de formación. Las columnas
`corregimiento`, `turnos`, `sesiones_por_semana`, `semanas` y `cupos_disponibles`
corresponden al modelo `Curso` de `contrato/modelos.py` y quedan vacías porque las páginas
públicas consultadas no publican esos datos por curso (sede, turnos y cupos dependen de cada
centro o cohorte).

## Estados de verificación

- **verificada**: el nombre del curso y su duración (o su naturaleza, para la plataforma)
  constan en una fuente oficial accesible.
- **parcial**: se confirmó la existencia (o el nombre) del curso, pero **no** todos los
  atributos: duración, costo, insignia o certificación. Los atributos que faltan se detallan
  en la columna `notas`.
- **pendiente**: dato aún no confirmado en una fuente oficial accesible.

La existencia de la ficha de un curso **no** implica que su duración, su costo, su insignia
ni su certificación estén verificados; cada atributo se respalda por separado.

## Fuentes oficiales consultadas

| Proveedor | Fuente | URL | Estado |
|---|---|---|---|
| INADEH | Área Tecnología de la Información y la Comunicación | https://www.inadeh.edu.pa/plantransformacionintegral/tecnologia-de-informacion-y-comunicacion/ | Usada (nombre y horas; incluye fichas PDF) |
| INADEH | Área Logística | https://www.inadeh.edu.pa/plantransformacionintegral/logistica/ | Usada (nombre y horas) |
| INADEH | Área Gestión Empresarial | https://www.inadeh.edu.pa/plantransformacionintegral/gestion-empresarial/ | Usada (nombre y horas) |
| INADEH | Área Idiomas | https://www.inadeh.edu.pa/plantransformacionintegral/idiomas/ | Usada (nombre y horas) |
| INADEH | Área Gastronomía | https://www.inadeh.edu.pa/plantransformacionintegral/gastronomia/ | Usada (nombre y horas; incluye fichas PDF) |
| INADEH | Área Electromecánica | https://www.inadeh.edu.pa/plantransformacionintegral/electromecanica/ | Usada (nombre y horas) |
| INADEH | Índice de Áreas de Formación | https://www.inadeh.edu.pa/areas-de-formacion/ | Usada (mapa de áreas) |
| INADEH | Plataforma de preinscripción (catálogo) | https://digital.inadeh.edu.pa/preinscrip/courselist/ | No utilizable (aplicación dinámica sin contenido estático) |
| Cisco NetAcad | Catálogo de cursos (PDF oficial) | https://prelogin-authoring.netacad.com/sites/default/files/course-catalog.pdf | No accesible en la auditoría (respuesta 503 / descarga vacía) |
| Cisco NetAcad | Catálogo de cursos de Cisco (copia de un centro NetAcad, 2023) | https://netacad.nl/wp-content/uploads/2023/10/English-NetAcad-Course-Catalog-Sep-2023-1.pdf | Usada para contrastar duraciones (documento de Cisco) |
| Cisco NetAcad | Fichas de curso | https://www.netacad.com/courses/introduction-to-cybersecurity · /python-essentials-1 · /python-essentials-2 · /networking-basics · /javascript-essentials-1 · /english-for-it1 · /english-for-it2 | Existencia confirmada (rutas propias); duración no expuesta en la ficha |
| Cisco NetAcad | Página de cursos gratis | https://www.cisco.com/site/us/en/learn/training-certifications/training/netacad/index.html | No accesible en la auditoría (403) |
| Oracle | Oracle SQL Explorer (ruta de aprendizaje) | https://learn.oracle.com/ols/learning-path/oracle-sql-explorer/132718/79918 | Accesible: nombre confirmado; duración no visible (contenido dinámico) |
| Oracle | Oracle Database Explorer (ruta de aprendizaje) | https://learn.oracle.com/ols/learning-path/oracle-database-explorer/132718/79873 | Accesible: nombre confirmado; duración no visible (contenido dinámico) |
| Oracle | Familia Database (duraciones del catálogo) | https://education.oracle.com/database/oracle-database/pFamily_32 | No accesible en la auditoría (403): las duraciones de las rutas Explorer no se pudieron confirmar aquí |
| Oracle | Oracle FreeSQL | https://www.oracle.com/database/technologies/oracle-free-sql/ | Usada (plataforma de práctica; descripción completa) |
| Oracle | Databases for Developers: Foundations (Dev Gym) | https://devgym.oracle.com/pls/apex/dg/class/databases-for-developers-foundations.html | Usada (curso gratuito con certificado de finalización de Dev Gym) |

## Correcciones derivadas de la auditoría

1. **Networking Basics (Cisco):** la ficha del curso existe (ruta propia), pero no se pudo
   confirmar su duración. Queda **sin duración**. Discrepancia documentada: **22 horas**
   (referencias de 2026) frente a **25 horas** (catálogo de Cisco 2023-2024).
2. **English for IT (Cisco):** no es un curso único. La fuente oficial lo separa en
   **English for IT 1** y **English for IT 2** (la ruta `/courses/english-for-it` no es una
   página propia). El registro queda como serie, con la columna `duracion` **vacía** y en estado
   **parcial**, a la espera de fijar a cuál de los dos corresponde. La duración **no se da por
   confirmada**: la cifra de 50 h por curso solo consta en un catálogo secundario, no en la ficha
   oficial del curso.
3. **Fichas de Cisco:** se distingue la existencia del curso (confirmada) de la verificación de
   duración, costo, insignia y certificación (no comprobadas de forma independiente). Los seis
   registros de Cisco pasan a **parcial**.
4. **Oracle SQL Explorer:** se conserva el nombre (confirmado en la página oficial); la duración
   y el número de temas se dejan **sin confirmar** porque el catálogo que citaba 1 h 22 min y
   12 temas no era accesible en la auditoría.
5. **Oracle Database Explorer:** el nombre se confirma en la página oficial de la ruta; la
   duración (1 h 42 min) provenía de una página bloqueada y queda **sin confirmar**.
6. **INADEH — duplicados de TIC y Logística:** la página de TIC lista la misma destreza de hoja
   de cálculo con varias duraciones ("Hoja electrónica básica" 40 h, "Hoja de cálculo para
   profesionales" 48 h, "Hoja de cálculo básica" 50 h); se conservó la variante **básica (50 h)**,
   que además tiene ficha técnica. La página de Logística repite "Elementos de la Cadena de
   Suministro (80 h)" dos veces con la **misma** duración (duplicado del listado, no una
   discrepancia). En todos los registros de INADEH se aclara que **la publicación del curso no
   garantiza que la inscripción esté abierta**.
7. **Oracle FreeSQL:** se mantiene como **plataforma de práctica**, sin duración de curso y sin
   certificado de curso.
8. **Oracle Dev Gym:** se precisa que es **gratuito** y que otorga un **certificado de
   finalización de Oracle Dev Gym**, no una certificación profesional de Oracle. No se declara
   una duración total en horas.

## Diccionario de columnas

- `id`: identificador único y estable del registro.
- `proveedor`: INADEH, Cisco NetAcad u Oracle.
- `area`: área o familia de formación.
- `nombre`: nombre del curso tal como lo publica la fuente.
- `duracion`: duración declarada por la fuente. Vacío cuando no se pudo confirmar.
- `modalidad`: presencial, virtual o en línea. Vacío cuando la fuente no lo indica.
- `costo`: valor de la matrícula cuando la fuente lo declara (0 = gratuito). Vacío cuando no consta.
- `corregimiento`, `turnos`, `sesiones_por_semana`, `semanas`, `cupos_disponibles`: campos del
  modelo `Curso`; vacíos porque la fuente no los publica por curso.
- `habilidades_otorgadas`: códigos de la taxonomía vigente, separados por punto y coma.
- `url`: enlace a la ficha o a la página de la fuente.
- `fecha_consulta`: fecha en que se consultó la fuente (sin cambios tras la auditoría).
- `verificacion`: verificada / parcial / pendiente.
- `notas`: aclaraciones y campos que siguen sin verificar.

## Limitaciones y advertencias

- Las páginas de INADEH listan nombre y duración por área, pero **no** publican por curso la
  sede, los turnos, las fechas de cohorte ni el costo; esos datos se confirman en cada centro.
  **Que un curso aparezca publicado no implica que haya inscripciones abiertas ni cupos.**
- La plataforma de preinscripción de INADEH entrega su catálogo de forma dinámica y no expone
  el listado a una consulta automatizada; por eso el catálogo se armó desde las páginas de área.
- El sitio de Cisco devuelve una página genérica para rutas inexistentes, por lo que un código
  HTTP 200 no prueba que un curso exista. La existencia se comprobó por ruta propia; la duración
  proviene del catálogo de Cisco y no de la ficha.
- **Oracle FreeSQL es una plataforma de práctica, no un curso de duración fija** ni otorga
  certificado de curso.
- **Oracle Dev Gym** otorga un certificado de finalización propio, no una certificación
  profesional de Oracle.
- La taxonomía de habilidades vigente no tiene códigos para programación pura, electricidad ni
  refrigeración. Los cursos de programación se asocian a `soporte_tecnico` y los oficios
  técnicos quedan sin habilidad, con la salvedad anotada en cada fila.

## Campos que continúan sin verificar

| Registro | Campos sin verificar |
|---|---|
| `cisco_redes_basicas` | duración (22 h vs 25 h) |
| `cisco_ingles_it` | nombre exacto (English for IT 1 o 2), duración |
| `cisco_intro_ciberseguridad`, `cisco_python_1`, `cisco_python_2`, `cisco_javascript_1` | costo, insignia y certificación (la duración proviene del catálogo, no de la ficha) |
| `oracle_sql_explorer` | duración y número de temas |
| `oracle_database_explorer` | duración |
| Todos los registros | `corregimiento`, `turnos`, `sesiones_por_semana`, `semanas`, `cupos_disponibles` |
