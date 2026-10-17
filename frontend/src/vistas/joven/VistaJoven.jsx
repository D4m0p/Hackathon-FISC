import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import Ayuda from "../../componentes/Ayuda.jsx";
import Barras from "../../componentes/Barras.jsx";
import Camino from "../../componentes/Camino.jsx";
import Deslizable from "../../componentes/Deslizable.jsx";
import Guia, { guiaVista, marcarGuiaVista } from "../../componentes/Guia.jsx";
import { AGENTES, NIVELES, TURNOS, conNombres, corregimiento, dinero, enPalabras } from "../../nombres.js";
import Entrevistas from "./Entrevistas.jsx";

const PESTANAS = [["vacantes", "Vacantes"], ["casi", "Le falta poco"], ["plan", "Cursos"], ["estado", "Mi proceso"]];

const PASOS_GUIA = [
  ["👉", "Le mostramos vacantes que le quedan cerca, en su horario y que le dejan dinero después del pasaje."],
  ["❤️", "Deslice a la derecha (o toque ✓) si le interesa. A la izquierda (✕) si no."],
  ["🤝", "Si a la empresa también le interesa su perfil, una orientadora lo revisa y le agenda la entrevista."],
  ["📍", "En «Mi proceso» ve en qué paso va. Las empresas no ven su nombre, edad ni género."],
];

export default function VistaJoven({ jovenId }) {
  const [pestana, setPestana] = useState("vacantes");
  const [nombres, setNombres] = useState({});
  const [cursos, setCursos] = useState({});
  const [guia, setGuia] = useState(() => !guiaVista("joven"));

  useEffect(() => {
    api.habilidades().then((hs) => setNombres(Object.fromEntries(hs.map((h) => [h.codigo, h.nombre])))).catch(() => {});
    api.cursos().then((cs) => setCursos(Object.fromEntries(cs.map((c) => [c.id, c])))).catch(() => {});
  }, []);

  return (
    <div className="vista">
      {guia && <Guia titulo="Así funciona" pasos={PASOS_GUIA} onCerrar={() => { marcarGuiaVista("joven"); setGuia(false); }} />}
      <nav className="pestanas">
        {PESTANAS.map(([k, t]) => (
          <button key={k} className={pestana === k ? "activa" : ""} onClick={() => setPestana(k)}>{t}</button>
        ))}
      </nav>
      {pestana === "vacantes" && <Vacantes jovenId={jovenId} nombres={nombres} onGuia={() => setGuia(true)} />}
      {pestana === "casi" && <CasiCalifica jovenId={jovenId} cursos={cursos} nombres={nombres} />}
      {pestana === "plan" && <Plan jovenId={jovenId} cursos={cursos} nombres={nombres} />}
      {pestana === "estado" && <Estado jovenId={jovenId} nombres={nombres} />}
    </div>
  );
}

function useCarga(fn, deps) {
  const [estado, setEstado] = useState({ datos: null, error: "", cargando: true });
  const recargar = useCallback(() => {
    setEstado((e) => ({ ...e, cargando: true }));
    fn().then((datos) => setEstado({ datos, error: "", cargando: false }))
      .catch((e) => setEstado({ datos: null, error: e.message, cargando: false, estado: e.estado }));
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(recargar, [recargar]);
  return { ...estado, recargar };
}

function Vacantes({ jovenId, nombres, onGuia }) {
  const { datos, error, cargando, recargar } = useCarga(() => api.tarjetasJoven(jovenId), [jovenId]);
  const [vistas, setVistas] = useState(0);
  const [aviso, setAviso] = useState(null);   // {tipo: "mutuo" | "interes", titulo}
  const [errDeslizar, setErrDeslizar] = useState("");

  async function decidir(t, leInteresa) {
    setErrDeslizar("");
    try {
      const r = await api.deslizar("joven", jovenId, t.vacante.id, leInteresa);
      setAviso(r.interes_mutuo ? { tipo: "mutuo", titulo: t.vacante.titulo }
        : leInteresa ? { tipo: "interes", titulo: t.vacante.titulo } : null);
      setVistas((n) => n + 1);
    } catch (e) {
      setErrDeslizar(e.message);
    }
  }

  if (cargando) return <p className="centro">Buscando vacantes…</p>;
  if (error) return <p className="error">{error}</p>;
  const restantes = datos.slice(vistas);

  return (
    <>
      <div className="barra-ayuda">
        <span className="suave">{restantes.length ? `${restantes.length} vacante(s) para usted` : ""}</span>
        <button className="enlace" onClick={onGuia}>¿Cómo funciona?</button>
      </div>
      {aviso?.tipo === "mutuo" && (
        <div className="mutuo" role="status">
          <b>¡A la empresa también le interesa!</b> «{aviso.titulo}» quiere conocerle.
          Una orientadora lo revisará y le avisará la fecha de la entrevista. Vea «Mi proceso».
          <button className="enlace" onClick={() => setAviso(null)}>Cerrar</button>
        </div>
      )}
      {aviso?.tipo === "interes" && (
        <p className="aviso" role="status">
          Listo, guardamos que le interesa «{aviso.titulo}». Si a la empresa también le interesa, le avisamos.
        </p>
      )}
      {errDeslizar && <p className="error">{errDeslizar}</p>}
      {restantes.length === 0 ? (
        <div className="vacio">
          <p>{vistas ? "Ya revisó todas las vacantes por ahora." : "Por ahora no hay vacantes que le convengan cerca de usted."}</p>
          <p className="suave">Mire «Le falta poco»: puede que le falte una sola cosa para otras vacantes.</p>
          <button className="boton secundario" onClick={() => { setVistas(0); recargar(); }}>Buscar de nuevo</button>
        </div>
      ) : (
        <Deslizable key={restantes[0].vacante.id} onDecidir={(si) => decidir(restantes[0], si)}>
          <TarjetaVacante t={restantes[0]} nombres={nombres} />
        </Deslizable>
      )}
    </>
  );
}

function TarjetaVacante({ t, nombres }) {
  const v = t.vacante, d = t.desglose;
  const p = enPalabras(d);
  return (
    <article>
      <span className={"etiqueta-opcion " + p.nivel}>
        {p.etiqueta}
        <Ayuda>
          Lo calcula el sistema, no una persona: cuenta lo que usted ya sabe hacer, cuánto tarda en
          llegar y cuánto le queda después del pasaje. Toque «Ver cómo se calculó» para el detalle.
        </Ayuda>
      </span>
      <h3 className="titulo-vacante">{v.titulo}</h3>
      <p className="lugar">{corregimiento(v.corregimiento)} · {[...v.turnos].map((x) => TURNOS[x]).join(", ")} · {v.dias_por_semana} días a la semana</p>

      <ul className="datos-clave">
        <li><span className="icono" aria-hidden="true">💵</span>
          <span><b>{dinero(v.salario_mensual)}</b> al mes
            {p.neto !== null && <> · <b>le quedan {dinero(p.neto)}</b> después del pasaje</>}</span></li>
        {p.minutos !== null && (
          <li><span className="icono" aria-hidden="true">🕒</span>
            <span><b>{p.minutos} min</b> desde su casa{p.pasajeSemana ? ` · pasaje de ${dinero(p.pasajeSemana)} por semana` : " · sin costo de pasaje"}</span></li>
        )}
        {p.sabe.length > 0 && (
          <li><span className="icono" aria-hidden="true">✅</span>
            <span>Usted ya sabe: <b>{p.sabe.map((c) => nombres[c] || c).join(", ")}</b></span></li>
        )}
      </ul>

      <details className="por-que">
        <summary>Ver cómo se calculó</summary>
        <Barras desglose={d} />
        <ul className="motivos">{d.motivos.map((m) => <li key={m}>{conNombres(m, nombres)}</li>)}</ul>
      </details>
    </article>
  );
}

// Lo que más piden las empresas en su corregimiento, marcando lo que ya tiene.
function LoQuePiden({ jovenId, nombres }) {
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    Promise.all([api.joven(jovenId), api.tendencias(5)])
      .then(([j, t]) => setDatos({ joven: j, piden: t.por_zona[j.corregimiento] || [], nota: t.nota }))
      .catch(() => setDatos(null));
  }, [jovenId]);
  if (!datos || !datos.piden.length) return null;
  const tiene = new Set(datos.joven.habilidades.map((h) => h.codigo));
  return (
    <section className="panel piden">
      <h3>Lo que más piden las empresas cerca de usted
        <Ayuda>Cuenta cuántas vacantes publicadas en {corregimiento(datos.joven.corregimiento)} piden cada
        habilidad. {datos.nota}</Ayuda></h3>
      <ul className="lista-piden">
        {datos.piden.map((p) => (
          <li key={p.codigo} className={tiene.has(p.codigo) ? "tiene" : "falta-hab"}>
            <span>{nombres[p.codigo] || p.nombre}</span>
            <span className="suave">{p.vacantes} vacante(s)</span>
            <b>{tiene.has(p.codigo) ? "✓ Usted ya la tiene" : "Le falta"}</b>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CasiCalifica({ jovenId, cursos, nombres }) {
  const { datos, error, cargando } = useCarga(() => api.casiCalifica(jovenId), [jovenId]);
  if (cargando) return <p className="centro">Cargando…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!datos.length) return <><LoQuePiden jovenId={jovenId} nombres={nombres} /><p className="vacio">No hay vacantes a las que le falte una sola cosa.</p></>;
  return (
    <>
      <LoQuePiden jovenId={jovenId} nombres={nombres} />
      <p className="suave intro">Vacantes para las que le falta <b>una sola cosa</b>. Si es una habilidad, le decimos qué curso gratuito la cubre.</p>
      <ul className="lista">
        {datos.map((c) => (
          <li key={c.vacante_id} className="item">
            <h3>{c.titulo}</h3>
            <p className="falta">{conNombres(c.incumplimiento.detalle, nombres)}</p>
            <p>{c.sugerencia}</p>
            {c.cursos.length > 0 && (
              <p className="suave">Curso: {c.cursos.map((id) => cursos[id]?.nombre || id).join(", ")}</p>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function Plan({ jovenId, cursos, nombres }) {
  const { datos, error, cargando, estado } = useCarga(() => api.plan(jovenId), [jovenId]);
  if (cargando) return <p className="centro">Cargando…</p>;
  if (estado === 404) return <p className="vacio">No necesita cursos por ahora: ya tiene vacantes a su alcance.</p>;
  if (error) return <p className="error">{error}</p>;
  return (
    <section className="panel">
      <h2>Cursos para usted</h2>
      <p className="suave">Con estos cursos podría postularse a más vacantes. Duran {datos.semanas_total} semanas en total y cuestan {dinero(datos.costo_total)} contando el pasaje.</p>
      <ol className="ruta">
        {datos.cursos.map((id) => {
          const c = cursos[id];
          return (
            <li key={id}>
              <b>{c?.nombre || id}</b>
              {c && <span className="suave"> · {c.centro}, {corregimiento(c.corregimiento)}, {c.semanas} semanas</span>}
            </li>
          );
        })}
      </ol>
      {datos.brecha_sin_cubrir.length > 0 && (
        <p className="falta">Todavía no hay curso disponible para: {datos.brecha_sin_cubrir.map((c) => nombres[c] || c).join(", ")}</p>
      )}
      <details className="por-que">
        <summary>Por qué estos cursos</summary>
        <ul className="motivos">{datos.motivos.map((m) => <li key={m}>{conNombres(m, nombres)}</li>)}</ul>
      </details>
    </section>
  );
}

const PASOS = ["Elija vacantes", "La empresa también le elige", "Una orientadora revisa", "Entrevista agendada"];
const QUE_SIGUE = [
  "Deslice a la derecha las vacantes que le interesen.",
  "Esperamos a que alguna empresa también se interese en su perfil.",
  "Una orientadora está revisando su match. Le avisaremos la fecha.",
  "Prepárese para su entrevista. Si no puede ir, cambie la fecha abajo.",
  "¡Su entrevista está agendada! Si no puede ir, cambie la fecha abajo.",
];

// En qué paso va: entrevista > en revisión > interés mutuo > le interesó algo > nada.
function pasoActual(h) {
  const vigentes = h.asignaciones.filter((a) => a.vigente && a.aprobada !== false);
  if (vigentes.some((a) => a.aprobada)) return 4;
  if (vigentes.length) return 2;
  const si = (actor) => new Set(h.deslizamientos.filter((d) => d.actor === actor && d.le_interesa).map((d) => d.vacante_id));
  const joven = si("joven"), empresa = si("empresa");
  if ([...joven].some((v) => empresa.has(v))) return 2;
  return joven.size ? 1 : 0;
}

function Estado({ jovenId, nombres }) {
  const { datos, error, cargando, recargar } = useCarga(() => api.historia(jovenId), [jovenId]);
  if (cargando && !datos) return <p className="centro">Cargando…</p>;
  if (error) return <p className="error">{error}</p>;
  const paso = pasoActual(datos);
  return (
    <section className="panel">
      <h2>Dónde va su proceso</h2>
      <Camino pasos={PASOS} actual={paso} />
      <p className="aviso">{QUE_SIGUE[paso]}</p>
      <Entrevistas jovenId={jovenId} asignaciones={datos.asignaciones} onCambio={recargar} />
      <h4>Lo que usted sabe hacer</h4>
      <ul className="habilidades">
        {datos.joven.habilidades.map((h) => (
          <li key={h.codigo}><div><b>{nombres[h.codigo] || h.codigo}</b> <span className="nivel">{NIVELES[h.nivel]}</span>
            {h.evidencia && <q>{h.evidencia}</q>}</div></li>
        ))}
      </ul>
      <details className="por-que">
        <summary>Historial de decisiones</summary>
        <p className="nota">Cada paso que dio el sistema con su perfil, y por qué.</p>
        <ol className="linea-tiempo">
          {datos.eventos.map((e, i) => (
            <li key={i}><span className="agente">{AGENTES[e.agente] || e.agente}</span> {conNombres(e.motivo, nombres)}</li>
          ))}
        </ol>
      </details>
    </section>
  );
}
