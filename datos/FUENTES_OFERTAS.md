# Fuentes de las ofertas de empleo (`datos/ofertas_empleo.csv`)

Fecha de consulta de todas las fuentes: **2026-10-16**.

Este archivo reúne ofertas de empleo reales de Panamá con URL individual verificable. Sirve
de referencia del agente de Inteligencia de mercado y del matching: cada fila describe una
plaza concreta (empresa, ubicación, jornada, salario, experiencia, educación y requisitos tal
como los publica la fuente). El catálogo tiene **30 ofertas**: 11 previas (EstasContratado y
Computrabajo) y 19 agregadas en esta ronda, orientadas a cubrir sectores que faltaban
(ciberseguridad, desarrollo de software, ventas, atención al cliente, gastronomía,
mantenimiento y puestos sin experiencia o de poco tiempo).

## Estados de verificación

- **verificada**: la página individual de la oferta se abrió y se leyó completa; los datos
  salen del propio aviso.
- **parcial**: se abrió la página, pero falta algún dato (fecha de publicación o de expiración,
  vigencia no confirmada) o el portal ya marca la vacante como cerrada. Se detalla en
  `nota_verificacion`.
- **pendiente**: dato que no se pudo confirmar en una fuente accesible.

La existencia de la página de una oferta **no** implica que siga vigente: muchas plazas se
republican con otro `id` o se cierran sin borrar la página. La vigencia se respalda por la
fecha de expiración cuando el portal la publica.

## Fuentes por portal

| Portal | Uso en este catálogo | URL base | Estado |
|---|---|---|---|
| EstasContratado | 19 ofertas (incluidas las nuevas de ventas, gastronomía, mantenimiento y TI) | https://www.estascontratado.com/ | Utilizable (páginas individuales `/<id>/<slug>.aspx`; requiere el `slug` correcto) |
| Computrabajo Panamá | 6 ofertas previas | https://pa.computrabajo.com/ | No utilizable de forma directa (`robots.txt` bloquea la lectura); datos de esas filas tomados de snapshots del buscador |
| CazVid | 2 ofertas nuevas (ciberseguridad y desarrollo) | https://cazvid.com/es/ | Utilizable (páginas individuales accesibles) |
| Canal de Panamá (Portal de empleo) | 1 oferta nueva (ciberseguridad) | https://empleos.pancanal.com/ | Utilizable; la plaza consultada figura **cerrada** |
| UTP — Bolsa de Trabajo | 1 oferta nueva (desarrollo) | https://bolsadetrabajo.utp.ac.pa/ | Utilizable (páginas individuales accesibles) |
| Hiringroom — Banco Nacional de Panamá | 1 oferta nueva (desarrollo) | https://banconacionaldepanama.hiringroom.com/ | Utilizable (página de la vacante accesible) |

Portales revisados y **descartados** para estas filas:

- **Konzerta (`konzerta.com`)**: es una aplicación que se arma en el navegador; sus páginas
  individuales devuelven un contenedor vacío al leerse sin JavaScript, por lo que no se pudo
  confirmar el contenido de forma directa. (Su portal asociado `konzertaselecta.hiringroom.com`
  respondió que la vacante buscada ya no está publicada.)
- **Computrabajo (`pa.computrabajo.com`)**: bloqueado por `robots.txt`; solo se usaron los
  snapshots del buscador para las filas previas.
- **Tigo (`tigo.wd103.myworkdayjobs.com`)**: el portal (Workday) respondió "currently
  unavailable" al leerse de forma directa.
- **`pa.opcionempleo.com`, `www.panamajobs.com`, `pawnacional`, `talent.com`, `jooble`,
  `encuentra24`**: sin acceso o sin páginas individuales confirmables.
- **LinkedIn**: bloqueado.

## Ofertas agregadas en esta ronda (OF-012 a OF-030)

| id | Fuente | Sector | Título | Empresa | Estado |
|---|---|---|---|---|---|
| OF-012 | Canal de Panamá | Ciberseguridad | ESPECIALISTA EN CIBERSEGURIDAD | Autoridad del Canal de Panamá | parcial (plaza cerrada) |
| OF-013 | CazVid | Ciberseguridad | Arquitecto de Ciberseguridad IT | Grupo Sega | verificada |
| OF-014 | CazVid | Desarrollo de software | Desarrollador de Software Jr. | KOGNIA CONSULTING (para Global Bank Panamá) | verificada |
| OF-015 | UTP Bolsa de Trabajo | Desarrollo de software | Desarrollador Full Stack | EDUPAN S A | verificada |
| OF-016 | Hiringroom | Desarrollo de software | Analista Programador (a) | Banco Nacional de Panamá | parcial (fecha relativa) |
| OF-017 | EstasContratado | Administración de TI | Jefe de Tecnología de la Información | confidencial | verificada |
| OF-018 | EstasContratado | Infraestructura y redes | LÍDER DE TI E INFRAESTRUCTURA | GREENCOL SA | verificada |
| OF-019 | EstasContratado | Videovigilancia y seguridad | OPERADOR DE CCTV | Maxipista de Panama | verificada |
| OF-020 | EstasContratado | Ventas / banca y automotriz | Asesor De Venta De Autos Hipotecas O Productos Bancarios | confidencial | verificada |
| OF-021 | EstasContratado | Ventas / consumo masivo | SUPERVISOR DE VENTAS PANAMA | Panama Bakery | verificada |
| OF-022 | EstasContratado | Ventas / retail | Vendedor/ Mercaderista | Milov Foods | verificada |
| OF-023 | EstasContratado | Atención al cliente / call center | Customer Service Representative | ITS PTY | verificada |
| OF-024 | EstasContratado | Atención al cliente / aerolíneas | Agente de reservas y ventas corporativas | Grupo Eulen Panamá | verificada |
| OF-025 | EstasContratado | Gastronomía / salón | Salonero | Cirsa Panamá | verificada |
| OF-026 | EstasContratado | Gastronomía / supervisión A&B | Supervisor de Alimentos y Bebidas | Cirsa Panamá | verificada |
| OF-027 | EstasContratado | Gastronomía / cocina | Cook II Pastry | MARRIOT Panamá | verificada |
| OF-028 | EstasContratado | Mantenimiento / electricidad | Electricista idóneo | EULEN PANAMA DE SERVICIOS | verificada |
| OF-029 | EstasContratado | Mantenimiento / mecánica automotriz | Mecanico | CarSpot | verificada |
| OF-030 | EstasContratado | Mantenimiento / electrónica | TECNICO SAT | confidencial | verificada |

## Cobertura de sectores

- **Ciberseguridad:** OF-012, OF-013. Costó hallar plazas de este sector: en EstasContratado las
  búsquedas de "ciberseguridad" devuelven sobre todo jefaturas de informática o ingeniería de
  sistemas, no seguridad.
- **Desarrollo de software:** OF-014, OF-015, OF-016.
- **Sin experiencia o menos de un año:** OF-023 (Customer Service, "Menos de un año"), OF-027
  (Cook II Pastry, "Sin experiencia") y OF-030 (Técnico SAT, "Menos de un año"). OF-016 no
  pertenece a este grupo: en el portal su experiencia figura como **"Semi Senior"** y el
  "hace 7 días" de su `nota_verificacion` es la antigüedad de la publicación, no el nivel exigido.

## Diccionario de columnas

- `id`: identificador único y estable del registro en este catálogo (`OF-0NN`).
- `fuente`: portal de origen (EstasContratado, Computrabajo, CazVid, Canal de Panamá, UTP
  Bolsa de Trabajo, Hiringroom).
- `url`: enlace a la página individual de la oferta.
- `fecha_consulta`: fecha en que se consultó la fuente.
- `fecha_publicacion`, `fecha_expiracion`: fechas del aviso tal como las publica el portal
  (formato `AAAA-MM-DD`); `no_publicado` cuando no aparecen.
- `estado_verificacion`: verificada / parcial / pendiente.
- `nota_verificacion`: aclaraciones sobre lo leído y sobre datos dudosos o ausentes.
- `titulo_original`: título de la plaza tal como lo publica la fuente.
- `empresa`: empleador. `no_publicado (confidencial)` cuando el aviso no lo divulga.
- `ubicacion_texto`, `provincia`: ubicación del aviso y su provincia normalizada.
- `sector`: área de la empresa o rubro de la plaza.
- `jornada`, `tipo_contrato`: jornada y tipo de contratación; `no_publicado` si el portal no
  lo distingue (EstasContratado solo muestra "Tiempo completo").
- `salario`: rango tal como lo publica el portal; `no_publicado` si no aparece.
- `experiencia`, `educacion`: nivel de experiencia y escolaridad exigidos.
- `requisitos_originales`: resumen de funciones y requisitos tomados del aviso.
- `habilidades_codigos`: códigos de la taxonomía vigente (los 11 del agente de mercado)
  separados por punto y coma; vacío cuando el aviso no respalda ningún código.
- `vacantes`: número de puestos vacantes; `no_publicado` si no aparece.

## Limitaciones y advertencias

- Sobre `habilidades_codigos`: la taxonomía vigente tiene 11 códigos de nivel inicial. Las 11
  filas previas (OF-001 a OF-011) tienen esta columna **vacía**; en las filas nuevas solo se
  asignó un código cuando el aviso lo respalda de forma clara. Las plazas de ciberseguridad,
  desarrollo de software y los oficios técnicos (electricidad, mecánica) quedan sin código
  porque la taxonomía no tiene términos para ellos.
- Salario: en EstasContratado muchos avisos no publican monto y en otros el rango no indica el
  periodo (mensual, quincenal, etc.); se conserva el texto del portal sin interpretarlo.
- Las plazas de EstasContratado se **republican con otro `id`** y misma descripción (por ejemplo
  el operador de CCTV de Maxipista aparece como 1107250, 1115801 y 1117645). Se incluyó una
  sola para no duplicar el mismo puesto.
- Fechas relativas: cuando el portal muestra "hace N días" en lugar de una fecha, se anota en
  `nota_verificacion` y `fecha_publicacion` queda como `no_publicado`.
- La vigencia de una plaza no se garantiza por la fecha de expiración: la empresa puede cerrarla
  antes. **Que una oferta aparezca no implica que siga abierta.**

## Campos que continúan sin verificar

| Registro | Campos sin verificar |
|---|---|
| `OF-012` | vigencia (plaza cerrada), fechas de publicación y expiración |
| `OF-016` | fecha de publicación exacta y fecha de expiración |
| `OF-013`, `OF-014` | salario y modalidad (CazVid muestra "No especificado") |
| `OF-015` | fecha de expiración |
| Todas las filas de EstasContratado | `tipo_contrato` (el portal no lo distingue de la jornada) |
