const REGLAS = {
  edad: "Edad", genero: "Género", buena_presencia: "Buena presencia", estado_civil: "Estado civil",
  residencia: "Lugar de residencia", foto: "Foto obligatoria",
};

export function nombreRegla(r) {
  return REGLAS[r] || r.replace(/_/g, " ").replace(/^\w/, (l) => l.toUpperCase());
}

// Lo que encontró el Auditor, con la frase que lo provocó y cómo redactarlo mejor.
export default function Hallazgos({ auditoria }) {
  if (auditoria.aprobado)
    return <p className="aviso ok">El Auditor no encontró requisitos discriminatorios. La vacante ya está publicada.</p>;
  return (
    <div className="hallazgos">
      <p className="aviso alerta">
        <b>La vacante quedó bloqueada.</b> El Auditor encontró {auditoria.hallazgos.length} requisito(s) que pueden
        dejar fuera a personas por razones que no tienen que ver con el trabajo. Corríjala para publicarla.
      </p>
      <ul className="lista">
        {auditoria.hallazgos.map((h, i) => (
          <li key={i} className="item hallazgo">
            <span className="etiqueta-regla">{nombreRegla(h.regla)}</span>
            {h.fragmento && <q className="fragmento">…{h.fragmento.trim()}…</q>}
            <p>{h.detalle}</p>
            {h.sugerencia && <p className="sugerencia"><b>Sugerencia:</b> {h.sugerencia}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
