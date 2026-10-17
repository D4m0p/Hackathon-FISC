import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import Ayuda from "../../componentes/Ayuda.jsx";
import FormMotivo from "../../componentes/FormMotivo.jsx";
import Guia, { guiaVista, marcarGuiaVista } from "../../componentes/Guia.jsx";
import { TURNOS, corregimiento, dinero, etiquetaJoven, numeroCorto } from "../../nombres.js";

const PASOS_GUIA = [
  ["📚", "Aquí ve sus cursos, cuántos cupos le quedan y qué jóvenes del sistema los necesitan."],
  ["🎯", "El sistema los ordena: primero quienes pueden asistir, y entre ellos a quien el curso le abre más vacantes de trabajo."],
  ["✅", "Usted decide a quién reservarle el cupo. El joven recibe un aviso y lo ve en su cuenta."],
];

function fecha(iso) {
  return new Date(iso).toLocaleDateString("es-PA", { day: "numeric", month: "long", timeZone: "America/Panama" });
}

export default function VistaCentro({ centro }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);   // {mensaje, pendiente}
  const [aviso, setAviso] = useState("");
  const [guia, setGuia] = useState(() => !guiaVista("centro"));

  const cargar = useCallback(() => {
    api.demandaCentro(centro).then(setDatos)
      .catch((e) => setError({ mensaje: e.message, pendiente: e.estado === 404 || e.estado === 405 }));
  }, [centro]);
  useEffect(cargar, [cargar]);

  if (error?.pendiente)
    return <p className="vacio">La vista de centros todavía no está conectada a la API. Vuelva a intentarlo cuando esté lista.</p>;
  if (error) return <p className="error">{error.mensaje}</p>;
  if (!datos) return <p className="centro">Cargando…</p>;

  const cupos = datos.reduce((s, d) => s + d.curso.cupos_disponibles, 0);
  const interesados = new Set(datos.flatMap((d) => d.interesados.map((i) => i.joven_id))).size;

  return (
    <div className="vista">
      {guia && <Guia titulo={`Así funciona para ${centro}`} pasos={PASOS_GUIA}
                     onCerrar={() => { marcarGuiaVista("centro"); setGuia(false); }} />}
      <div className="barra-ayuda">
        <h2>{centro} · Mis cursos</h2>
        <button className="enlace" onClick={() => setGuia(true)}>¿Cómo funciona?</button>
      </div>
      <div className="resumen-centro">
        <div><b>{datos.length}</b><span>cursos</span></div>
        <div><b>{cupos}</b><span>cupos libres</span></div>
        <div><b>{interesados}</b><span>jóvenes que los necesitan</span></div>
      </div>
      {aviso && <p className="aviso" role="status">{aviso}</p>}
      <ul className="lista">
        {[...datos].sort((a, b) => b.interesados.length - a.interesados.length)
          .map((d) => <Curso key={d.curso.id} d={d} onReservado={(m) => { setAviso(m); cargar(); window.scrollTo(0, 0); }} />)}
      </ul>
    </div>
  );
}

function Curso({ d, onReservado }) {
  const c = d.curso;
  const [abierto, setAbierto] = useState(null);   // joven_id con el formulario abierto
  const [todos, setTodos] = useState(false);
  const VISIBLES = 3;
  const escasez = d.interesados.length > c.cupos_disponibles;
  const vacantes = new Set(d.interesados.flatMap((i) => i.vacantes_que_abre.map((v) => v.vacante_id))).size;

  return (
    <li className="item curso">
      <div className="entrevista-cabeza">
        <h3>{c.nombre}</h3>
        <span className={"estado-chip " + (c.cupos_disponibles ? "publicada" : "cerrada")}>
          {c.cupos_disponibles ? `${c.cupos_disponibles} cupo(s)` : "Sin cupos"}
        </span>
      </div>
      <p className="suave">
        {corregimiento(c.corregimiento)} · {[...c.turnos].map((t) => TURNOS[t]).join(", ")} · {c.semanas} semanas
        {c.costo ? ` · ${dinero(c.costo)}` : " · gratuito"}
      </p>
      <p>
        <b>{d.interesados.length}</b> joven(es) lo necesitan
        {vacantes > 0 && <> · abriría <b>{vacantes}</b> vacante(s) de trabajo</>}
      </p>
      {escasez && c.cupos_disponibles > 0 && (
        <p className="aviso alerta">Hay más interesados que cupos: el orden de abajo le ayuda a decidir.</p>
      )}
      {c.cupos_disponibles === 0 && d.interesados.length > 0 && (
        <p className="aviso">Sin cupos: estos jóvenes quedan en lista de espera, en este orden.</p>
      )}

      {d.interesados.length > 0 && (
        <ol className="interesados">
          {(todos ? d.interesados : d.interesados.slice(0, VISIBLES)).map((i, n) => (
            <li key={i.joven_id} className={n === 0 ? "primero" : ""}>
              <div className="interesado-cabeza">
                <b>{etiquetaJoven(i.joven_id, { [i.joven_id]: i })}</b>
                {i.en_plan && <span className="nivel">En su plan de cursos</span>}
                {!i.cabe_en_horario && <span className="nivel aviso-chip">Choca con su horario</span>}
              </div>
              <p>{i.motivo}</p>
              {i.vacantes_que_abre.length > 0 && (
                <p className="suave">Le abre: {i.vacantes_que_abre.map((v) => v.titulo).join(", ")}</p>
              )}
              {abierto === i.joven_id ? (
                <FormMotivo pregunta="¿Por qué le reserva el cupo?" textoBoton="Reservar cupo"
                            opciones={["Es quien más vacantes abre", "Le queda cerca", "Lo pidió en el centro"]}
                            nota="Se descuenta un cupo y el joven recibe un aviso."
                            onCancelar={() => setAbierto(null)}
                            onConfirmar={async (m) => {
                              await api.reservarCupo(c.id, i.joven_id, m);
                              setAbierto(null);
                              onReservado(`Cupo reservado en «${c.nombre}» para ${etiquetaJoven(i.joven_id, { [i.joven_id]: i })}. Se le avisó.`);
                            }} />
              ) : c.cupos_disponibles > 0 && (
                <button className={n === 0 ? "boton" : "boton secundario"}
                        onClick={() => setAbierto(i.joven_id)}>Reservar cupo</button>
              )}
            </li>
          ))}
        </ol>
      )}
      {d.interesados.length > VISIBLES && (
        <button className="enlace" onClick={() => setTodos(!todos)}>
          {todos ? "Ver menos" : `Ver los otros ${d.interesados.length - VISIBLES}`}
        </button>
      )}
      {d.interesados.length > 1 && (
        <p className="nota">
          Orden del sistema <Ayuda>Primero quienes pueden asistir (le cabe en su horario y llega a tiempo); entre ellos, a quien
          el curso le abre más vacantes, a quien lo tiene en su plan y a quien le queda más cerca. Es un cálculo fijo, no una IA. Usted decide a quién reservar.</Ayuda>
        </p>
      )}
      {d.reservas.length > 0 && (
        <p className="suave">Reservados: {d.reservas.map((r) => `${numeroCorto(r.joven_id)} (${fecha(r.fecha)})`).join(", ")}</p>
      )}
    </li>
  );
}
