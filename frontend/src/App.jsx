import { useEffect, useState } from "react";
import { api, guardarToken, leerToken } from "./api.js";
import Entrada from "./vistas/Entrada.jsx";
import VistaJoven from "./vistas/joven/VistaJoven.jsx";
import Registro from "./vistas/joven/Registro.jsx";
import VistaEmpresa from "./vistas/VistaEmpresa.jsx";
import VistaOrientador from "./vistas/VistaOrientador.jsx";

export default function App() {
  const [yo, setYo] = useState(null);         // {rol, sujeto}
  const [cargando, setCargando] = useState(true);
  const [registrando, setRegistrando] = useState(false);
  const [error, setError] = useState("");

  async function entrar(token) {
    setError("");
    try {
      const ident = await api.yo(token);
      guardarToken(token);
      setYo(ident);
    } catch (e) {
      guardarToken(null);
      setError(e.message);
    }
  }

  function salir() {
    guardarToken(null);
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
  else if (yo.rol === "joven") contenido = <VistaJoven jovenId={yo.sujeto} />;
  else if (yo.rol === "empresa") contenido = <VistaEmpresa empresaId={yo.sujeto} />;
  else contenido = <VistaOrientador />;

  return (
    <div className="app">
      <header className="barra">
        <span className="marca">Empleo<b>Joven</b></span>
        {yo && (
          <span className="sesion">
            <span className="etiqueta">{ROLES[yo.rol]}{yo.sujeto ? ` · ${yo.sujeto}` : ""}</span>
            <button className="enlace" onClick={salir}>Salir</button>
          </span>
        )}
      </header>
      <main>{contenido}</main>
    </div>
  );
}

const ROLES = { joven: "Joven", empresa: "Empresa", orientador: "Orientador" };
