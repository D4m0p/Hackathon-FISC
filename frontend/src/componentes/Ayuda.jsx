import { useEffect, useRef, useState } from "react";

// Botón «?» que explica un término en una frase. Se cierra al tocar fuera o con Escape.
export default function Ayuda({ children, etiqueta = "¿Qué significa?" }) {
  const [abierta, setAbierta] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!abierta) return undefined;
    const cerrar = (e) => { if (e.key === "Escape" || (e.type === "pointerdown" && !ref.current?.contains(e.target))) setAbierta(false); };
    document.addEventListener("pointerdown", cerrar);
    document.addEventListener("keydown", cerrar);
    return () => { document.removeEventListener("pointerdown", cerrar); document.removeEventListener("keydown", cerrar); };
  }, [abierta]);

  return (
    <span className="ayuda" ref={ref}>
      <button type="button" className="ayuda-boton" aria-label={etiqueta} aria-expanded={abierta}
              onClick={(e) => { e.stopPropagation(); setAbierta(!abierta); }}>?</button>
      {abierta && <span className="ayuda-texto" role="tooltip">{children}</span>}
    </span>
  );
}
