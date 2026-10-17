import { useEffect, useState } from "react";
import Ayuda from "../../componentes/Ayuda.jsx";
import { api } from "../../api.js";
import FormMotivo from "../../componentes/FormMotivo.jsx";

const MIN = 0.05, MAX = 0.8;
const r2 = (x) => Math.round(x * 100) / 100;

// El orientador ajusta cuánto vale cada componente del puntaje. Antes de aplicar
// puede simular qué propuestas cambiarían; la API no guarda nada al simular.
export default function Pesos({ cat }) {
  const [actuales, setActuales] = useState(null);
  const [h, setH] = useState(0.6);
  const [t, setT] = useState(0.25);
  const [sim, setSim] = useState(null);
  const [aplicando, setAplicando] = useState(false);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.pesos().then((p) => { setActuales(p); setH(p.habilidades); setT(p.traslado); }).catch((e) => setError(e.message));
  }, []);

  const s = r2(1 - h - t);
  const valido = s >= MIN - 1e-9 && s <= MAX + 1e-9;
  const nuevos = { habilidades: r2(h), traslado: r2(t), salario: s };
  const cambio = actuales && (nuevos.habilidades !== actuales.habilidades || nuevos.traslado !== actuales.traslado);
  const titulo = (id) => cat.vacantes[id]?.titulo || id;

  async function simular() {
    setError("");
    setAviso("");
    try { setSim(await api.simularPesos(nuevos)); } catch (e) { setError(e.message); }
  }

  if (!actuales) return error ? <p className="error">{error}</p> : <p className="centro">Cargando…</p>;
  return (
    <section className="panel">
      <h2>Qué importa más al elegir <Ayuda>
        Cada propuesta tiene un puntaje que suma tres cosas: si sabe hacer el trabajo, qué tan fácil le
        queda llegar y cuánto le queda del salario. Aquí decide cuánto pesa cada una. Antes de aplicar,
        «Simular» le muestra qué propuestas cambiarían.
      </Ayuda></h2>
      <p className="suave">Ninguna parte puede bajar de 5 % ni pasar de 80 %, para que ninguna se ignore del todo.</p>
      <Deslizador nombre="Habilidades" valor={h} onCambio={(x) => { setH(x); setSim(null); }} />
      <Deslizador nombre="Traslado" valor={t} onCambio={(x) => { setT(x); setSim(null); }} />
      <div className="peso-fila">
        <span>Salario</span><b className={valido ? "" : "falta"}>{Math.round(s * 100)} %</b>
        <span className="nota">(lo que queda para sumar 100 %)</span>
      </div>
      {!valido && <p className="error">El salario debe quedar entre 5 % y 80 %: ajuste los otros dos.</p>}
      <p className="nota">Actual: habilidades {Math.round(actuales.habilidades * 100)} %, traslado {Math.round(actuales.traslado * 100)} %, salario {Math.round(actuales.salario * 100)} %.</p>

      <div className="acciones-item">
        <button className="boton secundario" disabled={!valido || !cambio} onClick={simular}>Simular</button>
        {sim && !aplicando && <button className="boton" onClick={() => setAplicando(true)}>Aplicar estos pesos</button>}
      </div>
      {error && <p className="error">{error}</p>}
      {aviso && <p className="aviso" role="status">{aviso}</p>}

      {sim && (
        <div className="simulacion">
          <p><b>{sim.se_mantienen}</b> propuesta(s) se mantienen.</p>
          {sim.entran.length > 0 && <><h4>Entrarían</h4><ul className="motivos">{sim.entran.map((c) =>
            <li key={c.joven_id + c.vacante_id}>{c.joven_id} → {titulo(c.vacante_id)} ({Math.round(c.total_nuevo * 100)}/100)</li>)}</ul></>}
          {sim.salen.length > 0 && <><h4>Saldrían</h4><ul className="motivos">{sim.salen.map((c) =>
            <li key={c.joven_id + c.vacante_id}>{c.joven_id} → {titulo(c.vacante_id)} (hoy {Math.round(c.total_actual * 100)}/100)</li>)}</ul></>}
          {!sim.entran.length && !sim.salen.length && <p className="suave">Las propuestas serían las mismas; solo cambian los puntajes.</p>}
        </div>
      )}
      {aplicando && (
        <FormMotivo pregunta="¿Por qué cambia los pesos?" textoBoton="Aplicar"
                    opciones={["Los traslados largos están causando inasistencias", "Priorizar habilidades para puestos técnicos"]}
                    nota="Las propuestas pendientes se retiran; corra el matching otra vez para recalcularlas."
                    onCancelar={() => setAplicando(false)}
                    onConfirmar={async (m) => {
                      const p = await api.cambiarPesos(nuevos, m);
                      setActuales(p); setAplicando(false); setSim(null);
                      setAviso("Pesos aplicados. Vaya a Matches y corra el matching para ver las nuevas propuestas.");
                    }} />
      )}
    </section>
  );
}

function Deslizador({ nombre, valor, onCambio }) {
  return (
    <label className="peso-fila">
      <span>{nombre}</span>
      <input type="range" min={MIN} max={MAX} step="0.05" value={valor} onChange={(e) => onCambio(Number(e.target.value))} />
      <b>{Math.round(valor * 100)} %</b>
    </label>
  );
}
