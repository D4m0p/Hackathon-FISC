import { useEffect, useState } from "react";

// Barras horizontales que crecen al aparecer. filas: [{clave, etiqueta, valor, detalle?}]
export default function BarrasH({ filas, maximo, color = "var(--aqua)", sufijo = "" }) {
  const [listo, setListo] = useState(false);
  useEffect(() => { const t = setTimeout(() => setListo(true), 60); return () => clearTimeout(t); }, []);
  const tope = maximo || Math.max(1, ...filas.map((f) => f.valor));
  return (
    <ul className="barras-h">
      {filas.map((f, i) => (
        <li key={f.clave} title={f.detalle || ""}>
          <span className="barras-h-etiqueta">{f.etiqueta}</span>
          <span className="barras-h-pista">
            <span className="barras-h-relleno"
                  style={{ width: listo ? `${(f.valor / tope) * 100}%` : 0, background: f.color || color, transitionDelay: `${i * 70}ms` }} />
          </span>
          <b className="barras-h-valor">{f.valor}{sufijo}</b>
        </li>
      ))}
    </ul>
  );
}
