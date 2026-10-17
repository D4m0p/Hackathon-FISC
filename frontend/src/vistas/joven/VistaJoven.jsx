import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import Ayuda from "../../componentes/Ayuda.jsx";
import Barras from "../../componentes/Barras.jsx";
import BarrasH from "../../componentes/BarrasH.jsx";
import Camino from "../../componentes/Camino.jsx";
import Contador from "../../componentes/Contador.jsx";
import Deslizable from "../../componentes/Deslizable.jsx";
import Guia, { guiaVista, marcarGuiaVista } from "../../componentes/Guia.jsx";
import LogoEmpresa from "../../componentes/LogoEmpresa.jsx";
import MapaPanama from "../../componentes/MapaPanama.jsx";
import { AGENTES, NIVELES, TURNOS, conNombres, corregimiento, dinero, enPalabras, nombreEmpresa } from "../../nombres.js";
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
      {pestana === "vacantes" && <Vacantes jovenId={jovenId} nombres={nombres} onGuia={() => setGuia(true)} onIr={setPestana} />}
      {pestana !== "vacantes" && (
        <div className="joven-angosta">
          {pestana === "casi" && <CasiCalifica jovenId={jovenId} cursos={cursos} nombres={nombres} />}
          {pestana === "plan" && <Plan jovenId={jovenId} cursos={cursos} nombres={nombres} />}
          {pestana === "estado" && <Estado jovenId={jovenId} nombres={nombres} />}
        </div>
      )}
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

function Vacantes({ jovenId, nombres, onGuia, onIr }) {
  const { datos, error, cargando, recargar } = useCarga(() => api.tarjetasJoven(jovenId), [jovenId]);
  const resumen = useResumen(jovenId);
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
    <div className="joven-grilla">
    <div className="joven-principal">
      <div className="barra-ayuda">
        <span className="suave">{restantes.length ? `${restantes.length} vacante(s) para usted` : ""}</span>
        <button className="enlace" onClick={onGuia}>¿Cómo funciona?</button>
      </div>
      <Ahorro datos={resumen} />
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
    </div>
    <PanelJoven jovenId={jovenId} datos={resumen} tarjetas={datos} nombres={nombres} onIr={onIr} />
    </div>
  );
}

const AMBAR = "#f2b84b", GRIS = "#94a9b9";

// Lo que el panel necesita, una sola vez para el resumen, el mapa y las cifras.
function useResumen(jovenId) {
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    Promise.all([api.impactoJoven(jovenId), api.vacantes(), api.casiCalifica(jovenId), api.historia(jovenId)])
      .then(([impacto, vacantes, casi, historia]) => setDatos({ impacto, vacantes, casi, historia }))
      .catch(() => setDatos(null));
  }, [jovenId]);
  return datos;
}

function Ahorro({ datos }) {
  if (!datos) return null;
  const i = datos.impacto;
  const otras = i.publicadas - i.viables;
  if (otras <= 0) return null;
  return (
    <p className="ahorro">
      {i.viables > 0 ? (
        <>De <b>{i.publicadas}</b> vacantes publicadas, <b>{i.viables} le sirven</b>.
          Le ahorramos <b>{otras}</b> postulaciones que no le convenían.</>
      ) : (
        <>Ninguna de las <b>{i.publicadas}</b> vacantes publicadas le sirve todavía.
          Mire «Le falta poco» y «Cursos»: le decimos qué le falta y cómo conseguirlo.</>
      )}
    </p>
  );
}

// Panel al costado (abajo en celular), con el mismo estilo del Panorama del orientador:
// cifras, mapa, por qué no le sirven las demás y lo que piden cerca. Solo muestra lo que ya
// decidió el Matching.
function PanelJoven({ jovenId, datos, tarjetas, nombres, onIr }) {
  if (!datos) return <aside className="joven-panel" />;
  const i = datos.impacto;
  const enProceso = datos.historia.asignaciones.filter((a) => a.vigente && a.aprobada !== false).length;
  const cursosQueAbren = new Set(datos.casi.flatMap((c) => c.cursos)).size;
  const kpis = [
    ["Le sirven", i.viables, "cerca, en su horario y le dejan dinero", "vacantes"],
    ["Le falta poco", datos.casi.length, "les falta una sola cosa", "casi"],
    ["Cursos útiles", cursosQueAbren, "gratuitos, para lo que le falta", "plan"],
    ["En proceso", enProceso, "con interés mutuo o entrevista", "estado"],
  ];

  // Una burbuja por corregimiento: aqua si alguna vacante le sirve, ámbar si le falta una sola cosa.
  const minutos = Object.fromEntries(tarjetas.map((t) => [t.vacante.id, enPalabras(t.desglose).minutos]));
  const sirve = new Set([...tarjetas.map((t) => t.vacante.id),
    ...datos.historia.deslizamientos.filter((d) => d.actor === "joven").map((d) => d.vacante_id)]);
  const casi = Object.fromEntries(datos.casi.map((c) => [c.vacante_id, c.incumplimiento.detalle]));
  const zonas = {};
  for (const v of datos.vacantes) {
    const z = (zonas[v.corregimiento] ||= { sirve: 0, casi: 0, lineas: [] });
    if (sirve.has(v.id)) { z.sirve++; z.lineas.push(`✓ ${v.titulo}${minutos[v.id] != null ? ` · ${minutos[v.id]} min` : ""}`); }
    else if (casi[v.id]) { z.casi++; z.lineas.push(`◐ ${v.titulo}: ${conNombres(casi[v.id], nombres)}`); }
    else z.lineas.push(`✕ ${v.titulo}: no encaja en varias cosas`);
  }
  const puntos = Object.entries(zonas).map(([codigo, z]) => ({
    codigo, radio: 6 + z.lineas.length * 3, color: z.sirve ? "var(--aqua)" : z.casi ? AMBAR : GRIS, lineas: z.lineas,
  }));
  const motivos = MOTIVOS_PANEL.filter(([k]) => i.descartes[k] > 0);

  return (
    <aside className="joven-panel">
      <div className="kpis joven-kpis">
        {kpis.map(([titulo, valor, sub, ir]) => (
          <button key={titulo} className="kpi enlazable" onClick={() => onIr(ir)}>
            <span className="kpi-titulo">{titulo}</span>
            <b className="kpi-valor"><Contador valor={valor} /></b>
            <span className="kpi-sub">{sub}</span>
          </button>
        ))}
      </div>

      <section className="panel-oscuro mapa-joven">
        <div className="panel-cabeza"><h3>Dónde están las vacantes</h3></div>
        <MapaPanama puntos={puntos} casa={datos.historia.joven.corregimiento}
                    leyenda={<><i className="punto aqua" /> le sirve <i className="punto ambar" /> le falta una cosa <i className="punto lejos" /> no encaja · la casita es usted</>} />
        <p className="nota">Toque una burbuja para ver qué vacantes hay ahí.</p>
      </section>

      {motivos.length > 0 && (
        <section className="panel">
          <h3>¿Por qué no le mostramos las otras {i.publicadas - i.viables}?
            <Ayuda>Lo decide el Matching con reglas fijas: distancia, pasaje, horario, salario y
            habilidades. Una vacante puede fallar en más de una cosa, por eso la suma puede ser mayor.</Ayuda></h3>
          <BarrasH filas={motivos.map(([k, etiqueta]) => ({
            clave: k, etiqueta, valor: i.descartes[k], color: k === "traslado" || k === "presupuesto" ? AMBAR : "var(--celeste)" }))} />
          <p className="nota">Un portal común le mostraría las {i.publicadas}; aquí solo ve las que le convienen.</p>
        </section>
      )}

      <LoQuePiden jovenId={jovenId} nombres={nombres} />
    </aside>
  );
}

const MOTIVOS_PANEL = [
  ["traslado", "Le queda muy lejos"], ["presupuesto", "El pasaje no le alcanza"], ["horario", "No coincide con su horario"],
  ["salario", "Paga menos de lo que pide"], ["habilidad", "Le falta una habilidad"], ["sin_datos", "Sin datos de cómo llegar"],
];

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
      <div className="cabeza-vacante">
        <LogoEmpresa empresaId={v.empresa_id} />
        <div>
          <h3 className="titulo-vacante">{v.titulo}</h3>
          <p className="nombre-empresa">{nombreEmpresa(v.empresa_id)}</p>
        </div>
      </div>
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

// Cupos que un centro de formación le reservó (vienen en la historia, si la API los envía).
function Reservas({ jovenId, cursos }) {
  const [reservas, setReservas] = useState([]);
  useEffect(() => { api.historia(jovenId).then((h) => setReservas(h.reservas || [])).catch(() => {}); }, [jovenId]);
  if (!reservas.length) return null;
  return (
    <div className="reservas-joven">
      {reservas.map((r) => {
        const c = cursos[r.curso_id];
        return (
          <p key={r.curso_id} className="aviso ok">
            ✓ <b>Tiene un cupo reservado</b> en «{c?.nombre || r.curso_id}»
            {c && <> · {c.centro}, {corregimiento(c.corregimiento)}</>}. El centro le contactará para empezar.
          </p>
        );
      })}
    </div>
  );
}

function Plan({ jovenId, cursos, nombres }) {
  const { datos, error, cargando, estado } = useCarga(() => api.plan(jovenId), [jovenId]);
  if (cargando) return <p className="centro">Cargando…</p>;
  if (estado === 404) return <><Reservas jovenId={jovenId} cursos={cursos} /><p className="vacio">No necesita cursos por ahora: ya tiene vacantes a su alcance.</p></>;
  if (error) return <p className="error">{error}</p>;
  return (
    <section className="panel">
      <Reservas jovenId={jovenId} cursos={cursos} />
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
