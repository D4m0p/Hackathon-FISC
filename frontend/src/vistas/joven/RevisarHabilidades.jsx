import { useState } from "react";
import { api } from "../../api.js";
import { NIVELES } from "../../nombres.js";

const PREFIJO_DECLARADA = "Según la persona: ";

// Igual que normalizar() del agente Perfil (minúsculas, sin tildes, espacios simples), pero
// recordando de qué posición del texto original sale cada carácter, para poder resaltarlo.
function normalizarConMapa(s) {
  let out = "";
  const mapa = [];
  for (let i = 0; i < s.length; i++) {
    for (const c of s[i].normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()) {
      if (/\s/.test(c)) {
        if (!out || out.endsWith(" ")) continue;
        out += " ";
      } else out += c;
      mapa.push(i);
    }
  }
  return { out, mapa };
}

// Busca la cita en los textos que dio la persona y devuelve el pedazo de alrededor.
export function ubicarCita(cita, fuentes, margen = 70) {
  const buscada = normalizarConMapa(cita).out.trim();
  if (buscada.length < 3) return null;
  for (const fuente of fuentes) {
    const { out, mapa } = normalizarConMapa(fuente);
    const i = out.indexOf(buscada);
    if (i < 0) continue;
    const ini = mapa[i], fin = mapa[i + buscada.length - 1] + 1;
    let a = Math.max(0, ini - margen), b = Math.min(fuente.length, fin + margen);
    if (a > 0) a = fuente.indexOf(" ", a) + 1 || a;              // no cortar palabras
    if (b < fuente.length) b = fuente.lastIndexOf(" ", b) > fin ? fuente.lastIndexOf(" ", b) : b;
    return { antes: (a > 0 ? "…" : "") + fuente.slice(a, ini), cita: fuente.slice(ini, fin),
             despues: fuente.slice(fin, b) + (b < fuente.length ? "…" : "") };
  }
  return null;
}

function DeDondeSalio({ h, fuentes }) {
  if (!h.evidencia) return null;
  if (h.evidencia.startsWith(PREFIJO_DECLARADA))
    return <p className="cita-propia"><q>{h.evidencia.slice(PREFIJO_DECLARADA.length)}</q> · lo agregó usted</p>;
  const lugar = ubicarCita(h.evidencia, fuentes);
  // si la cita ya es todo lo que escribió (pasa con respuestas cortas), no hay nada más que mostrar
  if (!lugar || (!lugar.antes.trim() && !lugar.despues.replace(/[\s.…,;:!?]/g, ""))) return <q>{h.evidencia}</q>;
  return (
    <details className="de-donde">
      <summary><q>{h.evidencia}</q> <span className="enlace-texto">Ver de dónde salió</span></summary>
      <p>{lugar.antes}<mark>{lugar.cita}</mark>{lugar.despues}</p>
    </details>
  );
}

function AgregarHabilidad({ taxonomia, yaTiene, onAgregar }) {
  const [abierto, setAbierto] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [evidencia, setEvidencia] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const disponibles = taxonomia.filter((h) => !yaTiene.has(h.codigo));

  if (!abierto)
    return disponibles.length > 0 && (
      <button type="button" className="enlace" onClick={() => setAbierto(true)}>
        + Agregar una habilidad que no apareció
      </button>
    );

  async function agregar(e) {
    e.preventDefault();
    if (!codigo) return setError("Elija la habilidad.");
    setError("");
    setEnviando(true);
    try {
      onAgregar(await api.declararHabilidad(codigo, evidencia));
      setCodigo(""); setEvidencia(""); setAbierto(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="agregar-habilidad" onSubmit={agregar}>
      <label>Habilidad
        <select value={codigo} onChange={(e) => setCodigo(e.target.value)}>
          <option value="">Elija una</option>
          {disponibles.map((h) => <option key={h.codigo} value={h.codigo}>{h.nombre}</option>)}
        </select>
      </label>
      <label>¿Dónde lo hizo o lo aprendió?
        <input value={evidencia} maxLength="200" onChange={(e) => setEvidencia(e.target.value)}
               placeholder="Ejemplo: vendo ropa en ferias del barrio desde hace un año" />
      </label>
      <p className="nota">Las que agrega usted quedan como «Básico» y la empresa ve que las indicó usted.</p>
      {error && <p className="error">{error}</p>}
      <div className="acciones">
        <button type="button" className="enlace" onClick={() => { setAbierto(false); setError(""); }}>Cancelar</button>
        <button className="boton" disabled={enviando}>{enviando ? "Agregando…" : "Agregar"}</button>
      </div>
    </form>
  );
}

// Lista para revisar: ver de dónde salió cada habilidad, bajarle el nivel, quitarla o agregar una.
export default function RevisarHabilidades({ habilidades, setHabilidades, fuentes, taxonomia }) {
  const nombres = Object.fromEntries(taxonomia.map((h) => [h.codigo, h.nombre]));
  const cambiarNivel = (codigo, nivel) =>
    setHabilidades((a) => a.map((x) => (x.codigo === codigo ? { ...x, nivel } : x)));

  return (
    <>
      {habilidades.length > 0 && (
        <ul className="habilidades">
          {habilidades.map((h) => {
            const tope = h.nivel_detectado || h.nivel;
            return (
              <li key={h.codigo}>
                <div>
                  <b>{nombres[h.codigo] || h.codigo}</b>{" "}
                  {tope > 1 ? (
                    <select className="nivel-select" aria-label={`Nivel de ${nombres[h.codigo] || h.codigo}`}
                            value={h.nivel} onChange={(e) => cambiarNivel(h.codigo, Number(e.target.value))}>
                      {[1, 2, 3].filter((n) => n <= tope).map((n) => <option key={n} value={n}>{NIVELES[n]}</option>)}
                    </select>
                  ) : <span className="nivel">{NIVELES[h.nivel]}</span>}
                  <DeDondeSalio h={h} fuentes={fuentes} />
                </div>
                <button type="button" className="enlace" aria-label={`Quitar ${nombres[h.codigo] || h.codigo}`}
                        onClick={() => setHabilidades((a) => a.filter((x) => x.codigo !== h.codigo))}>Quitar</button>
              </li>
            );
          })}
        </ul>
      )}
      <AgregarHabilidad taxonomia={taxonomia} yaTiene={new Set(habilidades.map((h) => h.codigo))}
                        onAgregar={(h) => setHabilidades((a) => [...a, h])} />
    </>
  );
}
