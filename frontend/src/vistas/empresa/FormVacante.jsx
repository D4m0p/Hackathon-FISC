import { useEffect, useState } from "react";
import { api, nuevoId } from "../../api.js";
import { TURNOS, corregimiento } from "../../nombres.js";

const VACIA = {
  titulo: "", texto_original: "", corregimiento: "", turnos: [], dias_por_semana: 5,
  salario_mensual: "", cupos: 1, habilidades_requeridas: [],
};

// Crea o corrige una vacante. Al guardar pasa siempre por el Auditor (lo hace la API).
export default function FormVacante({ empresaId, inicial, onPublicada, onCancelar }) {
  const [v, setV] = useState(() => (inicial ? { ...VACIA, ...inicial, turnos: [...inicial.turnos] } : VACIA));
  const [habilidades, setHabilidades] = useState([]);
  const [corregimientos, setCorregimientos] = useState([]);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const cambiar = (k) => (e) => setV({ ...v, [k]: e.target.value });

  useEffect(() => {
    api.habilidades().then(setHabilidades).catch(() => {});
    api.traslados().then((ts) => setCorregimientos([...new Set(ts.flatMap((t) => [t.origen, t.destino]))].sort())).catch(() => {});
  }, []);

  function alternarTurno(t) {
    setV({ ...v, turnos: v.turnos.includes(t) ? v.turnos.filter((x) => x !== t) : [...v.turnos, t] });
  }

  function cambiarRequisito(i, campo, valor) {
    const rs = v.habilidades_requeridas.map((r, j) => (j === i ? { ...r, [campo]: valor } : r));
    setV({ ...v, habilidades_requeridas: rs });
  }

  const libres = habilidades.filter((h) => !v.habilidades_requeridas.some((r) => r.codigo === h.codigo));

  async function enviar(e) {
    e.preventDefault();
    if (!v.corregimiento) return setError("Elija dónde queda el trabajo.");
    if (!v.turnos.length) return setError("Marque al menos un turno.");
    setError("");
    setEnviando(true);
    const vacante = {
      id: inicial?.id || nuevoId("v"),
      empresa_id: empresaId,
      titulo: v.titulo.trim(),
      texto_original: v.texto_original.trim() || null,
      corregimiento: v.corregimiento,
      turnos: v.turnos,
      dias_por_semana: Number(v.dias_por_semana),
      salario_mensual: Number(v.salario_mensual),
      cupos: Number(v.cupos),
      habilidades_requeridas: v.habilidades_requeridas.map((r) => ({ ...r, nivel_minimo: Number(r.nivel_minimo) })),
    };
    try {
      onPublicada(await api.publicarVacante(vacante));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  }

  return (
    <form className="panel" onSubmit={enviar}>
      <h2>{inicial?.id ? "Corregir la vacante" : "Publicar una vacante"}</h2>
      <p className="nota">Antes de publicarse, el Auditor revisa que no tenga requisitos discriminatorios.</p>

      <fieldset>
        <legend>El puesto</legend>
        <label>Título<input required maxLength="120" value={v.titulo} onChange={cambiar("titulo")} placeholder="Ej.: Cajero/a de supermercado" /></label>
        <label>Descripción
          <textarea rows="4" maxLength="2000" value={v.texto_original || ""} onChange={cambiar("texto_original")}
                    placeholder="Funciones, ambiente de trabajo, qué ofrece la empresa…" />
        </label>
      </fieldset>

      <fieldset>
        <legend>Lugar y horario</legend>
        <label>Corregimiento
          <select value={v.corregimiento} onChange={cambiar("corregimiento")}>
            <option value="">Elija uno</option>
            {corregimientos.map((c) => <option key={c} value={c}>{corregimiento(c)}</option>)}
          </select>
          <span className="nota">¿No aparece su lugar? Elija el corregimiento más cercano: con él calculamos el viaje.</span>
        </label>
        <div className="turnos">
          {Object.entries(TURNOS).map(([t, nombre]) => (
            <label key={t} className={"turno" + (v.turnos.includes(t) ? " activo" : "")}>
              <input type="checkbox" checked={v.turnos.includes(t)} onChange={() => alternarTurno(t)} />{nombre}
            </label>
          ))}
        </div>
        <div className="fila">
          <label>Días por semana<input type="number" min="1" max="7" value={v.dias_por_semana} onChange={cambiar("dias_por_semana")} /></label>
          <label>Cupos<input type="number" min="1" max="50" value={v.cupos} onChange={cambiar("cupos")} /></label>
        </div>
        <label>Salario mensual (B/.)<input required type="number" min="0" step="10" value={v.salario_mensual} onChange={cambiar("salario_mensual")} /></label>
      </fieldset>

      <fieldset>
        <legend>Habilidades que necesita</legend>
        {v.habilidades_requeridas.map((r, i) => (
          <div key={r.codigo} className="requisito">
            <b>{habilidades.find((h) => h.codigo === r.codigo)?.nombre || r.codigo}</b>
            <select value={r.nivel_minimo} onChange={(e) => cambiarRequisito(i, "nivel_minimo", e.target.value)} aria-label="Nivel mínimo">
              <option value="1">Básico</option><option value="2">Con práctica</option><option value="3">Avanzado</option>
            </select>
            <label className="casilla">
              <input type="checkbox" checked={r.obligatoria} onChange={(e) => cambiarRequisito(i, "obligatoria", e.target.checked)} />
              Obligatoria
            </label>
            <button type="button" className="enlace" onClick={() => setV({ ...v, habilidades_requeridas: v.habilidades_requeridas.filter((_, j) => j !== i) })}>Quitar</button>
          </div>
        ))}
        {libres.length > 0 && (
          <select value="" onChange={(e) => e.target.value && setV({ ...v, habilidades_requeridas: [...v.habilidades_requeridas, { codigo: e.target.value, nivel_minimo: 1, obligatoria: true }] })}>
            <option value="">+ Agregar habilidad</option>
            {libres.map((h) => <option key={h.codigo} value={h.codigo}>{h.nombre}</option>)}
          </select>
        )}
        <p className="nota">Pida solo lo que de verdad hace falta: cada requisito obligatorio deja fuera a quien no lo tiene.</p>
      </fieldset>

      {error && <p className="error">{error}</p>}
      <div className="acciones">
        <button type="button" className="enlace" onClick={onCancelar}>Cancelar</button>
        <button className="boton" disabled={enviando}>{enviando ? "Revisando…" : inicial?.id ? "Volver a revisar" : "Publicar"}</button>
      </div>
    </form>
  );
}
