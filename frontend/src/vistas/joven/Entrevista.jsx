import { useEffect, useState } from "react";
import { api } from "../../api.js";
import GrabarVoz from "../../componentes/GrabarVoz.jsx";

export default function Entrevista({ onResultado, onVolver }) {
  const [preguntas, setPreguntas] = useState(null);
  const [i, setI] = useState(0);
  const [respuestas, setRespuestas] = useState({});
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [deVoz, setDeVoz] = useState(false);

  useEffect(() => {
    api.preguntas().then(setPreguntas).catch((e) =>
      setError(e.estado === 404 ? "El agente Perfil aún no está conectado a la API." : e.message));
  }, []);

  async function terminar() {
    const lista = Object.entries(respuestas)
      .filter(([, t]) => t.trim())
      .map(([pregunta_id, texto]) => ({ pregunta_id, texto }));
    if (!lista.length) return onResultado({ habilidades: [] });
    setEnviando(true);
    try {
      const r = await api.perfilDesdeEntrevista(lista);
      onResultado({ ...r, fuente: lista.map((x) => x.texto).join("\n") });
    } catch (e) {
      setError(e.message);
      setEnviando(false);
    }
  }

  if (error) return <section className="panel"><p className="error">{error}</p><button className="enlace" onClick={onVolver}>Volver</button></section>;
  if (!preguntas) return <p className="centro">Cargando preguntas…</p>;

  const p = preguntas[i];
  const ultima = i === preguntas.length - 1;
  return (
    <section className="panel">
      <div className="progreso"><div style={{ width: `${((i + 1) / preguntas.length) * 100}%` }} /></div>
      <span className="suave">Pregunta {i + 1} de {preguntas.length}</span>
      <h2>{p.texto}</h2>
      <textarea rows="4" maxLength="600" value={respuestas[p.id] || ""}
                onChange={(e) => setRespuestas({ ...respuestas, [p.id]: e.target.value })}
                placeholder={`Por ejemplo: ${p.ejemplo}`} />
      <GrabarVoz key={p.id} onTexto={(t) => {
        const antes = respuestas[p.id] ? respuestas[p.id] + " " : "";
        setRespuestas({ ...respuestas, [p.id]: (antes + t).slice(0, 600) });
        setDeVoz(true);
      }} />
      <p className="nota">
        {deVoz ? "Revise lo que escribimos de su nota de voz: puede corregirlo antes de seguir."
          : "Puede escribir o hablar. Si no aplica, déjelo en blanco y siga."}
      </p>
      <div className="acciones">
        <button className="enlace" onClick={() => (i ? setI(i - 1) : onVolver())}>Atrás</button>
        {ultima
          ? <button className="boton" disabled={enviando} onClick={terminar}>{enviando ? "Analizando…" : "Terminar"}</button>
          : <button className="boton" onClick={() => setI(i + 1)}>Siguiente</button>}
      </div>
    </section>
  );
}
