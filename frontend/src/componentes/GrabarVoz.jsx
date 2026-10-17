import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const MAX_SEGUNDOS = 120;

function aBase64(blob) {
  return new Promise((ok, falla) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",")[1]);
    r.onerror = () => falla(new Error("No se pudo leer el audio"));
    r.readAsDataURL(blob);
  });
}

function formatoGrabacion() {
  if (typeof MediaRecorder === "undefined") return null;
  return ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/mp4"]
    .find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

// Grabar con el micrófono o subir una nota de voz (p. ej. de WhatsApp). Devuelve el texto
// transcrito para que la persona lo revise; no decide nada.
export default function GrabarVoz({ onTexto }) {
  const [estado, setEstado] = useState("listo");   // listo | grabando | enviando
  const [segundos, setSegundos] = useState(0);
  const [error, setError] = useState("");
  const grabador = useRef(null);
  const reloj = useRef(null);
  const puedeGrabar = formatoGrabacion() !== null && !!navigator.mediaDevices?.getUserMedia;

  useEffect(() => () => { clearInterval(reloj.current); grabador.current?.stream?.getTracks().forEach((t) => t.stop()); }, []);

  async function enviar(blob, mime) {
    setEstado("enviando");
    setError("");
    try {
      const r = await api.transcribir("audio", await aBase64(blob), mime);
      onTexto(r.texto);
    } catch (e) {
      setError(e.message);
    }
    setEstado("listo");
  }

  async function empezar() {
    setError("");
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      return setError("No pudimos usar el micrófono. Revise el permiso del navegador o escriba su respuesta.");
    }
    const tipo = formatoGrabacion();
    const rec = new MediaRecorder(stream, tipo ? { mimeType: tipo } : undefined);
    const partes = [];
    rec.ondataavailable = (e) => e.data.size && partes.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(reloj.current);
      const mime = rec.mimeType || tipo || "audio/webm";
      enviar(new Blob(partes, { type: mime }), mime);
    };
    grabador.current = rec;
    rec.start();
    setSegundos(0);
    setEstado("grabando");
    reloj.current = setInterval(() => setSegundos((s) => {
      if (s + 1 >= MAX_SEGUNDOS) rec.state === "recording" && rec.stop();
      return s + 1;
    }), 1000);
  }

  function detener() {
    if (grabador.current?.state === "recording") grabador.current.stop();
  }

  return (
    <div className="grabar-voz">
      {estado === "grabando" ? (
        <button type="button" className="boton grabando" onClick={detener}>
          ⏹ Terminar ({Math.floor(segundos / 60)}:{String(segundos % 60).padStart(2, "0")})
        </button>
      ) : (
        <>
          {puedeGrabar && (
            <button type="button" className="boton secundario" disabled={estado === "enviando"} onClick={empezar}>
              🎤 Responder con voz
            </button>
          )}
          <label className={"enlace subir-audio" + (estado === "enviando" ? " deshabilitado" : "")}>
            <input type="file" accept="audio/*,.ogg,.opus,.m4a" disabled={estado === "enviando"}
                   onChange={(e) => { const f = e.target.files[0]; e.target.value = ""; if (f) enviar(f, f.type || "audio/ogg"); }} />
            o subir una nota de voz
          </label>
        </>
      )}
      {estado === "enviando" && <span className="suave">Escuchando su nota de voz…</span>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
