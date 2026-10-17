import { useEffect, useState } from "react";
import { api } from "../../api.js";
import Auditoria from "./Auditoria.jsx";
import Bloqueadas from "./Bloqueadas.jsx";
import Panorama from "./Panorama.jsx";
import Matches from "./Matches.jsx";
import Pesos from "./Pesos.jsx";
import SinMatch from "./SinMatch.jsx";
import Trazas from "./Trazas.jsx";

const PESTANAS = [["panorama", "Panorama"], ["matches", "Propuestas"], ["bloqueadas", "Bloqueadas"], ["sin", "Sin opciones"], ["pesos", "Prioridades"], ["auditoria", "Auditoría"], ["trazas", "Historial"]];

// Catálogos que usan varias pestañas: nombres de habilidades, vacantes y cursos.
export default function VistaOrientador() {
  const [pestana, setPestana] = useState("panorama");
  const [cat, setCat] = useState({ habilidades: {}, vacantes: {}, cursos: {}, jovenes: {} });

  useEffect(() => {
    Promise.all([api.habilidades(), api.vacantes(), api.cursos(), api.jovenes()]).then(([hs, vs, cs, js]) => setCat({
      habilidades: Object.fromEntries(hs.map((h) => [h.codigo, h.nombre])),
      vacantes: Object.fromEntries(vs.map((v) => [v.id, v])),
      cursos: Object.fromEntries(cs.map((c) => [c.id, c])),
      jovenes: Object.fromEntries(js.map((j) => [j.id, j])),
    })).catch(() => {});
  }, [pestana]);

  return (
    <div className="vista">
      <ReiniciarSimulacion />
      <nav className="pestanas">
        {PESTANAS.map(([k, t]) => (
          <button key={k} className={pestana === k ? "activa" : ""} onClick={() => setPestana(k)}>{t}</button>
        ))}
      </nav>
      {pestana === "panorama" && <Panorama cat={cat} onIr={setPestana} />}
      {pestana === "matches" && <Matches cat={cat} />}
      {pestana === "bloqueadas" && <Bloqueadas />}
      {pestana === "sin" && <SinMatch cat={cat} />}
      {pestana === "pesos" && <Pesos cat={cat} />}
      {pestana === "auditoria" && <Auditoria cat={cat} />}
      {pestana === "trazas" && <Trazas cat={cat} />}
    </div>
  );
}

// Vuelve a los datos de demostración (vacantes, jóvenes, cursos y matching inicial).
function ReiniciarSimulacion() {
  const [paso, setPaso] = useState("boton");   // boton | confirmar | trabajando
  const [error, setError] = useState("");
  async function reiniciar() {
    setPaso("trabajando");
    setError("");
    try {
      await api.reiniciarDemo();
      window.location.reload();
    } catch (e) {
      setError(e.message);
      setPaso("boton");
    }
  }
  if (paso === "boton")
    return (
      <div className="reiniciar-demo">
        {error && <span className="error">{error}</span>}
        <button className="enlace" onClick={() => setPaso("confirmar")}>↺ Reiniciar simulación</button>
      </div>
    );
  return (
    <div className="aviso alerta reiniciar-confirmar" role="alertdialog" aria-label="Reiniciar simulación">
      <span>Se borra todo lo hecho (deslizamientos, aprobaciones, reservas, ofertas nuevas y registros) y se
        vuelve a los datos de demostración. ¿Seguir?</span>
      <div className="acciones">
        <button className="enlace" disabled={paso === "trabajando"} onClick={() => setPaso("boton")}>Cancelar</button>
        <button className="boton" disabled={paso === "trabajando"} onClick={reiniciar}>
          {paso === "trabajando" ? "Reiniciando…" : "Sí, reiniciar"}
        </button>
      </div>
    </div>
  );
}
