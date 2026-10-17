import { useEffect, useState } from "react";
import { api, ErrorApi } from "../../api.js";
import { conNombres, corregimiento, dinero } from "../../nombres.js";

// Jóvenes que no tienen match viable y la ruta de cursos que calculó el agente de Formación.
export default function SinMatch({ cat }) {
  const [planes, setPlanes] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.jovenes().then((js) => Promise.all(js.map((j) =>
      api.plan(j.id).then((p) => ({ joven: j, plan: p }))
        .catch((e) => (e instanceof ErrorApi && e.estado === 404 ? null : Promise.reject(e))),
    ))).then((rs) => setPlanes(rs.filter(Boolean))).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!planes) return <p className="centro">Cargando…</p>;
  if (!planes.length) return <p className="vacio">Todos los jóvenes tienen al menos una vacante a su alcance.</p>;
  return (
    <ul className="lista">
      {planes.map(({ joven, plan }) => (
        <li key={joven.id} className="item">
          <div className="entrevista-cabeza">
            <h3>{joven.id} · {corregimiento(joven.corregimiento)}</h3>
            <span className="estado-chip">{plan.semanas_total} sem · {dinero(plan.costo_total)}</span>
          </div>
          <p className="suave">Para: {plan.vacantes_objetivo.map((id) => cat.vacantes[id]?.titulo || id).join(", ")}</p>
          <ol className="ruta">
            {plan.cursos.map((id) => <li key={id}><b>{cat.cursos[id]?.nombre || id}</b>{cat.cursos[id] && <span className="suave"> · {cat.cursos[id].centro}</span>}</li>)}
          </ol>
          {plan.brecha_sin_cubrir.length > 0 && (
            <p className="falta">Sin curso disponible para: {plan.brecha_sin_cubrir.map((c) => cat.habilidades[c] || c).join(", ")}</p>
          )}
          <ul className="motivos">{plan.motivos.map((m) => <li key={m}>{conNombres(m, cat.habilidades)}</li>)}</ul>
        </li>
      ))}
    </ul>
  );
}
