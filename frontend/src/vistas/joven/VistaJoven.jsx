import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import Barras from "../../componentes/Barras.jsx";
import Deslizable from "../../componentes/Deslizable.jsx";
import { NIVELES, TURNOS, conNombres, corregimiento, dinero } from "../../nombres.js";

const PESTANAS = [["vacantes", "Vacantes"], ["casi", "Casi califica"], ["plan", "Mi plan"], ["estado", "Mi estado"]];

export default function VistaJoven({ jovenId }) {
  const [pestana, setPestana] = useState("vacantes");
  const [nombres, setNombres] = useState({});
  const [cursos, setCursos] = useState({});

  useEffect(() => {
    api.habilidades().then((hs) => setNombres(Object.fromEntries(hs.map((h) => [h.codigo, h.nombre])))).catch(() => {});
    api.cursos().then((cs) => setCursos(Object.fromEntries(cs.map((c) => [c.id, c])))).catch(() => {});
  }, []);

  return (
    <div className="vista">
      <nav className="pestanas">
        {PESTANAS.map(([k, t]) => (
          <button key={k} className={pestana === k ? "activa" : ""} onClick={() => setPestana(k)}>{t}</button>
        ))}
      </nav>
      {pestana === "vacantes" && <Vacantes jovenId={jovenId} nombres={nombres} />}
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

function Vacantes({ jovenId, nombres }) {
  const { datos, error, cargando, recargar } = useCarga(() => api.tarjetasJoven(jovenId), [jovenId]);
  const [vistas, setVistas] = useState(0);
  const [mutuo, setMutuo] = useState(null);
  const [errDeslizar, setErrDeslizar] = useState("");

  async function decidir(t, leInteresa) {
    setErrDeslizar("");
    try {
      const r = await api.deslizar("joven", jovenId, t.vacante.id, leInteresa);
      if (r.interes_mutuo) setMutuo(t.vacante);
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
      {mutuo && (
        <div className="mutuo" role="status">
          <b>¡Interés mutuo!</b> A «{mutuo.titulo}» también le interesa su perfil.
          Un orientador revisará el match y le avisará la fecha de entrevista.
          <button className="enlace" onClick={() => setMutuo(null)}>Cerrar</button>
        </div>
      )}
      {errDeslizar && <p className="error">{errDeslizar}</p>}
      {restantes.length === 0 ? (
        <div className="vacio">
          <p>{vistas ? "Ya revisó todas las vacantes por ahora." : "Por ahora no hay vacantes que le convengan cerca de usted."}</p>
          <p className="suave">Revise «Casi califica»: puede que le falte una sola cosa para otras vacantes.</p>
          <button className="boton secundario" onClick={() => { setVistas(0); recargar(); }}>Actualizar</button>
        </div>
      ) : (
        <Deslizable key={restantes[0].vacante.id} onDecidir={(si) => decidir(restantes[0], si)}>
          <TarjetaVacante t={restantes[0]} nombres={nombres} />
        </Deslizable>
      )}
      {restantes.length > 1 && <p className="centro suave">{restantes.length - 1} más después de esta</p>}
    </>
  );
}

function TarjetaVacante({ t, nombres }) {
  const v = t.vacante, d = t.desglose;
  return (
    <article>
      <div className="tarjeta-cabeza">
        <h3>{v.titulo}</h3>
        <span className="puntaje">{Math.round(d.total * 100)}<small>/100</small></span>
      </div>
      <p className="lugar">{corregimiento(v.corregimiento)} · {[...v.turnos].map((x) => TURNOS[x]).join(", ")} · {v.dias_por_semana} días</p>
      <p className="salario">{dinero(v.salario_mensual)} <small>al mes</small></p>
      <h4>Por qué le aparece</h4>
      <ul className="motivos">
        {d.motivos.map((m) => <li key={m}>{conNombres(m, nombres)}</li>)}
      </ul>
      <Barras desglose={d} />
    </article>
  );
}

function CasiCalifica({ jovenId, cursos, nombres }) {
  const { datos, error, cargando } = useCarga(() => api.casiCalifica(jovenId), [jovenId]);
  if (cargando) return <p className="centro">Cargando…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!datos.length) return <p className="vacio">No hay vacantes a las que le falte una sola cosa.</p>;
  return (
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
  );
}

function Plan({ jovenId, cursos, nombres }) {
  const { datos, error, cargando, estado } = useCarga(() => api.plan(jovenId), [jovenId]);
  if (cargando) return <p className="centro">Cargando…</p>;
  if (estado === 404) return <p className="vacio">No tiene plan de formación: ya tiene vacantes a su alcance.</p>;
  if (error) return <p className="error">{error}</p>;
  return (
    <section className="panel">
      <h2>Su ruta de formación</h2>
      <p className="suave">{datos.semanas_total} semanas · {dinero(datos.costo_total)} con transporte</p>
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
        <p className="falta">Sin curso disponible para: {datos.brecha_sin_cubrir.map((c) => nombres[c] || c).join(", ")}</p>
      )}
      <ul className="motivos">{datos.motivos.map((m) => <li key={m}>{conNombres(m, nombres)}</li>)}</ul>
    </section>
  );
}

function Estado({ jovenId, nombres }) {
  const { datos, error, cargando } = useCarga(() => api.historia(jovenId), [jovenId]);
  if (cargando) return <p className="centro">Cargando…</p>;
  if (error) return <p className="error">{error}</p>;
  return (
    <section className="panel">
      <h2>Dónde está su proceso</h2>
      <p className="aviso">{datos.estado}</p>
      <h4>Sus habilidades</h4>
      <ul className="habilidades">
        {datos.joven.habilidades.map((h) => (
          <li key={h.codigo}><div><b>{nombres[h.codigo] || h.codigo}</b> <span className="nivel">{NIVELES[h.nivel]}</span>
            {h.evidencia && <q>{h.evidencia}</q>}</div></li>
        ))}
      </ul>
      <h4>Qué decidió el sistema</h4>
      <ol className="linea-tiempo">
        {datos.eventos.map((e, i) => (
          <li key={i}><span className="agente">{e.agente}</span> {conNombres(e.motivo, nombres)}</li>
        ))}
      </ol>
    </section>
  );
}
