import { useState } from "react";

// Pide un motivo (obligatorio en la API) con atajos de un toque.
export default function FormMotivo({ pregunta, opciones = [], nota, textoBoton, peligro, onCancelar, onConfirmar }) {
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    if (!motivo.trim()) return setError("Escriba el motivo, aunque sea corto.");
    setEnviando(true);
    setError("");
    try {
      await onConfirmar(motivo.trim());
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  }

  return (
    <form className="form-motivo" onSubmit={enviar}>
      <p><b>{pregunta}</b></p>
      {opciones.length > 0 && (
        <div className="chips">
          {opciones.map((o) => (
            <button type="button" key={o} className={"chip" + (motivo === o ? " activo" : "")} onClick={() => setMotivo(o)}>{o}</button>
          ))}
        </div>
      )}
      <input value={motivo} maxLength="300" onChange={(e) => setMotivo(e.target.value)}
             placeholder={opciones.length ? "U otro motivo" : "Motivo"} />
      {nota && <p className="nota">{nota}</p>}
      {error && <p className="error">{error}</p>}
      <div className="acciones">
        <button type="button" className="enlace" onClick={onCancelar}>Volver</button>
        <button className={"boton" + (peligro ? " peligro" : "")} disabled={enviando}>
          {enviando ? "Enviando…" : textoBoton}
        </button>
      </div>
    </form>
  );
}
