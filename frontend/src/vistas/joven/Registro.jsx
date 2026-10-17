import { useEffect, useState } from "react";
import { api, nuevoId } from "../../api.js";
import { TURNOS, corregimiento } from "../../nombres.js";
import Entrevista from "./Entrevista.jsx";
import RevisarHabilidades from "./RevisarHabilidades.jsx";
import SubirCv from "./SubirCv.jsx";

// Une habilidades nuevas con las que ya tenía: por código se queda el nivel más alto.
// nivel_detectado es el tope al que la persona puede corregir (solo hacia abajo).
function unir(actuales, nuevas) {
  const m = new Map(actuales.map((h) => [h.codigo, h]));
  for (const h of nuevas)
    if (!m.has(h.codigo) || h.nivel > (m.get(h.codigo).nivel_detectado || m.get(h.codigo).nivel))
      m.set(h.codigo, { ...h, nivel_detectado: h.nivel });
  return [...m.values()];
}

const MINUTOS = [[30, "30 min"], [45, "45 min"], [60, "1 h"], [90, "1 h 30"]];
const PASAJE = [5, 10, 15, 20, 25];
const SALARIO = [400, 500, 600, 700];

// Respuestas de un toque debajo de un número; el campo sigue editable.
function Rapidas({ opciones, valor, onElegir, etiqueta }) {
  return (
    <div className="rapidas" role="group" aria-label={etiqueta}>
      {opciones.map(([v, texto]) => (
        <button type="button" key={v} className={"chip" + (String(v) === String(valor) ? " activo" : "")}
                aria-pressed={String(v) === String(valor)} onClick={() => onElegir(String(v))}>{texto}</button>
      ))}
    </div>
  );
}

function CodigoAcceso({ token, onListo }) {
  const [copiado, setCopiado] = useState("");
  async function copiar(e) {
    try {
      await navigator.clipboard.writeText(token);
      setCopiado("Copiado ✓");
    } catch {
      // sin portapapeles (página sin https): se selecciona para copiarlo a mano
      const r = document.createRange();
      r.selectNodeContents(e.currentTarget.parentElement.querySelector("code"));
      getSelection().removeAllRanges(); getSelection().addRange(r);
      setCopiado("Ya quedó seleccionado: cópielo");
    }
  }
  return (
    <section className="panel">
      <h2>¡Listo, ya está registrado!</h2>
      <p>Este es su código de acceso:</p>
      <div className="codigo-acceso">
        <code className="token">{token}</code>
        <button type="button" className="boton secundario" onClick={copiar}>{copiado || "Copiar"}</button>
      </div>
      <ul className="nota lista-corta">
        <li>Este equipo lo recuerda: la próxima vez entra directo, sin escribirlo.</li>
        <li>Si entra desde otro teléfono o computadora lo va a necesitar: anótelo o tómele una foto.</li>
      </ul>
      <button className="boton grande" onClick={() => onListo(token)}>Ver vacantes</button>
    </section>
  );
}

export default function Registro({ onListo, onCancelar }) {
  const [paso, setPaso] = useState("experiencia");   // experiencia | cv | entrevista | datos | token
  const [habilidades, setHabilidades] = useState([]);
  const [aviso, setAviso] = useState("");
  const [modoBasico, setModoBasico] = useState(false);
  const [taxonomia, setTaxonomia] = useState([]);
  const [fuentes, setFuentes] = useState([]);    // textos que dio la persona, para mostrar de dónde salió cada habilidad
  const [token, setToken] = useState("");

  useEffect(() => {
    api.habilidades().then(setTaxonomia).catch(() => {});
  }, []);

  function recibir(resultado) {
    setHabilidades((a) => unir(a, resultado.habilidades));
    if (resultado.fuente) setFuentes((f) => [...f, resultado.fuente]);
    // "llm" = lo leyó el asistente; "palabras_clave" o "mixto" = el servicio no respondió y se usó el modo básico
    setModoBasico(Boolean(resultado.metodo) && resultado.metodo !== "llm");
    setAviso(resultado.habilidades.length
      ? `Encontramos ${resultado.habilidades.length} habilidad(es). Revíselas abajo.`
      : "No encontramos habilidades con evidencia. Pruebe con la entrevista corta o agréguelas abajo.");
    setPaso("experiencia");
  }

  if (paso === "cv") return <SubirCv onResultado={recibir} onVolver={() => setPaso("experiencia")} />;
  if (paso === "entrevista") return <Entrevista onResultado={recibir} onVolver={() => setPaso("experiencia")} />;
  if (paso === "datos")
    return <DatosJoven habilidades={habilidades} onVolver={() => setPaso("experiencia")}
                       onRegistrado={(t) => { setToken(t); setPaso("token"); }} />;
  if (paso === "token") return <CodigoAcceso token={token} onListo={onListo} />;

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
      {aviso && <p className="aviso" role="status">{aviso}</p>}
      {modoBasico && (
        <p className="aviso alerta" role="status">
          Hoy el lector automático no está disponible y usamos un modo básico que solo reconoce algunas
          palabras. Revise bien la lista y agregue lo que falte.
        </p>
      )}

      <RevisarHabilidades habilidades={habilidades} setHabilidades={setHabilidades}
                          fuentes={fuentes} taxonomia={taxonomia} />

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
    const id = nuevoId("j");
    const joven = {
      id, corregimiento: f.corregimiento, disponibilidad: f.disponibilidad,
      presupuesto_transporte_semanal: Number(f.presupuesto), salario_minimo: Number(f.salario),
      max_minutos_traslado: Number(f.minutos),
      habilidades: habilidades.map(({ codigo, nivel, evidencia }) => ({ codigo, nivel, evidencia })),
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
        <Rapidas etiqueta="Minutos de viaje" opciones={MINUTOS} valor={f.minutos}
                 onElegir={(v) => setF((x) => ({ ...x, minutos: v }))} />
      </fieldset>

      <fieldset>
        <legend>Dinero</legend>
        <label>Puede gastar en pasaje por semana (B/.)
          <input type="number" min="0" step="0.5" value={f.presupuesto} onChange={cambiar("presupuesto")} />
        </label>
        <Rapidas etiqueta="Pasaje por semana" opciones={PASAJE.map((v) => [v, `B/. ${v}`])} valor={f.presupuesto}
                 onElegir={(v) => setF((x) => ({ ...x, presupuesto: v }))} />
        <p className="nota">Para calcularlo: lo que paga de ida y vuelta en un día, por los días que trabajaría.
          Si el viaje le cuesta B/. 1 por tramo y va 5 días, son B/. 10.</p>
        <label>Salario mínimo que acepta al mes (B/.)
          <input type="number" min="0" step="10" value={f.salario} onChange={cambiar("salario")} />
        </label>
        <Rapidas etiqueta="Salario mínimo" opciones={SALARIO.map((v) => [v, `B/. ${v}`])} valor={f.salario}
                 onElegir={(v) => setF((x) => ({ ...x, salario: v }))} />
      </fieldset>

      {error && <p className="error">{error}</p>}
      <div className="acciones">
        <button type="button" className="enlace" onClick={onVolver}>Volver</button>
        <button className="boton" disabled={enviando}>{enviando ? "Registrando…" : "Registrarme"}</button>
      </div>
    </form>
  );
}
