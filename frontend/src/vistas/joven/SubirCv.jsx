import { useState } from "react";
import { api } from "../../api.js";

const MAX_BYTES = 4 * 1024 * 1024;

function aBase64(archivo) {
  return new Promise((ok, falla) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",")[1]);
    r.onerror = () => falla(new Error("No se pudo leer el archivo"));
    r.readAsDataURL(archivo);
  });
}

export default function SubirCv({ onResultado, onVolver }) {
  const [modo, setModo] = useState("archivo");
  const [texto, setTexto] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState("");
  const [leyendo, setLeyendo] = useState(false);

  async function analizar(e) {
    e.preventDefault();
    setError("");
    let cuerpo;
    if (modo === "texto") {
      if (!texto.trim()) return setError("Escriba o pegue el texto de su CV.");
      cuerpo = { tipo: "texto", texto };
    } else {
      if (!archivo) return setError("Elija un archivo.");
      if (archivo.size > MAX_BYTES) return setError("El archivo supera 4 MB.");
      const esPdf = archivo.type === "application/pdf";
      cuerpo = { tipo: esPdf ? "pdf" : "imagen", tipo_mime: archivo.type,
                 contenido_base64: await aBase64(archivo) };
    }
    setLeyendo(true);
    try {
      const r = await api.perfilDesdeCv(cuerpo);
      onResultado({ ...r, fuente: modo === "texto" ? texto : r.texto_leido });
    } catch (err) {
      setError(err.estado === 404 ? "El agente Perfil aún no está conectado a la API." : err.message);
      setLeyendo(false);
    }
  }

  return (
    <form className="panel" onSubmit={analizar}>
      <h2>Su CV</h2>
      <div className="pestanas">
        <button type="button" className={modo === "archivo" ? "activa" : ""} onClick={() => setModo("archivo")}>PDF o foto</button>
        <button type="button" className={modo === "texto" ? "activa" : ""} onClick={() => setModo("texto")}>Escribirlo</button>
      </div>
      {modo === "archivo" ? (
        <label className="soltar">
          <input type="file" accept="application/pdf,image/jpeg,image/png,image/webp"
                 onChange={(e) => setArchivo(e.target.files[0] || null)} />
          {archivo ? <b>{archivo.name}</b> : <span>Toque para elegir un PDF o una foto de su CV</span>}
        </label>
      ) : (
        <textarea rows="8" maxLength="8000" value={texto} onChange={(e) => setTexto(e.target.value)}
                  placeholder="Ejemplo: Desde 2022 ayudo en la fonda de mi abuela: preparo almuerzos y cobro…" />
      )}
      <p className="nota">Solo leemos su CV para encontrar habilidades; no guardamos el texto.</p>
      {leyendo && <p className="aviso" role="status">Leyendo su CV… puede tardar unos segundos.</p>}
      {error && <p className="error">{error}</p>}
      <div className="acciones">
        <button type="button" className="enlace" onClick={onVolver}>Volver</button>
        <button className="boton" disabled={leyendo}>{leyendo ? "Leyendo…" : "Buscar habilidades"}</button>
      </div>
    </form>
  );
}
