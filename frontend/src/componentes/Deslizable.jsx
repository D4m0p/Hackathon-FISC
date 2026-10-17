import { useEffect, useRef, useState } from "react";

const UMBRAL = 110;   // píxeles para que cuente como deslizamiento

// Tarjeta que se arrastra a la derecha (me interesa) o a la izquierda (no me interesa).
// También responde a las flechas del teclado y a los botones de abajo.
export default function Deslizable({ children, onDecidir, deshabilitado }) {
  const [dx, setDx] = useState(0);
  const [saliendo, setSaliendo] = useState(0);   // -1, 0, 1
  const inicio = useRef(null);

  function decidir(dir) {
    if (deshabilitado || saliendo) return;
    setSaliendo(dir);
    setTimeout(() => { onDecidir(dir > 0); setSaliendo(0); setDx(0); }, 220);
  }

  useEffect(() => {
    const tecla = (e) => {
      if (e.target.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight") decidir(1);
      if (e.key === "ArrowLeft") decidir(-1);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  const x = saliendo ? saliendo * 600 : dx;
  const estilo = {
    transform: `translateX(${x}px) rotate(${x / 25}deg)`,
    transition: inicio.current === null ? "transform .22s ease" : "none",
  };

  return (
    <div className="deslizable">
      <div className="tarjeta" style={estilo}
           onPointerDown={(e) => {
             // Los botones y enlaces de adentro («?», «Ver cómo se calculó») no inician arrastre.
             if (e.target.closest("button, summary, a, input, select, .ayuda-texto")) return;
             inicio.current = e.clientX;
             e.currentTarget.setPointerCapture(e.pointerId);
           }}
           onPointerMove={(e) => { if (inicio.current !== null) setDx(e.clientX - inicio.current); }}
           onPointerUp={() => {
             inicio.current = null;
             if (Math.abs(dx) > UMBRAL) decidir(Math.sign(dx)); else setDx(0);
           }}
           onPointerCancel={() => { inicio.current = null; setDx(0); }}>
        {dx > 40 && <span className="sello si">ME INTERESA</span>}
        {dx < -40 && <span className="sello no">PASO</span>}
        {children}
      </div>
      <div className="botones-deslizar">
        <button className="redondo no" disabled={deshabilitado} onClick={() => decidir(-1)} aria-label="No me interesa">✕</button>
        <button className="redondo si" disabled={deshabilitado} onClick={() => decidir(1)} aria-label="Me interesa">✓</button>
      </div>
    </div>
  );
}
