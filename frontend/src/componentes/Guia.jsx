// Explicación corta que aparece la primera vez (y cuando se pide con «¿Cómo funciona?»).
export default function Guia({ titulo, pasos, onCerrar }) {
  return (
    <div className="guia-fondo" role="dialog" aria-modal="true" aria-label={titulo}>
      <div className="guia">
        <h2>{titulo}</h2>
        <ol className="guia-pasos">
          {pasos.map(([icono, texto]) => (
            <li key={texto}><span className="guia-icono" aria-hidden="true">{icono}</span><span>{texto}</span></li>
          ))}
        </ol>
        <button className="boton grande" onClick={onCerrar} autoFocus>Entendido</button>
      </div>
    </div>
  );
}

const CLAVE = "empleo_guia_vista";

export function guiaVista(rol) {
  try { return localStorage.getItem(`${CLAVE}_${rol}`) === "1"; } catch { return false; }
}

export function marcarGuiaVista(rol) {
  try { localStorage.setItem(`${CLAVE}_${rol}`, "1"); } catch { /* sin almacenamiento: se vuelve a mostrar */ }
}
