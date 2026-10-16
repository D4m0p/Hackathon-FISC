import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { NIVELES, TURNOS, corregimiento } from "../../nombres.js";
import Entrevista from "./Entrevista.jsx";
import SubirCv from "./SubirCv.jsx";

// Une habilidades nuevas con las que ya tenía: por código se queda el nivel más alto.
function unir(actuales, nuevas) {
  const m = new Map(actuales.map((h) => [h.codigo, h]));
  for (const h of nuevas) if (!m.has(h.codigo) || h.nivel > m.get(h.codigo).nivel) m.set(h.codigo, h);
  return [...m.values()];
}

export default function Registro({ onListo, onCancelar }) {
  const [paso, setPaso] = useState("experiencia");   // experiencia | cv | entrevista | datos | token
  const [habilidades, setHabilidades] = useState([]);
  const [aviso, setAviso] = useState("");
  const [nombres, setNombres] = useState({});
  const [token, setToken] = useState("");

  useEffect(() => {
    api.habilidades().then((hs) => setNombres(Object.fromEntries(hs.map((h) => [h.codigo, h.nombre])))).catch(() => {});
  }, []);

  function recibir(resultado) {
    setHabilidades((a) => unir(a, resultado.habilidades));
    setAviso(resultado.habilidades.length
      ? `Encontramos ${resultado.habilidades.length} habilidad(es). Revíselas abajo.`
      : "No encontramos habilidades con evidencia. Pruebe con la entrevista corta.");
    setPaso("experiencia");
  }

  if (paso === "cv") return <SubirCv onResultado={recibir} onVolver={() => setPaso("experiencia")} />;
  if (paso === "entrevista") return <Entrevista onResultado={recibir} onVolver={() => setPaso("experiencia")} />;
  if (paso === "datos")
    return <DatosJoven habilidades={habilidades} onVolver={() => setPaso("experiencia")}
                       onRegistrado={(t) => { setToken(t); setPaso("token"); }} />;
  if (paso === "token")
    return (
      <section className="panel">
        <h2>¡Listo, ya está registrado!</h2>
        <p>Este es su código de acceso. Guárdelo: lo necesitará para volver a entrar.</p>
        <code className="token">{token}</code>
        <button className="boton grande" onClick={() => onListo(token)}>Ver vacantes</button>
      </section>
    );

  return (
    <section className="panel">
      <h2>Cuéntenos lo que sabe hacer</h2>
      <p className="suave">También cuenta lo que ha hecho sin contrato: ayudar en el negocio de la familia, vender por redes, cuidar un depósito…</p>
      <div className="opciones">
        <button className="opcion" onClick={() => setPaso("cv")}>
          <b>Subir mi CV</b><span>PDF, foto o texto</span>
        </button>
        <button className="opcion" onClick={() => setPaso("entrevista")}>
          <b>Responder 5 preguntas</b><span>Si no tiene CV</span>
        </button>
      </div>
      {aviso && <p className="aviso">{aviso}</p>}

      {habilidades.length > 0 && (
        <ul className="habilidades">
          {habilidades.map((h) => (
            <li key={h.codigo}>
              <div>
                <b>{nombres[h.codigo] || h.codigo}</b> <span className="nivel">{NIVELES[h.nivel]}</span>
                {h.evidencia && <q>{h.evidencia}</q>}
              </div>
              <button className="enlace" aria-label="Quitar"
                      onClick={() => setHabilidades((a) => a.filter((x) => x.codigo !== h.codigo))}>Quitar</button>
            </li>
          ))}
        </ul>
      )}

      <div className="acciones">
        <button className="enlace" onClick={onCancelar}>Cancelar</button>
        <button className="boton" onClick={() => setPaso("datos")}>
          {habilidades.length ? "Continuar" : "Continuar sin habilidades"}
        </button>
      </div>
    </section>
  );
}

function DatosJoven({ habilidades, onVolver, onRegistrado }) {
  const [corregimientos, setCorregimientos] = useState([]);
  const [f, setF] = useState({
    nombre: "", edad: "", genero: "no_indica", contacto_telegram: "",
    corregimiento: "", disponibilidad: [], presupuesto: "15", salario: "500", minutos: "75",
  });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const cambiar = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    api.traslados()
      .then((ts) => setCorregimientos([...new Set(ts.flatMap((t) => [t.origen, t.destino]))].sort()))
      .catch((e) => setError(e.message));
  }, []);

  function alternarTurno(t) {
    setF({ ...f, disponibilidad: f.disponibilidad.includes(t)
      ? f.disponibilidad.filter((x) => x !== t) : [...f.disponibilidad, t] });
  }

  async function enviar(e) {
    e.preventDefault();
    if (!f.corregimiento) return setError("Elija dónde vive.");
    if (!f.disponibilidad.length) return setError("Marque al menos un horario disponible.");
    setError("");
    setEnviando(true);
    const id = "j-" + crypto.randomUUID().slice(0, 8);
    const joven = {
      id, corregimiento: f.corregimiento, disponibilidad: f.disponibilidad,
      presupuesto_transporte_semanal: Number(f.presupuesto), salario_minimo: Number(f.salario),
      max_minutos_traslado: Number(f.minutos), habilidades,
    };
    const datos = {
      joven_id: id, nombre: f.nombre.trim(), genero: f.genero,
      edad: f.edad ? Number(f.edad) : null, contacto_telegram: f.contacto_telegram.trim() || null,
    };
    try {
      const r = await api.registrarJoven(joven, datos);
      onRegistrado(r.token);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  }

  return (
    <form className="panel" onSubmit={enviar}>
      <h2>Sus datos</h2>

      <fieldset>
        <legend>Sobre usted</legend>
        <label>Nombre<input required value={f.nombre} onChange={cambiar("nombre")} /></label>
        <div className="fila">
          <label>Edad (opcional)<input type="number" min="14" max="99" value={f.edad} onChange={cambiar("edad")} /></label>
          <label>Género (opcional)
            <select value={f.genero} onChange={cambiar("genero")}>
              <option value="no_indica">Prefiero no decir</option>
              <option value="femenino">Femenino</option>
              <option value="masculino">Masculino</option>
              <option value="otro">Otro</option>
            </select>
          </label>
        </div>
        <label>Usuario de Telegram (opcional)<input value={f.contacto_telegram} onChange={cambiar("contacto_telegram")} /></label>
        <p className="nota">Su nombre, edad y género no se usan para decidir, y las empresas no los ven cuando revisan candidatos.</p>
      </fieldset>

      <fieldset>
        <legend>Dónde y cuándo puede trabajar</legend>
        <label>Corregimiento donde vive
          <select value={f.corregimiento} onChange={cambiar("corregimiento")}>
            <option value="">Elija uno</option>
            {corregimientos.map((c) => <option key={c} value={c}>{corregimiento(c)}</option>)}
          </select>
        </label>
        <div className="turnos">
          {Object.entries(TURNOS).map(([t, nombre]) => (
            <label key={t} className={"turno" + (f.disponibilidad.includes(t) ? " activo" : "")}>
              <input type="checkbox" checked={f.disponibilidad.includes(t)} onChange={() => alternarTurno(t)} />
              {nombre}
            </label>
          ))}
        </div>
        <label>Máximo de minutos de viaje (ida)
          <input type="number" min="10" max="180" value={f.minutos} onChange={cambiar("minutos")} />
        </label>
      </fieldset>

      <fieldset>
        <legend>Dinero</legend>
        <div className="fila">
          <label>Puede gastar en pasaje por semana (B/.)
            <input type="number" min="0" step="0.5" value={f.presupuesto} onChange={cambiar("presupuesto")} />
          </label>
          <label>Salario mínimo que acepta al mes (B/.)
            <input type="number" min="0" step="10" value={f.salario} onChange={cambiar("salario")} />
          </label>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}
      <div className="acciones">
        <button type="button" className="enlace" onClick={onVolver}>Volver</button>
        <button className="boton" disabled={enviando}>{enviando ? "Registrando…" : "Registrarme"}</button>
      </div>
    </form>
  );
}
