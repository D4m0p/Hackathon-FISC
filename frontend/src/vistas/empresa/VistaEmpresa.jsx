import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import BarrasH from "../../componentes/BarrasH.jsx";
import Contador from "../../componentes/Contador.jsx";
import Guia, { guiaVista, marcarGuiaVista } from "../../componentes/Guia.jsx";
import LogoEmpresa from "../../componentes/LogoEmpresa.jsx";
import MapaPanama from "../../componentes/MapaPanama.jsx";
import { TURNOS, corregimiento, dinero, nombreEmpresa } from "../../nombres.js";
import DetalleVacante from "./DetalleVacante.jsx";
import FormVacante from "./FormVacante.jsx";
import Hallazgos from "./Hallazgos.jsx";

const ESTADOS = { publicada: "Publicada", bloqueada: "Bloqueada", cerrada: "Cerrada", borrador: "Borrador" };
const PASOS_GUIA = [
  ["📝", "Publique una vacante con el formulario o pegue la oferta como la escribiría en redes."],
  ["🛡️", "Antes de publicarse, el sistema revisa que no pida edad, género, apariencia u otros requisitos que discriminen. Si encuentra algo, le dice qué cambiar."],
  ["👉", "Vea candidatos que cumplen y que pueden llegar a tiempo. No verá su nombre, edad ni género: solo lo que saben hacer."],
  ["🤝", "Si a usted y al candidato les interesa, una orientadora coordina la entrevista."],
];

const FALTANTES = {
  corregimiento: "dónde queda el trabajo", salario_mensual: "el salario mensual", turnos: "el horario (mañana, tarde…)",
  titulo: "el nombre del puesto", habilidades_requeridas: "qué debe saber hacer",
};

export default function VistaEmpresa({ empresaId }) {
  // pantalla: lista | nueva | texto | detalle | editar | resultado
  const [pantalla, setPantalla] = useState({ tipo: "lista" });
  const [vacantes, setVacantes] = useState(null);
  const [nombres, setNombres] = useState({});
  const [error, setError] = useState("");
  const [guia, setGuia] = useState(() => !guiaVista("empresa"));

  useEffect(() => {
    api.habilidades().then((hs) => setNombres(Object.fromEntries(hs.map((h) => [h.codigo, h.nombre])))).catch(() => {});
  }, []);

  const cargar = useCallback(() => {
    api.vacantes()
      .then((vs) => setVacantes(vs.filter((v) => v.empresa_id === empresaId)))
      .catch((e) => setError(e.message));
  }, [empresaId]);
  useEffect(cargar, [cargar]);

  // Candidatos por vacante publicada, asignaciones y tendencias: se piden una sola vez y se reparten.
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    if (!vacantes) return;
    const publicadas = vacantes.filter((v) => v.estado === "publicada");
    Promise.all([
      Promise.all(publicadas.map((v) => api.candidatos(v.id).catch(() => []))),
      api.asignaciones().catch(() => []),
      api.tendencias(5).catch(() => null),
    ]).then(([listas, asig, tend]) => setDatos({
      listas: Object.fromEntries(publicadas.map((v, i) => [v.id, listas[i]])), asig, tend,
    }));
  }, [vacantes]);
  useEffect(() => { window.scrollTo(0, 0); }, [pantalla]);

  function publicada(resultado) {
    cargar();
    setPantalla({ tipo: "resultado", resultado });
  }

  const volver = () => { cargar(); setPantalla({ tipo: "lista" }); };

  if (pantalla.tipo === "nueva")
    return <FormVacante empresaId={empresaId} onPublicada={publicada} onCancelar={volver} />;
  if (pantalla.tipo === "editar")
    return <FormVacante empresaId={empresaId} inicial={pantalla.vacante} onPublicada={publicada}
                        onCancelar={() => setPantalla({ tipo: "detalle", id: pantalla.vacante.id })} />;
  if (pantalla.tipo === "texto")
    return <OfertaTexto empresaId={empresaId} onPublicada={publicada} onCancelar={volver}
                        onFormulario={(texto) => setPantalla({ tipo: "editar", vacante: { texto_original: texto, turnos: [] } })} />;
  if (pantalla.tipo === "resultado") {
    const { vacante, auditoria } = pantalla.resultado;
    return (
      <section className="panel">
        <h2>{vacante.titulo}</h2>
        <p className="suave">
          {corregimiento(vacante.corregimiento)} · {[...vacante.turnos].map((t) => TURNOS[t]).join(", ")} ·{" "}
          {dinero(vacante.salario_mensual)} al mes · {vacante.cupos} cupo(s)
        </p>
        {vacante.habilidades_requeridas.length > 0 && (
          <p>Pide: {vacante.habilidades_requeridas.map((r) => nombres[r.codigo] || r.codigo).join(", ")}</p>
        )}
        <Hallazgos auditoria={auditoria} />
        <div className="acciones">
          <button className="enlace" onClick={volver}>Ir a mis vacantes</button>
          {auditoria.aprobado
            ? <button className="boton" onClick={() => setPantalla({ tipo: "detalle", id: vacante.id })}>Ver candidatos</button>
            : <button className="boton" onClick={() => setPantalla({ tipo: "editar", vacante })}>Corregir la vacante</button>}
        </div>
      </section>
    );
  }
  if (pantalla.tipo === "detalle") {
    const v = vacantes?.find((x) => x.id === pantalla.id);
    if (v) return <DetalleVacante vacante={v} onVolver={volver} onEditar={() => setPantalla({ tipo: "editar", vacante: v })}
                                  onRevisada={publicada} onCambio={cargar} />;
  }

  if (error) return <p className="error">{error}</p>;
  if (!vacantes) return <p className="centro">Cargando…</p>;
  const orden = { bloqueada: 0, publicada: 1, borrador: 2, cerrada: 3 };
  return (
    <div className="vista">
      {guia && <Guia titulo="Así funciona para su empresa" pasos={PASOS_GUIA}
                     onCerrar={() => { marcarGuiaVista("empresa"); setGuia(false); }} />}
      <div className="barra-ayuda">
        <span className="cabeza-vacante"><LogoEmpresa empresaId={empresaId} tamano={36} /><b>{nombreEmpresa(empresaId)}</b></span>
        <button className="enlace" onClick={() => setGuia(true)}>¿Cómo funciona?</button>
      </div>
      <ResumenEmpresa vacantes={vacantes} datos={datos} />
      <TableroEmpresa vacantes={vacantes} datos={datos} nombres={nombres} />
      <div className="opciones">
        <button className="opcion" onClick={() => setPantalla({ tipo: "nueva" })}>
          <b>Publicar vacante</b><span>Con un formulario</span>
        </button>
        <button className="opcion" onClick={() => setPantalla({ tipo: "texto" })}>
          <b>Pegar una oferta</b><span>Texto libre, el sistema la ordena</span>
        </button>
      </div>
      <h4>Mis vacantes</h4>
      {vacantes.length === 0 && <p className="vacio">Todavía no tiene vacantes.</p>}
      <ul className="lista">
        {[...vacantes].sort((a, b) => orden[a.estado] - orden[b.estado]).map((v) => {
          const av = avanceVacante(v, datos);
          return (
          <li key={v.id}>
            <button className={"item fila-vacante " + v.estado} onClick={() => setPantalla({ tipo: "detalle", id: v.id })}>
              <div>
                <h3>{v.titulo}</h3>
                <p className="suave">{corregimiento(v.corregimiento)} · {dinero(v.salario_mensual)} · {v.cupos} cupo(s)</p>
              </div>
              <span className={"estado-chip " + v.estado}>{ESTADOS[v.estado]}</span>
            </button>
            {av && (
              <div className="emp-avance">
                <span className="emp-avance-pista" aria-hidden="true">
                  <span className="emp-avance-aprobados" style={{ width: `${(av.aprobados / Math.max(1, av.candidatos + av.proceso + av.aprobados)) * 100}%` }} />
                  <span className="emp-avance-proceso" style={{ width: `${(av.proceso / Math.max(1, av.candidatos + av.proceso + av.aprobados)) * 100}%` }} />
                </span>
                <span className="emp-avance-texto">{av.candidatos} por revisar · {av.proceso} en proceso · {av.aprobados} {av.aprobados === 1 ? "aprobado" : "aprobados"}</span>
              </div>
            )}
          </li>
          );
        })}
      </ul>
    </div>
  );
}

function OfertaTexto({ empresaId, onPublicada, onCancelar, onFormulario }) {
  const [texto, setTexto] = useState("");
  const [error, setError] = useState(null);   // {mensaje, sinMercado}
  const [enviando, setEnviando] = useState(false);
  const [leyendo, setLeyendo] = useState(false);
  const [deFoto, setDeFoto] = useState(false);

  // Foto del volante → texto que la empresa revisa antes de publicar (Mercado lo estructura después).
  async function leerFoto(archivo) {
    if (!archivo) return;
    if (archivo.size > 4 * 1024 * 1024) return setError({ mensaje: "La foto supera 4 MB." });
    setLeyendo(true);
    setError(null);
    try {
      const b64 = await new Promise((ok, falla) => {
        const r = new FileReader();
        r.onload = () => ok(String(r.result).split(",")[1]);
        r.onerror = () => falla(new Error("No se pudo leer la foto"));
        r.readAsDataURL(archivo);
      });
      const r = await api.transcribir("imagen", b64, archivo.type, "oferta");
      setTexto(r.texto.slice(0, 5000));
      setDeFoto(true);
    } catch (err) {
      setError({ mensaje: err.message });
    }
    setLeyendo(false);
  }

  async function enviar(e) {
    e.preventDefault();
    if (texto.trim().length < 10) return setError({ mensaje: "Escriba la oferta completa." });
    setEnviando(true);
    setError(null);
    try {
      onPublicada(await api.publicarOferta(texto.trim(), empresaId));
    } catch (err) {
      setError({ mensaje: err.message, sinMercado: err.estado === 501, faltantes: err.cuerpo?.faltantes });
      setEnviando(false);
    }
  }

  const faltan = error?.faltantes?.map((c) => FALTANTES[c] || c.replace(/_/g, " "));

  return (
    <form className="panel" onSubmit={enviar}>
      <h2>Pegar una oferta</h2>
      <p className="suave">Pegue el anuncio, el mensaje de WhatsApp o suba una foto del volante. El sistema saca el puesto, el horario, el salario y las habilidades.</p>
      <label className={"boton secundario subir-foto" + (leyendo ? " deshabilitado" : "")}>
        <input type="file" accept="image/jpeg,image/png,image/webp" disabled={leyendo}
               onChange={(e) => { const f = e.target.files[0]; e.target.value = ""; leerFoto(f); }} />
        📷 {leyendo ? "Leyendo la foto…" : "Subir foto del volante"}
      </label>
      <textarea rows="8" maxLength="5000" value={texto} onChange={(e) => setTexto(e.target.value)}
                placeholder="Ej.: Se busca cajero/a para supermercado en Arraiján, turno de mañana, B/. 650 al mes…" />
      {deFoto && <p className="nota">Este es el texto que leímos de la foto. Revíselo y corrija lo que haga falta antes de publicar.</p>}
      {error && (faltan?.length ? (
        <div className="aviso alerta">
          <p><b>A la oferta le falta información para publicarla:</b> {faltan.join(", ")}.</p>
          <p>Agréguela al texto y vuelva a publicar, o complete el formulario.</p>
          <button type="button" className="boton secundario" onClick={() => onFormulario(texto)}>Completar en el formulario</button>
        </div>
      ) : (
        <div className="error">
          {error.sinMercado ? "La lectura automática de ofertas todavía no está disponible." : error.mensaje}
          {error.sinMercado && (
            <p><button type="button" className="boton secundario" onClick={() => onFormulario(texto)}>Usar el formulario con este texto</button></p>
          )}
        </div>
      ))}
      <div className="acciones">
        <button type="button" className="enlace" onClick={onCancelar}>Cancelar</button>
        <button className="boton" disabled={enviando}>{enviando ? "Leyendo…" : "Publicar"}</button>
      </div>
    </form>
  );
}

// Candidatos, en proceso (pendientes) y aprobados de una vacante publicada; null mientras no hay datos.
function avanceVacante(v, datos) {
  const lista = datos?.listas[v.id];
  if (!lista) return null;
  const mias = datos.asig.filter((a) => a.vacante_id === v.id && a.vigente === true);
  return {
    candidatos: lista.length,
    proceso: mias.filter((a) => a.aprobada === null).length,
    aprobados: mias.filter((a) => a.aprobada === true).length,
  };
}

// Cifras de la empresa: vacantes publicadas, candidatos por revisar y personas en proceso.
function ResumenEmpresa({ vacantes, datos }) {
  const publicadas = vacantes.filter((v) => v.estado === "publicada");
  const bloqueadas = vacantes.filter((v) => v.estado === "bloqueada").length;
  const candidatos = datos ? Object.values(datos.listas).reduce((s, l) => s + l.length, 0) : 0;
  const proceso = datos ? datos.asig.filter((a) => a.vigente && a.aprobada !== false).length : 0;
  const kpis = [
    ["Vacantes publicadas", publicadas.length, bloqueadas ? `${bloqueadas} bloqueada(s) por corregir` : "todas revisadas por el Auditor"],
    ["Candidatos por revisar", candidatos, "cumplen y pueden llegar a tiempo"],
    ["Personas en proceso", proceso, "en revisión o con entrevista"],
  ];
  return (
    <div className="kpis tres">
      {kpis.map(([titulo, valor, sub]) => (
        <div key={titulo} className="kpi"><span className="kpi-titulo">{titulo}</span>
          <b className="kpi-valor"><Contador valor={valor} /></b><span className="kpi-sub">{sub}</span></div>
      ))}
    </div>
  );
}

// Mapa de vacantes y candidatos, habilidades de los candidatos y lo que piden otras empresas en la zona.
// Un solo punto por corregimiento (el mapa identifica los puntos por su corregimiento).
function TableroEmpresa({ vacantes, datos, nombres }) {
  const [zona, setZona] = useState(null);
  const publicadas = vacantes.filter((v) => v.estado === "publicada");
  if (!publicadas.length || !datos) return null;

  const candidatos = Object.values(datos.listas).flat().map((t) => t.joven);
  const pedidas = new Set(publicadas.flatMap((v) => v.habilidades_requeridas.map((r) => r.codigo)));
  const zonas = [...new Set([...publicadas.map((v) => v.corregimiento), ...candidatos.map((j) => j.corregimiento)])];
  const puntos = zonas.map((z) => {
    const vs = publicadas.filter((v) => v.corregimiento === z);
    const cupos = vs.reduce((s, v) => s + v.cupos, 0);
    const n = candidatos.filter((j) => j.corregimiento === z).length;
    return {
      codigo: z, radio: vs.length ? 7 + cupos * 3 : 6 + Math.min(n, 8) * 1.5,
      color: vs.length ? "var(--aqua)" : "var(--celeste)", anillo: n ? "var(--celeste)" : null,
      lineas: [...(vs.length ? [`${vs.length} vacante(s) · ${cupos} cupo(s)`] : []), ...(n ? [`${n} ${n === 1 ? "candidato" : "candidatos"}`] : [])],
    };
  });

  const cuenta = {};
  candidatos.forEach((j) => j.habilidades.forEach((h) => { cuenta[h.codigo] = (cuenta[h.codigo] || 0) + 1; }));
  const filas = Object.entries(cuenta).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([c, n]) => ({
    clave: c, etiqueta: nombres[c] || c, valor: n, color: pedidas.has(c) ? "var(--aqua)" : "var(--celeste)",
  }));

  const zonasVacante = [...new Set(publicadas.map((v) => v.corregimiento))];
  const zonaTend = zona && zonasVacante.includes(zona) ? zona : null;
  const piden = zonaTend
    ? datos.tend?.por_zona[zonaTend] || []
    : Object.values(zonasVacante.flatMap((z) => datos.tend?.por_zona[z] || []).reduce((acc, h) => {
      acc[h.codigo] = { ...h, vacantes: (acc[h.codigo]?.vacantes || 0) + h.vacantes };
      return acc;
    }, {})).sort((a, b) => b.vacantes - a.vacantes).slice(0, 5);

  return (
    <div className="panorama-grilla emp-grilla">
      <section className="panel-oscuro panorama-mapa">
        <div className="panel-cabeza">
          <h3>Dónde viven sus candidatos</h3>
          {zona && <button className="chip claro" onClick={() => setZona(null)}>Ver todo · quitar {corregimiento(zona)}</button>}
        </div>
        <MapaPanama puntos={puntos} seleccionado={zona} onSeleccion={setZona}
                    leyenda={<><i className="punto aqua" /> vacantes (tamaño) <i className="punto anillo" /> viven candidatos</>} />
        <p className="nota">Toque un corregimiento para ver qué piden otras empresas ahí.</p>
      </section>

      <div className="panorama-lado">
        <section className="panel">
          <h3>Lo que saben sus candidatos</h3>
          {filas.length ? <BarrasH filas={filas} /> : <p className="suave">Todavía no hay candidatos para sus vacantes.</p>}
          <p className="nota"><i className="punto aqua" /> la piden sus vacantes · <i className="punto celeste" /> otras habilidades.
            Candidatos que cumplen y pueden llegar a tiempo; sin nombre, género ni edad.</p>
        </section>

        {piden.length > 0 && (
          <section className="panel">
            <h3>Qué piden otras empresas en {zonaTend ? corregimiento(zonaTend) : "su zona"}</h3>
            <BarrasH filas={piden.map((h) => ({ clave: h.codigo, etiqueta: nombres[h.codigo] || h.nombre, valor: h.vacantes }))} sufijo=" vac." />
            {datos.tend?.nota && <p className="nota">{datos.tend.nota}</p>}
          </section>
        )}
      </div>
    </div>
  );
}
