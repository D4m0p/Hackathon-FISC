import { useEffect, useState } from "react";
import { api } from "../../api.js";
import FormMotivo from "../../componentes/FormMotivo.jsx";

const MOTIVOS_CANCELAR = ["Ya conseguí otro trabajo", "El horario ya no me sirve", "No me queda cerca", "Prefiero no decirlo"];
const MOTIVOS_REPROGRAMAR = ["Tengo un compromiso ese día", "Problema de transporte", "Tengo una cita médica"];

const CIERRES = {
  cancelacion_joven: "Usted la canceló",
  inasistencia: "No se presentó",
  retiro_empresa: "La empresa retiró el proceso",
  vacante_cerrada: "La vacante se cerró",
};

function fecha(iso) {
  return new Date(iso).toLocaleString("es-PA", { weekday: "long", day: "numeric", month: "long",
    hour: "2-digit", minute: "2-digit", timeZone: "America/Panama" });
}

function estadoDe(a) {
  if (!a.vigente) return "cerrada";
  return a.aprobada === null ? "pendiente" : a.aprobada ? "aprobada" : "rechazada";
}

// Entrevistas del joven: puede cancelar (pendiente o aprobada) o reprogramar (aprobada).
export default function Entrevistas({ jovenId, asignaciones, onCambio }) {
  const [titulos, setTitulos] = useState({});
  const [abierta, setAbierta] = useState(null);   // {vacante_id, accion}
  const [aviso, setAviso] = useState("");

  useEffect(() => {
    api.vacantes().then((vs) => setTitulos(Object.fromEntries(vs.map((v) => [v.id, v.titulo])))).catch(() => {});
  }, []);

  if (!asignaciones.length) return null;
  const orden = { aprobada: 0, pendiente: 1, rechazada: 2, cerrada: 3 };
  const lista = [...asignaciones].sort((a, b) => orden[estadoDe(a)] - orden[estadoDe(b)]);

  async function confirmar(a, accion, motivo) {
    if (accion === "cancelar") {
      await api.cancelar(jovenId, a.vacante_id, motivo);
      setAviso("Listo. El cupo queda libre para otra persona y seguimos buscando opciones para usted.");
    } else {
      const r = await api.reprogramar(jovenId, a.vacante_id, motivo);
      setAviso(`Listo, le avisaremos también por mensaje. Nueva fecha: ${fecha(r.entrevista)}`);
    }
    setAbierta(null);
    onCambio();
  }

  return (
    <>
      <h4>Mis entrevistas</h4>
      {aviso && <p className="aviso" role="status">{aviso}</p>}
      <ul className="lista">
        {lista.map((a) => {
          const estado = estadoDe(a);
          const titulo = titulos[a.vacante_id] || a.vacante_id;
          const formulario = abierta?.vacante_id === a.vacante_id ? abierta.accion : null;
          return (
            <li key={a.vacante_id} className={"item entrevista " + estado}>
              <div className="entrevista-cabeza">
                <h3>{titulo}</h3>
                <span className={"estado-chip " + estado}>{ETIQUETAS[estado]}</span>
              </div>
              {estado === "aprobada" && (
                <p>{a.entrevista ? <>Entrevista el <b>{fecha(a.entrevista)}</b></> : "El orientador aprobó; pronto le darán la fecha."}</p>
              )}
              {estado === "pendiente" && <p className="suave">Una orientadora está revisando este match. Le avisaremos cuando lo apruebe.</p>}
              {estado === "rechazada" && <p className="suave">El orientador no lo aprobó{a.motivo_orientador ? `: ${a.motivo_orientador}` : "."}</p>}
              {estado === "cerrada" && (
                <p className="suave">{CIERRES[a.tipo_cierre] || "Cerrada"}{a.motivo_cierre ? ` · ${a.motivo_cierre}` : ""}</p>
              )}

              {formulario ? (
                formulario === "cancelar" ? (
                  <FormMotivo pregunta="¿Por qué cancela?" opciones={MOTIVOS_CANCELAR} peligro textoBoton="Sí, cancelar"
                              nota="El cupo quedará libre para otra persona. Esto no se puede deshacer."
                              onCancelar={() => setAbierta(null)} onConfirmar={(m) => confirmar(a, "cancelar", m)} />
                ) : (
                  <FormMotivo pregunta="¿Por qué necesita otra fecha?" opciones={MOTIVOS_REPROGRAMAR} textoBoton="Pedir otra fecha"
                              nota="Le daremos el siguiente espacio libre de la empresa en su horario."
                              onCancelar={() => setAbierta(null)} onConfirmar={(m) => confirmar(a, "reprogramar", m)} />
                )
              ) : (estado === "aprobada" || estado === "pendiente") && (
                <div className="acciones-item">
                  {estado === "aprobada" && a.entrevista && (
                    <button className="boton secundario" onClick={() => { setAviso(""); setAbierta({ vacante_id: a.vacante_id, accion: "reprogramar" }); }}>
                      Cambiar fecha
                    </button>
                  )}
                  <button className="enlace peligro" onClick={() => { setAviso(""); setAbierta({ vacante_id: a.vacante_id, accion: "cancelar" }); }}>
                    {estado === "pendiente" ? "Ya no me interesa" : "Cancelar entrevista"}
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

const ETIQUETAS = { aprobada: "Confirmada", pendiente: "En revisión", rechazada: "No aprobada", cerrada: "Cerrada" };
