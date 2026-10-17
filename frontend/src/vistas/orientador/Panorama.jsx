import { useEffect, useState } from "react";
import { api } from "../../api.js";
import Ayuda from "../../componentes/Ayuda.jsx";
import BarrasH from "../../componentes/BarrasH.jsx";
import Contador from "../../componentes/Contador.jsx";
import MapaPanama from "../../componentes/MapaPanama.jsx";
import { corregimiento } from "../../nombres.js";
import Automaticas from "./Automaticas.jsx";

const MOTIVOS = [
  ["presupuesto", "El pasaje no le alcanza"], ["traslado", "Le queda muy lejos"], ["horario", "No coincide el horario"],
  ["salario", "Paga menos de lo que pide"], ["habilidad", "Le falta una habilidad"], ["sin_datos", "Sin datos de cómo llegar"],
];
const AMBAR = "#f2b84b";

// Tablero del orientador: cifras, mapa por corregimiento, por qué se descartan las combinaciones
// y lo que más piden las empresas. Solo muestra lo que ya calcularon los agentes.
export default function Panorama({ cat, onIr }) {
  const [d, setD] = useState(null);
  const [zona, setZona] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.impacto(), api.planes(), api.asignacionesEstado("pendiente"), api.tendencias(5)])
      .then(([impacto, planes, pendientes, tendencias]) => setD({ impacto, planes, pendientes, tendencias }))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!d) return <p className="centro">Cargando panorama…</p>;

  const sinOpcion = new Set(d.planes.map((p) => p.joven_id));
  const vacantes = Object.values(cat.vacantes).filter((v) => v.estado === "publicada");
  const jovenes = Object.values(cat.jovenes);
  const zonas = [...new Set([...vacantes.map((v) => v.corregimiento), ...jovenes.map((j) => j.corregimiento)])];
  const puntos = zonas.map((z) => {
    const nv = vacantes.filter((v) => v.corregimiento === z).length;
    const js = jovenes.filter((j) => j.corregimiento === z);
    const ns = js.filter((j) => sinOpcion.has(j.id)).length;
    return {
      codigo: z, radio: 7 + nv * 5, color: ns ? AMBAR : "var(--aqua)", anillo: js.length ? "var(--celeste)" : null, pulso: ns > 0,
      lineas: [`${nv} vacante(s) publicada(s)`, `${js.length} joven(es) viven aquí`, ...(ns ? [`${ns} sin ninguna opción todavía`] : [])],
    };
  });

  const piden = zona ? (d.tendencias.por_zona[zona] || []) : Object.values(
    Object.values(d.tendencias.por_zona).flat().reduce((acc, h) => {
      acc[h.codigo] = { ...h, vacantes: (acc[h.codigo]?.vacantes || 0) + h.vacantes };
      return acc;
    }, {})).sort((a, b) => b.vacantes - a.vacantes).slice(0, 5);

  const i = d.impacto;
  const kpis = [
    ["Combinaciones revisadas", i.pares, `${i.jovenes} jóvenes × ${i.vacantes_publicadas} vacantes`, null],
    ["Le sirven al joven", i.viables, `${Math.round((i.viables / Math.max(1, i.pares)) * 100)} % del total`, null],
    ["Propuestas por aprobar", d.pendientes.length, "esperan su decisión", "matches"],
    ["Jóvenes sin opción", sinOpcion.size, "con ruta de cursos", "sin"],
  ];

  return (
    <div className="panorama">
      <div className="kpis">
        {kpis.map(([titulo, valor, sub, ir]) => (
          <button key={titulo} className={"kpi" + (ir ? " enlazable" : "")} onClick={() => ir && onIr(ir)} disabled={!ir}>
            <span className="kpi-titulo">{titulo}</span>
            <b className="kpi-valor"><Contador valor={valor} /></b>
            <span className="kpi-sub">{sub}</span>
          </button>
        ))}
      </div>

      <div className="panorama-grilla">
        <div className="panorama-izq">
        <section className="panel-oscuro panorama-mapa">
          <div className="panel-cabeza">
            <h3>Dónde están las vacantes y los jóvenes</h3>
            {zona && <button className="chip claro" onClick={() => setZona(null)}>Ver todo · quitar {corregimiento(zona)}</button>}
          </div>
          <MapaPanama puntos={puntos} seleccionado={zona} onSeleccion={setZona}
                      leyenda={<><i className="punto aqua" /> vacantes (tamaño) <i className="punto anillo" /> viven jóvenes <i className="punto ambar" /> hay jóvenes sin opción</>} />
          <p className="nota">Toque un corregimiento para ver qué piden las empresas ahí.</p>
        </section>
        <Automaticas cat={cat} />
        </div>

        <div className="panorama-lado">
          <section className="panel">
            <h3>¿Por qué no sirven las demás? <Ayuda>De todas las combinaciones joven–vacante, cuántas fallan por cada
              motivo. Una misma combinación puede fallar en varias cosas, por eso la suma es mayor. Lo calcula el
              Matching con reglas fijas.</Ayuda></h3>
            <p className="suave">{(i.pares - i.viables).toLocaleString("es-PA")} combinaciones descartadas; {i.pares_con_un_solo_motivo} fallan en una sola cosa.</p>
            <BarrasH filas={MOTIVOS.filter(([k]) => i.descartes[k] > 0).map(([k, e]) => ({
              clave: k, etiqueta: e, valor: i.descartes[k], color: k === "traslado" || k === "presupuesto" ? AMBAR : "var(--celeste)" }))} />
            <p className="nota">En ámbar, lo que tiene que ver con la geografía: distancia y pasaje.</p>
          </section>

          <section className="panel">
            <h3>Lo que más piden las empresas {zona ? `en ${corregimiento(zona)}` : ""}</h3>
            {piden.length ? (
              <BarrasH filas={piden.map((h) => ({ clave: h.codigo, etiqueta: cat.habilidades[h.codigo] || h.nombre, valor: h.vacantes }))}
                       sufijo=" vac." />
            ) : <p className="suave">No hay vacantes publicadas en esta zona.</p>}
            <p className="nota">{d.tendencias.nota}</p>
          </section>
        </div>
      </div>
    </div>
  );
}
