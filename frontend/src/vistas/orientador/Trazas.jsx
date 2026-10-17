import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { conNombres } from "../../nombres.js";

const AGENTES = [["", "Todos"], ["mercado", "Mercado"], ["perfil", "Perfil"], ["matching", "Matching"],
  ["formacion", "Formación"], ["auditor", "Auditor"], ["orquestador", "Orquestador"], ["orientador", "Orientador"]];

// Línea de tiempo: qué agente decidió qué y por qué. También los mensajes enviados.
export default function Trazas({ cat }) {
  const [agente, setAgente] = useState("");
  const [trazas, setTrazas] = useState(null);
  const [mensajes, setMensajes] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setTrazas(null);
    api.trazas(agente).then(setTrazas).catch((e) => setError(e.message));
  }, [agente]);
  useEffect(() => { api.mensajes().then(setMensajes).catch(() => {}); }, []);

  return (
    <>
      <div className="chips filtros">
        {AGENTES.map(([k, t]) => (
          <button key={k} className={"chip" + (agente === k ? " activo" : "")} onClick={() => setAgente(k)}>{t}</button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      {!trazas ? <p className="centro">Cargando…</p> : trazas.length === 0 ? <p className="vacio">Sin registros.</p> : (
        <ol className="linea-tiempo panel">
          {trazas.map((t, i) => (
            <li key={i}>
              <span className="hora">{new Date(t.fecha).toLocaleString("es-PA", { dateStyle: "short", timeStyle: "short", timeZone: "America/Panama" })}</span>
              <span className="agente">{t.agente}</span> <b>{t.accion.replace(/_/g, " ")}</b>
              <div>{conNombres(t.motivo, cat.habilidades)}</div>
            </li>
          ))}
        </ol>
      )}
      {mensajes.length > 0 && (
        <>
          <h4>Mensajes enviados</h4>
          <ul className="lista">
            {mensajes.slice(-20).reverse().map((m, i) => (
              <li key={i} className="item">
                <p>{m.texto}</p>
                <p className="nota">{m.destino || "sin destino"} · {m.enviado ? "enviado" : "solo registrado (sin Telegram)"}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
