import { useEffect, useState } from "react";
import { api } from "../../api.js";
import Ayuda from "../../componentes/Ayuda.jsx";
import { corregimiento, etiquetaJoven } from "../../nombres.js";

const CAMPOS = {
  corregimiento: "Dónde vive", disponibilidad: "Su horario", habilidades: "Lo que sabe hacer",
  id: "Número interno", max_minutos_traslado: "Minutos máximos de viaje",
  presupuesto_transporte_semanal: "Presupuesto de pasaje", salario_minimo: "Salario mínimo",
};
const NO_VE = ["Nombre", "Género", "Edad", "Contacto"];

const pct = (x) => Math.round(x * 100);

// Prueba contrafactual: el mismo joven puesto en cada corregimiento. Lo que sabe hacer
// debe puntuar igual en todos lados; solo el traslado y el salario pueden moverse.
export default function Auditoria({ cat }) {
  const ids = Object.keys(cat.jovenes).sort((a, b) => a.localeCompare(b, "es", { numeric: true }));
  const [jovenId, setJovenId] = useState("j01");
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (ids.length && !cat.jovenes[jovenId]) setJovenId(ids[0]);
  }, [ids.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setDatos(null);
    setError("");
    api.contrafactual(jovenId).then(setDatos).catch((e) => setError(e.message));
  }, [jovenId]);

  return (
    <>
      <p className="suave intro">
        ¿El sistema trata igual a todos? Aquí se pone al mismo joven en cada corregimiento y se
        recalcula su puntaje.
        <Ayuda>Si el sistema discriminara por el lugar donde vive, cambiaría lo que vale su experiencia.
        Lo correcto es que «Lo que sabe hacer» puntúe igual en todos lados y solo cambien el tiempo de
        viaje y lo que le queda del salario, que sí dependen del lugar.</Ayuda>
      </p>
      <label className="selector-joven">Joven
        <select value={jovenId} onChange={(e) => setJovenId(e.target.value)}>
          {ids.map((id) => <option key={id} value={id}>{etiquetaJoven(id, cat.jovenes)}</option>)}
        </select>
      </label>

      {error && <p className="error">{error}</p>}
      {!datos && !error && <p className="centro">Calculando…</p>}
      {datos && (
        <>
          <div className={"veredicto " + datos.veredicto}>
            <b>{datos.veredicto === "sin_sesgo" ? "✓ Sin sesgo" : "⚠ Revisar"}</b>
            <span>{datos.veredicto === "sin_sesgo"
              ? "Lo que sabe hacer vale lo mismo viva donde viva, y sus datos personales no influyen."
              : "El Auditor encontró diferencias que hay que revisar."}</span>
          </div>
          {datos.hallazgos.length > 0 && (
            <ul className="lista">{datos.hallazgos.map((h, i) => <li key={i} className="item hallazgo"><p>{h.detalle || JSON.stringify(h)}</p></li>)}</ul>
          )}

          <section className="panel ve-no-ve">
            <h4>Lo que el sistema ve para decidir</h4>
            <div className="chips">{datos.campos_que_ve_el_solver.map((c) => <span key={c} className="chip ve">{CAMPOS[c] || c}</span>)}</div>
            <h4>Lo que el sistema nunca recibe</h4>
            <div className="chips">{NO_VE.map((c) => <span key={c} className="chip no-ve">{c}</span>)}</div>
            <p className="nota">{datos.identidad}</p>
          </section>

          {datos.filas.length === 0 ? (
            <p className="vacio">Este joven no tiene vacantes posibles para comparar. Elija otro.</p>
          ) : datos.filas.map((f) => <TablaVacante key={f.vacante_id} fila={f} hogar={datos.corregimiento} />)}
        </>
      )}
    </>
  );
}

function TablaVacante({ fila, hogar }) {
  const filas = [{ corregimiento: hogar, factible: true, componentes: fila.original, habilidades_igual: true, hogar: true },
    ...fila.variantes.filter((v) => v.corregimiento !== hogar)];
  const factibles = filas.filter((v) => v.factible);
  const siempreIgual = factibles.every((v) => v.habilidades_igual);
  return (
    <section className="panel">
      <h3>{fila.titulo}</h3>
      <div className="tabla-envoltura">
        <table className="tabla-contrafactual">
          <thead>
            <tr><th>Si viviera en…</th><th>Lo que sabe</th><th>Viaje</th><th>Salario</th><th>Total</th></tr>
          </thead>
          <tbody>
            {filas.map((v) => (
              <tr key={v.corregimiento} className={(v.hogar ? "hogar " : "") + (v.factible ? "" : "no-factible")}>
                <th scope="row">{corregimiento(v.corregimiento)}{v.hogar && <small> (donde vive)</small>}</th>
                {v.factible ? (
                  <>
                    <td className={v.habilidades_igual ? "igual" : "distinto"}>{pct(v.componentes.habilidades)}{v.habilidades_igual && " ✓"}</td>
                    <td>{pct(v.componentes.traslado)}</td>
                    <td>{pct(v.componentes.salario)}</td>
                    <td><b>{pct(v.componentes.total)}</b></td>
                  </>
                ) : (
                  <td colSpan="4" className="suave">No le sirve: el viaje o el pasaje pasan su límite</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={siempreIgual ? "aviso ok" : "error"}>
        {siempreIgual
          ? `En los ${factibles.length} lugares posibles, «Lo que sabe hacer» vale ${pct(fila.original.habilidades)}: solo cambian el viaje y el salario.`
          : "«Lo que sabe hacer» cambió según el lugar: esto hay que revisarlo."}
      </p>
    </section>
  );
}
