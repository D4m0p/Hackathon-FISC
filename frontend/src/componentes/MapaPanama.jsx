import { useState } from "react";
import { ALTO, ANCHO, CANAL, POSICIONES, TIERRA, proyectar } from "../geo.js";
import { corregimiento } from "../nombres.js";

// Mapa esquemático (posiciones aproximadas). puntos: [{codigo, radio, color, anillo?, lineas: [texto], pulso?}]
// casa: codigo del corregimiento del joven (se marca y se trazan líneas hacia los puntos).
export default function MapaPanama({ puntos, casa, seleccionado, onSeleccion, leyenda }) {
  const [encima, setEncima] = useState(null);
  const visibles = puntos.filter((p) => POSICIONES[p.codigo]);
  // La casa se corre un poco si en su corregimiento también hay una burbuja, para no taparla.
  const pCasa = casa && POSICIONES[casa]
    ? proyectar(POSICIONES[casa]).map((v, k) => v + (visibles.some((p) => p.codigo === casa) ? (k ? 18 : -18) : 0))
    : null;
  const info = visibles.find((p) => p.codigo === (encima || seleccionado));

  return (
    <div className="mapa">
      <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} role="img" aria-label="Mapa esquemático de Panamá y Panamá Oeste">
        <defs>
          <radialGradient id="brillo"><stop offset="0%" stopColor="#fff" stopOpacity=".35" /><stop offset="100%" stopColor="#fff" stopOpacity="0" /></radialGradient>
          <pattern id="reticula" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M24 0H0V24" fill="none" stroke="currentColor" strokeOpacity=".06" />
          </pattern>
        </defs>
        <rect width={ANCHO} height={ALTO} fill="url(#reticula)" />
        <path d={TIERRA} className="mapa-tierra" />
        <path d={CANAL} className="mapa-canal" />
        <text x={proyectar([-79.585, 9.12])[0] + 6} y={18} className="mapa-rotulo">Canal</text>
        <text x={proyectar([-79.82, 8.9])[0]} y={proyectar([-79.82, 9.1])[1]} className="mapa-rotulo grande">Panamá Oeste</text>
        <text x={proyectar([-79.46, 9.1])[0]} y={proyectar([-79.46, 9.12])[1]} className="mapa-rotulo grande">Ciudad de Panamá</text>
        <text x={ANCHO - 120} y={ALTO - 12} className="mapa-rotulo">Océano Pacífico</text>

        {pCasa && visibles.filter((p) => p.codigo !== casa).map((p) => {
          const [x, y] = proyectar(POSICIONES[p.codigo]);
          return <line key={"l" + p.codigo} x1={pCasa[0]} y1={pCasa[1]} x2={x} y2={y} className="mapa-linea" stroke={p.color} />;
        })}

        {visibles.map((p) => {
          const [x, y] = proyectar(POSICIONES[p.codigo]);
          const activo = p.codigo === (encima || seleccionado);
          return (
            <g key={p.codigo} transform={`translate(${x} ${y})`} className={"mapa-punto" + (activo ? " activo" : "")}
               onMouseEnter={() => setEncima(p.codigo)} onMouseLeave={() => setEncima(null)}
               onClick={() => onSeleccion?.(p.codigo === seleccionado ? null : p.codigo)}
               tabIndex={onSeleccion ? 0 : -1} role={onSeleccion ? "button" : undefined}
               aria-label={`${corregimiento(p.codigo)}: ${p.lineas.join(", ")}`}
               onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSeleccion?.(p.codigo === seleccionado ? null : p.codigo)}>
              {p.pulso && <circle r={p.radio} fill={p.color} className="mapa-pulso" />}
              {p.anillo && <circle r={p.radio + 5} fill="none" stroke={p.anillo} strokeWidth="2" strokeDasharray="3 3" />}
              <circle r={p.radio} fill={p.color} fillOpacity=".85" />
              <circle r={p.radio} fill="url(#brillo)" />
            </g>
          );
        })}

        {pCasa && (
          <g transform={`translate(${pCasa[0]} ${pCasa[1]})`} className="mapa-casa">
            <circle r="9" className="mapa-casa-anillo" />
            <path d="M-6 1 L0 -5 L6 1 V6 H-6 Z" fill="#fff" />
          </g>
        )}
      </svg>

      {info && (
        <div className="mapa-globo" role="status">
          <b>{corregimiento(info.codigo)}</b>
          {info.lineas.map((l) => <span key={l}>{l}</span>)}
        </div>
      )}
      <div className="mapa-pie">
        {leyenda && <span className="mapa-leyenda">{leyenda}</span>}
        <span className="mapa-aviso">Mapa esquemático: posiciones aproximadas</span>
      </div>
    </div>
  );
}
