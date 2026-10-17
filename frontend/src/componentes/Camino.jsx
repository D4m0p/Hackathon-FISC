// Línea de pasos: los anteriores al actual quedan hechos, el actual resaltado.
export default function Camino({ pasos, actual }) {
  return (
    <ol className="camino" aria-label="Pasos del proceso">
      {pasos.map((p, i) => {
        const estado = i < actual ? "hecho" : i === actual ? "actual" : "pendiente";
        return (
          <li key={p} className={estado} aria-current={estado === "actual" ? "step" : undefined}>
            <span className="camino-punto" aria-hidden="true">{estado === "hecho" ? "✓" : i + 1}</span>
            <span className="camino-texto">{p}</span>
          </li>
        );
      })}
    </ol>
  );
}
