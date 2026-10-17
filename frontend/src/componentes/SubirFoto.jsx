import { useState } from "react";
import { api } from "../api.js";
import FotoPersona from "./FotoPersona.jsx";

// La foto se achica en el teléfono antes de subirla (máx. 480 px, JPG): sube rápido y pesa poco.
function achicar(archivo) {
  return new Promise((resolver, rechazar) => {
    const img = new Image();
    img.onload = () => {
      const escala = Math.min(1, 480 / Math.max(img.width, img.height));
      const lienzo = document.createElement("canvas");
      lienzo.width = Math.round(img.width * escala);
      lienzo.height = Math.round(img.height * escala);
      lienzo.getContext("2d").drawImage(img, 0, 0, lienzo.width, lienzo.height);
      resolver(lienzo.toDataURL("image/jpeg", 0.85).split(",")[1]);
      URL.revokeObjectURL(img.src);
    };
    img.onerror = () => rechazar(new Error("No se pudo leer la imagen"));
    img.src = URL.createObjectURL(archivo);
  });
}

export default function SubirFoto({ jovenId }) {
  const [version, setVersion] = useState(0);
  const [estado, setEstado] = useState("");
  async function elegir(e) {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (!archivo) return;
    setEstado("Subiendo…");
    try {
      await api.subirFoto(jovenId, await achicar(archivo), "image/jpeg");
      setVersion((v) => v + 1);
      setEstado("Listo. La empresa solo la verá cuando su entrevista esté confirmada.");
    } catch (err) { setEstado(err.message); }
  }
  async function quitar() {
    try { await api.borrarFoto(jovenId); setVersion((v) => v + 1); setEstado("Foto quitada."); }
    catch (err) { setEstado(err.message); }
  }
  return (
    <div className="subir-foto">
      <FotoPersona jovenId={jovenId} tamano={72} version={version} />
      <div>
        <label className="boton secundario">
          Subir mi foto
          <input type="file" accept="image/*" capture="user" onChange={elegir} hidden />
        </label>
        <button className="enlace" onClick={quitar}>Quitar</button>
        <p className="nota">{estado || "Opcional. Las empresas no la ven al elegir candidatos: solo cuando su entrevista ya está confirmada."}</p>
      </div>
    </div>
  );
}
