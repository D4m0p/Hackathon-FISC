import { useEffect, useRef, useState } from "react";

// Número que sube desde 0 hasta su valor al aparecer (o al cambiar).
export default function Contador({ valor, duracion = 900 }) {
  const [actual, setActual] = useState(0);
  const desde = useRef(0);

  useEffect(() => {
    const inicio = performance.now(), origen = desde.current;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setActual(valor); desde.current = valor; return undefined; }
    let marco;
    const paso = (t) => {
      const p = Math.min(1, (t - inicio) / duracion);
      const v = origen + (valor - origen) * (1 - Math.pow(1 - p, 3));
      setActual(Math.round(v));
      if (p < 1) marco = requestAnimationFrame(paso); else desde.current = valor;
    };
    marco = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(marco);
  }, [valor, duracion]);

  return <>{actual.toLocaleString("es-PA")}</>;
}
