# Datos de muestra para la demostración (`datos/demo/`)

Fecha de los datos: **2026-10-16** (la `fecha_consulta` de los CSV de origen).

Esta carpeta guarda la conversión de los datos de investigación
(`datos/ofertas_empleo.csv` y `datos/cursos.csv`) a datos **de muestra**
compatibles con el contrato del proyecto (`contrato/modelos.py`). El resultado se
genera con un script reproducible; **los CSV originales no se tocan**.

> Los registros de esta carpeta son **muestras de investigación**, no
> oportunidades activas confirmadas. Ver "Muestra vs. vacante activa" más abajo.

## Cómo se regenera

```bash
python3 datos/normalizar_demo.py            # escribe en datos/demo/
```

- Entrada: `datos/ofertas_empleo.csv`, `datos/cursos.csv`.
- Salida: `datos/demo/vacantes_demo.json` (contrato `Vacante`),
  `datos/demo/cursos_demo.json` (contrato `Curso`) y
  `datos/demo/exclusiones.json` (trazabilidad y motivos).
- Es **determinístico**: los mismos CSV producen exactamente los mismos bytes.
  Lo cubre `tests/test_datos_demo.py`.

## Resultado actual de la conversión

| Origen | Registros | Convertidos al contrato | Excluidos |
|---|---|---|---|
| `datos/ofertas_empleo.csv` | 30 | **0** | 30 |
| `datos/cursos.csv` | 28 | **0** | 28 |

**Ningún registro se pudo convertir de forma fiel.** No es un error del conversor:
a todos les falta al menos un campo **obligatorio** del modelo, y el conversor no
los rellena con valores inventados ni con los valores por defecto del modelo. El
detalle por registro (con su URL de origen y el motivo) está en
`datos/demo/exclusiones.json`.

### Qué campos obligatorios faltan y por qué

| Modelo | Campo obligatorio | Por qué no se puede tomar de la fuente |
|---|---|---|
| `Vacante` | `empresa_id` | La fuente trae el **nombre** de la empresa, no un identificador. |
| `Vacante` | `corregimiento` | Solo hay **provincia/ubicación textual** ("Ciudad Panamá"), no un corregimiento. |
| `Vacante` | `turnos` | Solo hay **jornada textual** ("Tiempo completo"), que no es un turno del enum. |
| `Vacante` | `salario_mensual` | El salario viene como **texto o rango** y sin periodo confirmado. |
| `Curso` | `corregimiento` | Vacío en la fuente (depende de cada centro o cohorte). |
| `Curso` | `turnos` | Vacío en la fuente. |
| `Curso` | `sesiones_por_semana` | Vacío en la fuente. |
| `Curso` | `semanas` | Vacío en la fuente. |
| `Curso` | `cupos_disponibles` | Vacío en la fuente. |
| `Curso` | `habilidades_otorgadas` | La fuente lista códigos **sin nivel**, y el modelo exige nivel 1-3. |

Estos huecos ya estaban documentados en `datos/FUENTES_OFERTAS.md` y
`datos/FUENTES.md`. Rellenarlos exigiría inventar datos, algo que no se hace.

## Muestra vs. vacante activa

- Un registro de esta carpeta o del CSV **no** es una oferta vigente: es la copia
  de un anuncio público en la fecha de consulta, con su URL de origen. La empresa
  pudo cerrarla, cambiar el salario o republicarla.
- La vigencia solo se respalda con la fecha de expiración que publica el portal
  (cuando la hay). No se declara "activa" ninguna muestra sin esa evidencia.
- La demo que se ejecuta hoy sigue usando `scripts/demo/datos_demo.json`, un
  conjunto **ilustrativo** (empresas y personas ficticias) pensado para el guion.
  Esta carpeta es aparte y **no** se carga en la demo, para no mezclar datos
  ilustrativos con muestras reales ni presentar muestras como activas.

## Cómo se integraría con la demo (cuando haya campos completos)

Los registros convertidos usan exactamente los campos de `Vacante` y `Curso`, de
modo que podrían añadirse a la lista `vacantes`/`cursos` del conjunto de demo sin
cambiar los modelos. Hoy no se hace porque no hay registros convertibles y porque
`scripts/` (incluido `scripts/semilla_demo.py`) es de otro integrante. Si en el
futuro se completa un registro, el conversor lo pondrá en `registros` y bastará
con incorporarlo al flujo de siembra que ya existe.

## Limitaciones

- El conversor **no** busca datos adicionales en la web: solo transforma lo que ya
  está en los CSV. Si una fuente publicara un corregimiento o turnos concretos,
  habría que ampliar el CSV y el mapeo correspondiente.
- `vacantes_demo.json` y `cursos_demo.json` guardan en `origen.sha256` la huella
  del CSV de entrada, para saber exactamente qué versión se convirtió. Es un dato
  de **trazabilidad**: ninguna prueba lo valida (ningún test lo lee) y una huella
  desfasada **no** hace fallar la suite; solo deja de identificar la versión
  convertida. Por eso, si cambia un CSV de origen hay que regenerar esta carpeta
  (con `normalizar_demo.py`) para que la huella vuelva a corresponder.
- Los originales siguen siendo la referencia: `datos/ofertas_empleo.csv`,
  `datos/cursos.csv`, `datos/FUENTES_OFERTAS.md` y `datos/FUENTES.md`.
