import { useState } from "react";
import { nombreEmpresa } from "../nombres.js";

// Logo generado: iniciales del nombre de la empresa sobre un color que sale siempre igual de su
// id. No se suben imágenes (eso queda para más adelante); así cada empresa se reconoce a simple
// vista. Los candidatos, en cambio, no llevan foto: la empresa decide por habilidades.
function iniciales(nombre) {
  const palabras = nombre.split(/\s+/).filter((p) => p.length > 2 || /^[A-ZÁÉÍÓÚÑ]/.test(p));
  const letras = (palabras.length ? palabras : [nombre]).slice(0, 2).map((p) => p[0]);
  return letras.join("").toUpperCase();
}

function tono(id) {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return 168 + (h % 44);   // entre aqua y azul: combina con la paleta de la página
}

// Si la empresa tiene logo en public/logos/<id>.svg (ejemplos ilustrados de la demo), se usa ese;
// si no, las iniciales.
export default function LogoEmpresa({ empresaId, tamano = 44 }) {
  const nombre = nombreEmpresa(empresaId);
  const [sinImagen, setSinImagen] = useState(false);
  if (!sinImagen)
    return (
      <img className="logo-empresa imagen" src={`/logos/${empresaId}.svg`} alt="" aria-hidden="true"
           width={tamano} height={tamano} onError={() => setSinImagen(true)} />
    );
  return (
    <span className="logo-empresa" title={nombre} aria-hidden="true"
          style={{ width: tamano, height: tamano, fontSize: tamano * 0.38,
                   background: `hsl(${tono(empresaId)} 55% 38%)` }}>
      {iniciales(nombre)}
    </span>
  );
}
