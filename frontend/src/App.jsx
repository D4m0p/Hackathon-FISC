import { useEffect, useState } from "react";
import { api, guardarToken, leerToken } from "./api.js";
import { nombreEmpresa } from "./nombres.js";
import Entrada, { DEMO } from "./vistas/Entrada.jsx";
import VistaJoven from "./vistas/joven/VistaJoven.jsx";
import Registro from "./vistas/joven/Registro.jsx";
import VistaEmpresa from "./vistas/empresa/VistaEmpresa.jsx";
import VistaOrientador from "./vistas/orientador/VistaOrientador.jsx";
import VistaCentro from "./vistas/centro/VistaCentro.jsx";

export default function App() {
  const [yo, setYo] = useState(null);         // {rol, sujeto}
  const [token, setToken] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [registrando, setRegistrando] = useState(false);
  const [error, setError] = useState("");
  // Tema claro u oscuro elegido a mano (si no, sigue al sistema). Se recuerda en este navegador.
  const [tema, setTema] = useState(() => { try { return localStorage.getItem("empleo_tema"); } catch { return null; } });
  useEffect(() => {
    if (tema) document.documentElement.dataset.tema = tema; else delete document.documentElement.dataset.tema;
    try { tema ? localStorage.setItem("empleo_tema", tema) : localStorage.removeItem("empleo_tema"); } catch { /* sin almacenamiento */ }
  }, [tema]);
  const oscuro = tema ? tema === "oscuro" : window.matchMedia?.("(prefers-color-scheme: dark)").matches;

  async function entrar(token) {
    setError("");
    try {
      const ident = await api.yo(token);
      guardarToken(token);
      setToken(token);
      setYo(ident);
      setRegistrando(false);
      window.scrollTo(0, 0);
    } catch (e) {
      // Solo se olvida el código si la API lo rechaza; si está caída, se conserva.
      if (e.estado === 401) guardarToken(null);
      setError(e.estado === 401 ? "Ese código no es válido. Revíselo o regístrese." : e.message);
    }
  }

  function salir() {
    guardarToken(null);
    setToken(null);
    setYo(null);
    setRegistrando(false);
  }

  useEffect(() => {
    const t = leerToken();
    (t ? entrar(t) : Promise.resolve()).finally(() => setCargando(false));
  }, []);

  let contenido;
  if (cargando) contenido = <p className="centro">Cargando…</p>;
  else if (registrando)
    contenido = <Registro onListo={(token) => { setRegistrando(false); entrar(token); }}
                          onCancelar={() => setRegistrando(false)} />;
  else if (!yo) contenido = <Entrada onEntrar={entrar} onNuevo={() => setRegistrando(true)} error={error} />;
  else if (yo.rol === "joven") contenido = <VistaJoven key={token} jovenId={yo.sujeto} />;
  else if (yo.rol === "empresa") contenido = <VistaEmpresa key={token} empresaId={yo.sujeto} />;
  else if (yo.rol === "centro") contenido = <VistaCentro key={token} centro={yo.sujeto} />;
  else contenido = <VistaOrientador key={token} />;

  return (
    <div className={"app" + (yo && yo.rol !== "joven" ? " ancho" : "")}>
      <header className="barra">
        <span className="marca">Empleo<b>Joven</b></span>
        <button className="tema" onClick={() => setTema(oscuro ? "claro" : "oscuro")}
                aria-label={oscuro ? "Usar tema claro" : "Usar tema oscuro"} title={oscuro ? "Tema claro" : "Tema oscuro"}>
          {oscuro ? "☀️" : "🌙"}
        </button>
        {yo && (
          <span className="sesion">
            {/* Cambiar de rol en un clic durante la demo */}
            <select className="cambiar-rol" aria-label="Ver como" value={DEMO.some((d) => d.token === token) ? token : ""}
                    onChange={(e) => e.target.value && entrar(e.target.value)}>
              {!DEMO.some((d) => d.token === token) && <option value="">{yo.rol === "empresa" ? `Empresa · ${nombreEmpresa(yo.sujeto)}` : ROLES[yo.rol]}</option>}
              {DEMO.map((d) => <option key={d.token} value={d.token}>{d.texto}</option>)}
            </select>
            <button className="enlace" onClick={salir}>Salir</button>
          </span>
        )}
      </header>
      <main>{contenido}</main>
    </div>
  );
}

const ROLES = { joven: "Joven", empresa: "Empresa", orientador: "Orientador", centro: "Centro de formación" };
