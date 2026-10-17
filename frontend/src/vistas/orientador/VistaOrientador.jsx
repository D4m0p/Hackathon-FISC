import { useEffect, useState } from "react";
import { api } from "../../api.js";
import Bloqueadas from "./Bloqueadas.jsx";
import Matches from "./Matches.jsx";
import Pesos from "./Pesos.jsx";
import SinMatch from "./SinMatch.jsx";
import Trazas from "./Trazas.jsx";

const PESTANAS = [["matches", "Propuestas"], ["bloqueadas", "Bloqueadas"], ["sin", "Sin opciones"], ["pesos", "Prioridades"], ["trazas", "Historial"]];

// Catálogos que usan varias pestañas: nombres de habilidades, vacantes y cursos.
export default function VistaOrientador() {
  const [pestana, setPestana] = useState("matches");
  const [cat, setCat] = useState({ habilidades: {}, vacantes: {}, cursos: {} });

  useEffect(() => {
    Promise.all([api.habilidades(), api.vacantes(), api.cursos()]).then(([hs, vs, cs]) => setCat({
      habilidades: Object.fromEntries(hs.map((h) => [h.codigo, h.nombre])),
      vacantes: Object.fromEntries(vs.map((v) => [v.id, v])),
      cursos: Object.fromEntries(cs.map((c) => [c.id, c])),
    })).catch(() => {});
  }, [pestana]);

  return (
    <div className="vista">
      <nav className="pestanas">
        {PESTANAS.map(([k, t]) => (
          <button key={k} className={pestana === k ? "activa" : ""} onClick={() => setPestana(k)}>{t}</button>
        ))}
      </nav>
      {pestana === "matches" && <Matches cat={cat} />}
      {pestana === "bloqueadas" && <Bloqueadas />}
      {pestana === "sin" && <SinMatch cat={cat} />}
      {pestana === "pesos" && <Pesos cat={cat} />}
      {pestana === "trazas" && <Trazas cat={cat} />}
    </div>
  );
}
