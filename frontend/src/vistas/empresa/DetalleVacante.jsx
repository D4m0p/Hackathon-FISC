import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import Ayuda from "../../componentes/Ayuda.jsx";
import Barras from "../../componentes/Barras.jsx";
import Deslizable from "../../componentes/Deslizable.jsx";
import FormMotivo from "../../componentes/FormMotivo.jsx";
import FotoPersona from "../../componentes/FotoPersona.jsx";
import { NIVELES, TURNOS, conNombres, corregimiento, dinero, numeroCorto } from "../../nombres.js";

const ESTADOS = { publicada: "Publicada", bloqueada: "Bloqueada", cerrada: "Cerrada", borrador: "Borrador" };

export default function DetalleVacante({ vacante: v, onVolver, onEditar, onRevisada, onCambio }) {
  const [nombres, setNombres] = useState({});
  const [pestana, setPestana] = useState("candidatos");
  const [cerrando, setCerrando] = useState(false);
  const [revisando, setRevisando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.habilidades().then((hs) => setNombres(Object.fromEntries(hs.map((h) => [h.codigo, h.nombre])))).catch(() => {});
  }, []);

  // Una vacante bloqueada se vuelve a mandar tal cual: el Auditor la revisa y dice qué falla.
  async function verMotivos() {
    setRevisando(true);
    setError("");
    try {
      onRevisada(await api.publicarVacante(v));
    } catch (e) {
      setError(e.message);
      setRevisando(false);
    }
  }

  return (
    <div className="vista">
      <button className="enlace" onClick={onVolver}>← Mis vacantes</button>
      <section className="panel">
        <div className="entrevista-cabeza">
          <h2>{v.titulo}</h2>
          <span className={"estado-chip " + v.estado}>{ESTADOS[v.estado] || v.estado}</span>
        </div>
        <p className="suave">
          {corregimiento(v.corregimiento)} · {[...v.turnos].map((t) => TURNOS[t]).join(", ")} · {v.dias_por_semana} días ·{" "}
          {dinero(v.salario_mensual)} al mes · {v.cupos} cupo(s)
        </p>
        {v.habilidades_requeridas.length > 0 && (
          <p>Pide: {v.habilidades_requeridas.map((r) =>
            `${nombres[r.codigo] || r.codigo}${r.obligatoria ? "" : " (deseable)"}`).join(", ")}</p>
        )}
        {v.texto_original && <p className="suave cita">{v.texto_original}</p>}

        {v.estado === "bloqueada" && (
          <>
            <p className="aviso alerta">El Auditor bloqueó esta vacante por requisitos que pueden discriminar. Nadie la ve hasta que la corrija.</p>
            <div className="acciones-item">
              <button className="boton" disabled={revisando} onClick={verMotivos}>{revisando ? "Revisando…" : "Ver qué hay que corregir"}</button>
              <button className="boton secundario" onClick={onEditar}>Corregir</button>
            </div>
          </>
        )}
        {v.estado === "publicada" && !cerrando && (
          <div className="acciones-item">
            <button className="boton secundario" onClick={onEditar}>Editar</button>
            <button className="enlace peligro" onClick={() => setCerrando(true)}>Cerrar vacante</button>
          </div>
        )}
        {cerrando && (
          <FormMotivo pregunta="¿Por qué cierra la vacante?" peligro textoBoton="Sí, cerrar"
                      opciones={["Ya cubrimos el puesto", "Se canceló el puesto", "Cambió el presupuesto"]}
                      nota="Las personas en proceso recibirán un aviso y el sistema les buscará otra opción."
                      onCancelar={() => setCerrando(false)}
                      onConfirmar={async (m) => { await api.cerrarVacante(v.id, m); setCerrando(false); onCambio(); }} />
        )}
        {error && <p className="error">{error}</p>}
      </section>

      {v.estado === "publicada" && (
        <>
          <nav className="pestanas">
            <button className={pestana === "candidatos" ? "activa" : ""} onClick={() => setPestana("candidatos")}>Candidatos</button>
            <button className={pestana === "proceso" ? "activa" : ""} onClick={() => setPestana("proceso")}>En proceso</button>
          </nav>
          {pestana === "candidatos" ? <Candidatos vacante={v} nombres={nombres} /> : <EnProceso vacante={v} />}
        </>
      )}
      {v.estado === "cerrada" && <EnProceso vacante={v} />}
    </div>
  );
}

function Candidatos({ vacante, nombres }) {
  const [tarjetas, setTarjetas] = useState(null);
  const [vistas, setVistas] = useState(0);
  const [mutuo, setMutuo] = useState(false);
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    setVistas(0);
    api.candidatos(vacante.id).then(setTarjetas).catch((e) => setError(e.message));
  }, [vacante.id]);
  useEffect(cargar, [cargar]);

  async function decidir(t, leInteresa) {
    setError("");
    try {
      const r = await api.deslizar("empresa", t.joven.id, vacante.id, leInteresa);
      setMutuo(r.interes_mutuo);
      setVistas((n) => n + 1);
    } catch (e) {
      setError(e.message);
    }
  }

  if (error && !tarjetas) return <p className="error">{error}</p>;
  if (!tarjetas) return <p className="centro">Buscando candidatos…</p>;
  const restantes = tarjetas.slice(vistas);
  return (
    <>
      <p className="nota centro">Los perfiles no muestran nombre, género, edad ni foto: solo lo que importa para el puesto.</p>
      {mutuo && (
        <div className="mutuo" role="status">
          <b>¡Interés mutuo!</b> A esta persona también le interesa la vacante. Un orientador revisará el match y coordinará la entrevista.
          <button className="enlace" onClick={() => setMutuo(false)}>Cerrar</button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {restantes.length === 0 ? (
        <div className="vacio">
          <p>{vistas ? "Ya revisó a todos los candidatos por ahora." : "Por ahora no hay candidatos que cumplan con esta vacante."}</p>
          <button className="boton secundario" onClick={cargar}>Actualizar</button>
        </div>
      ) : (
        <Deslizable key={restantes[0].joven.id} onDecidir={(si) => decidir(restantes[0], si)}>
          <TarjetaCandidato t={restantes[0]} nombres={nombres} />
        </Deslizable>
      )}
      {restantes.length > 1 && <p className="centro suave">{restantes.length - 1} más después de este perfil</p>}
    </>
  );
}

function TarjetaCandidato({ t, nombres }) {
  const j = t.joven, d = t.desglose;
  return (
    <article>
      <div className="tarjeta-cabeza">
        <h3>Candidato/a · {corregimiento(j.corregimiento)}</h3>
        <span className="puntaje">{Math.round(d.total * 100)}<small>/100</small>
          <Ayuda>Qué tan bien encaja, de 0 a 100: suma si sabe hacer lo que pide, qué tan fácil le queda
          llegar y cuánto le rinde el salario. Lo calcula el sistema con reglas fijas, no una IA.</Ayuda></span>
      </div>
      <p className="lugar">Disponible: {[...j.disponibilidad].map((x) => TURNOS[x]).join(", ")}</p>
      <h4>Lo que sabe hacer</h4>
      <ul className="habilidades compacta">
        {j.habilidades.map((h) => (
          <li key={h.codigo}>
            <div><b>{nombres[h.codigo] || h.codigo}</b> <span className="nivel">{NIVELES[h.nivel]}</span>
              {h.evidencia && <q>{h.evidencia}</q>}</div>
          </li>
        ))}
      </ul>
      <h4>Por qué le conviene</h4>
      <ul className="motivos">{d.motivos.map((m) => <li key={m}>{conNombres(m, nombres)}</li>)}</ul>
      <Barras desglose={d} />
    </article>
  );
}

const ESTADO_ASIG = (a) => (!a.vigente ? "cerrada" : a.aprobada === null ? "pendiente" : a.aprobada ? "aprobada" : "rechazada");
const ETIQUETAS = { aprobada: "Entrevista confirmada", pendiente: "En revisión del orientador", rechazada: "No aprobada", cerrada: "Cerrada" };

function EnProceso({ vacante }) {
  const [lista, setLista] = useState(null);
  const [retirando, setRetirando] = useState(null);
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    api.asignaciones().then((as) => setLista(as.filter((a) => a.vacante_id === vacante.id))).catch((e) => setError(e.message));
  }, [vacante.id]);
  useEffect(cargar, [cargar]);

  if (error) return <p className="error">{error}</p>;
  if (!lista) return <p className="centro">Cargando…</p>;
  if (!lista.length) return <p className="vacio">Todavía no hay personas en proceso para esta vacante.</p>;
  return (
    <ul className="lista">
      {lista.map((a) => {
        const estado = ESTADO_ASIG(a);
        return (
          <li key={a.joven_id} className={"item entrevista " + estado}>
            <div className="entrevista-cabeza">
              <div className="persona-cabeza">
                {estado === "aprobada" && <FotoPersona jovenId={a.joven_id} tamano={56} revelar />}
                <h3>Candidato/a {numeroCorto(a.joven_id)}</h3>
              </div>
              <span className={"estado-chip " + estado}>{ETIQUETAS[estado]}</span>
            </div>
            {a.entrevista && estado === "aprobada" && (
              <p>Entrevista: <b>{new Date(a.entrevista).toLocaleString("es-PA", { dateStyle: "full", timeStyle: "short", timeZone: "America/Panama" })}</b></p>
            )}
            <p className="suave">Puntaje {Math.round(a.desglose.total * 100)}/100</p>
            {estado === "cerrada" && a.motivo_cierre && <p className="suave">{a.motivo_cierre}</p>}
            {(estado === "aprobada" || estado === "pendiente") && (
              retirando === a.joven_id ? (
                <FormMotivo pregunta="¿Por qué retira a esta persona del proceso?" peligro textoBoton="Sí, retirar"
                            opciones={["Decidimos no continuar", "No cumple con el perfil", "El puesto ya se cubrió"]}
                            nota="El sistema le avisará y le buscará otra opción; el cupo queda libre."
                            onCancelar={() => setRetirando(null)}
                            onConfirmar={async (m) => { await api.retirar(a.joven_id, vacante.id, m); setRetirando(null); cargar(); }} />
              ) : (
                <button className="enlace peligro" onClick={() => setRetirando(a.joven_id)}>Retirar del proceso</button>
              )
            )}
          </li>
        );
      })}
    </ul>
  );
}
