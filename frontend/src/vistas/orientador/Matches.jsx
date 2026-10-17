import { useCallback, useEffect, useState } from "react";
import Ayuda from "../../componentes/Ayuda.jsx";
import { api } from "../../api.js";
import Barras from "../../componentes/Barras.jsx";
import FormMotivo from "../../componentes/FormMotivo.jsx";
import { conNombres, corregimiento, etiquetaJoven, nombreEmpresa } from "../../nombres.js";

const FILTROS = [["pendiente", "Por aprobar"], ["aprobada", "Aprobadas"], ["rechazada", "Rechazadas"], ["cerrada", "Cerradas"]];
const CIERRES = { cancelacion_joven: "El joven canceló", inasistencia: "No se presentó", retiro_empresa: "La empresa lo retiró", vacante_cerrada: "Vacante cerrada" };

function fecha(iso) {
  return new Date(iso).toLocaleString("es-PA", { weekday: "long", day: "numeric", month: "long",
    hour: "2-digit", minute: "2-digit", timeZone: "America/Panama" });
}

export default function Matches({ cat }) {
  const [filtro, setFiltro] = useState("pendiente");
  const [lista, setLista] = useState(null);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [corriendo, setCorriendo] = useState(false);
  const [abierto, setAbierto] = useState(null);   // {clave, accion}
  const [mensaje, setMensaje] = useState(null);   // el último aviso enviado a un joven
  const [mutuos, setMutuos] = useState(new Set());

  // Interés mutuo = el joven y la empresa dijeron que sí (sale de la historia de cada joven).
  const cargar = useCallback(() => {
    setLista(null);
    api.asignacionesEstado(filtro).then(async (as) => {
      const jovenes = [...new Set(as.map((a) => a.joven_id))];
      const historias = await Promise.all(jovenes.map((j) => api.historia(j).catch(() => null)));
      const m = new Set();
      for (const h of historias.filter(Boolean)) {
        const si = (actor) => new Set(h.deslizamientos.filter((d) => d.actor === actor && d.le_interesa).map((d) => d.vacante_id));
        const joven = si("joven"), empresa = si("empresa");
        for (const v of joven) if (empresa.has(v)) m.add(`${h.joven.id}|${v}`);
      }
      setMutuos(m);
      const orden = (a) => (m.has(`${a.joven_id}|${a.vacante_id}`) ? 1 : 0);
      setLista([...as].sort((a, b) => orden(b) - orden(a) || b.desglose.total - a.desglose.total));
    }).catch((e) => setError(e.message));
  }, [filtro]);
  useEffect(cargar, [cargar]);

  async function correrMatching() {
    setCorriendo(true);
    setMensaje(null);
    setError("");
    try {
      const r = await api.matching();
      setAviso(`Listo: ${r.asignaciones.length} propuesta(s) para revisar; ${r.sin_asignar.length} joven(es) sin una opción por ahora` +
        (r.infactibles.length ? `, ${r.infactibles.length} par(es) con interés mutuo que no son factibles.` : "."));
      setFiltro("pendiente");
      cargar();
    } catch (e) {
      setError(e.message);
    }
    setCorriendo(false);
  }

  async function aprobar(a) {
    setError("");
    try {
      const r = await api.decidir(a.joven_id, a.vacante_id, true);
      // El mensaje que el sistema le mandó al joven (Telegram o, sin bot, solo registrado).
      const ultimo = (await api.mensajes().catch(() => [])).at(-1);
      setAviso(`Aprobado: entrevista el ${fecha(r.entrevista)}`);
      setMensaje(ultimo ? { ...ultimo, texto: conNombres(ultimo.texto, cat.habilidades) } : null);
      window.scrollTo(0, 0);
      cargar();
    } catch (e) {
      setError(e.message);
    }
  }

  const titulo = (id) => cat.vacantes[id]?.titulo || id;

  return (
    <>
      <div className="barra-acciones">
        <button className="boton" disabled={corriendo} onClick={correrMatching}>
          {corriendo ? "Calculando…" : "Buscar las mejores opciones"}
        </button>
        <Ayuda>
          El sistema reparte las vacantes para que la mayor cantidad de jóvenes consiga una buena opción,
          sin pasarse de los cupos y respetando tiempo de viaje, pasaje, horario y salario mínimo. Es un
          cálculo exacto (optimización), no lo decide una IA. Usted aprueba o rechaza cada propuesta.
        </Ayuda>
      </div>
      <div className="chips filtros">
        {FILTROS.map(([k, t]) => (
          <button key={k} className={"chip" + (filtro === k ? " activo" : "")} onClick={() => { setAviso(""); setMensaje(null); setFiltro(k); }}>{t}</button>
        ))}
      </div>
      {aviso && <p className="aviso" role="status">{aviso}</p>}
      {mensaje && (
        <div className="mensaje-enviado">
          <span className="nota">{mensaje.enviado ? "Mensaje enviado por Telegram" : "Mensaje para el joven (registrado; sin bot de Telegram configurado)"}</span>
          <p className="burbuja">{mensaje.texto}</p>
          <button className="enlace" onClick={() => setMensaje(null)}>Cerrar</button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {!lista ? <p className="centro">Cargando…</p> : lista.length === 0 ? (
        <p className="vacio">{filtro === "pendiente" ? "No hay propuestas por aprobar. Toque «Buscar las mejores opciones»." : "No hay nada aquí."}</p>
      ) : (
        <ul className="lista">
          {lista.map((a) => {
            const clave = `${a.joven_id}|${a.vacante_id}`;
            const v = cat.vacantes[a.vacante_id];
            return (
              <li key={clave} className={"item" + (mutuos.has(clave) ? " mutuo-item" : "")}>
                {mutuos.has(clave) && <span className="etiqueta-mutuo">Interés mutuo: los dos dijeron que sí</span>}
                <div className="tarjeta-cabeza">
                  <div>
                    <h3>{titulo(a.vacante_id)}</h3>
                    <p><b>{etiquetaJoven(a.joven_id, cat.jovenes)}</b></p>
                    {v && <p className="suave">{nombreEmpresa(v.empresa_id)}, en {corregimiento(v.corregimiento)}</p>}
                  </div>
                  <span className="puntaje">{Math.round(a.desglose.total * 100)}<small>/100</small></span>
                </div>
                <Barras desglose={a.desglose} />
                <details className="por-que">
                  <summary>Por qué el sistema lo propone</summary>
                  <ul className="motivos">{a.desglose.motivos.map((m) => <li key={m}>{conNombres(m, cat.habilidades)}</li>)}</ul>
                </details>
                {filtro === "aprobada" && a.entrevista && <p>Entrevista: <b>{fecha(a.entrevista)}</b></p>}
                {a.motivo_orientador && <p className="suave">Motivo del orientador: {a.motivo_orientador}</p>}
                {filtro === "cerrada" && <p className="suave">{CIERRES[a.tipo_cierre] || "Cerrada"}{a.motivo_cierre ? ` · ${a.motivo_cierre}` : ""}</p>}

                {abierto?.clave === clave ? (
                  abierto.accion === "rechazar" ? (
                    <FormMotivo pregunta="¿Por qué rechaza este match?" peligro textoBoton="Rechazar"
                                opciones={["El joven no podrá llegar a tiempo", "La empresa pidió otro perfil", "El joven pidió esperar"]}
                                nota="El motivo queda registrado en la traza."
                                onCancelar={() => setAbierto(null)}
                                onConfirmar={async (m) => { await api.decidir(a.joven_id, a.vacante_id, false, m); setAbierto(null); setAviso("Rechazado; quedó registrado el motivo."); cargar(); }} />
                  ) : (
                    <FormMotivo pregunta="¿Qué pasó con la entrevista?" peligro textoBoton="Registrar inasistencia"
                                opciones={["No se presentó y no avisó", "Llegó muy tarde"]}
                                nota="El cupo se libera y el sistema propone un reemplazo de inmediato."
                                onCancelar={() => setAbierto(null)}
                                onConfirmar={async (m) => {
                                  const r = await api.inasistencia(a.joven_id, a.vacante_id, m);
                                  setAbierto(null);
                                  setAviso(r.nuevas.length
                                    ? `Cupo liberado. Nuevas propuestas: ${r.nuevas.map((n) => `${etiquetaJoven(n.joven_id, cat.jovenes)} → ${titulo(n.vacante_id)}`).join(", ")}.`
                                    : "Cupo liberado. El matching no generó propuestas nuevas (revise «Por aprobar»).");
                                  cargar();
                                }} />
                  )
                ) : filtro === "pendiente" ? (
                  <div className="acciones-item">
                    <button className="boton" onClick={() => aprobar(a)}>Aprobar</button>
                    <button className="enlace peligro" onClick={() => setAbierto({ clave, accion: "rechazar" })}>Rechazar</button>
                  </div>
                ) : filtro === "aprobada" ? (
                  <div className="acciones-item">
                    <button className="enlace peligro" onClick={() => setAbierto({ clave, accion: "inasistencia" })}>Registrar inasistencia</button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
