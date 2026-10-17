# Muestra sintética para la demo (`datos/demo_muestra/`)

> **AVISO: todos los datos de esta carpeta son ficticios.**
> Jóvenes, vacantes, cursos, cupos, empresas, salarios, turnos y deslizamientos
> (interacciones) están **inventados** a propósito para demostrar el flujo de la
> aplicación. **No** representan personas, empresas, ofertas laborales ni cursos
> reales ni vigentes, y no provienen de ningún portal.

## Para qué sirve

Los datos de investigación (`datos/ofertas_empleo.csv` y `datos/cursos.csv`) **no se
pueden convertir** a los modelos del contrato sin inventar campos obligatorios
(corregimiento, turnos, salario mensual, semanas, cupos, niveles): el detalle está en
`datos/demo/LEEME.md` y en `datos/demo/exclusiones.json`. Por eso, para tener una
primera muestra **funcional** sin tocar los modelos, los agentes ni los datos
originales, se usa este conjunto **separado y rotulado como sintético**.

Demuestra el recorrido completo: publicar vacantes (pasan por el Auditor), registrar
jóvenes, deslizar, correr el matching y generar un plan de formación.

## Qué no es esta muestra

- **No es fuente de verdad del mercado.** No use estas cifras (número de vacantes,
  salarios, cupos o habilidades demandadas) como conclusiones ni estadísticas reales de
  empleo: sirven únicamente para pruebas y demostraciones.
- **Academias y fuentes pueden ser reales, los registros no.** Es posible que algunos
  centros de formación o fuentes de investigación citados en `datos/` existan de verdad,
  pero eso **no** convierte a estos registros sintéticos en cursos u ofertas actualmente
  disponibles.
- **No sustituye los datos de investigación.** No reemplaza ni corrige
  `datos/ofertas_empleo.csv`, `datos/cursos.csv` ni `datos/FUENTES*.md`, que se conservan
  intactos y son la referencia de lo verificable.

## Cómo se carga

```bash
.venv/bin/python datos/cargar_muestra.py --base datos_muestra.db --reiniciar --matching
```

- `--base` ruta de la base SQLite (por defecto `datos_muestra.db`).
- `--reiniciar` borra la base antes de cargar; `--matching` corre el matching al final.
- El cargador **no modifica** `scripts/semilla_demo.py`: importa y reutiliza sus
  funciones `cargar` y `credenciales_demo` (scripts/ es de otro integrante). Tokens:
  `demo-orientador`, `demo-<joven_id>` y `demo-<empresa_id>`.

## Qué contiene

| Clave | Cantidad | Notas |
|---|---|---|
| `habilidades` | 11 | La misma taxonomía del sistema (infraestructura, no una afirmación sobre empleos). |
| `traslados` | 10 | Matriz ilustrativa entre los 5 corregimientos usados. |
| `vacantes` | 6 | Ficticias (`v_sint_*`, empresa `e_sint_*`). |
| `cursos` | 5 | Ficticios (`c_sint_*`), centro "Centro Demo de Formación". |
| `jovenes` | 5 | Ficticios (`j_sint_*`); uno sin habilidades para mostrar el plan de formación. |
| `deslizamientos` | 8 | Cuatro pares con interés mutuo para que el matching asigne. |

Resultado esperado: 6 vacantes (ninguna bloqueada), 5 jóvenes, 5 cursos, 4 asignaciones
y 1 plan de formación.

## Cómo se distingue de lo real

- Todo dato inventado vive **solo** aquí. Los CSV de investigación y sus documentos
  (`datos/FUENTES*.md`) se conservan intactos y son la referencia de lo verificable.
- Identificadores inequívocos: vacantes `v_sint_*`, cursos `c_sint_*`, jóvenes
  `j_sint_*`, empresas `e_sint_*`, centro "Centro Demo de Formación".
- El archivo lleva un `_nota` que lo declara ficticio; no incluye URLs de origen.
- La demo ilustrativa por defecto (`scripts/demo/datos_demo.json`, que usa `scripts/demo.sh`)
  **no** cambia: esta muestra es aparte y no se carga por accidente.

## Pruebas

`tests/test_demo_muestra.py` verifica que todo valida contra el contrato, que está
rotulada como ficticia, que no se mezcla con los datos de investigación, que la
integridad referencial es correcta y que el flujo carga y produce resultados.

## Pendiente de coordinar con A

Lo ideal es que el cargador de la demo acepte un `--datos RUTA` opcional en
`scripts/semilla_demo.py` (archivo de A) para sembrar esta muestra por la vía estándar
(`scripts/demo.sh`). Mientras tanto, este cargador funciona sin tocar `scripts/`.
