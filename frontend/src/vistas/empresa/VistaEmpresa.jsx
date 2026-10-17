import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import Guia, { guiaVista, marcarGuiaVista } from "../../componentes/Guia.jsx";
import { TURNOS, corregimiento, dinero } from "../../nombres.js";
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
        <span />
        <button className="enlace" onClick={() => setGuia(true)}>¿Cómo funciona?</button>
      </div>
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
        {[...vacantes].sort((a, b) => orden[a.estado] - orden[b.estado]).map((v) => (
          <li key={v.id}>
            <button className={"item fila-vacante " + v.estado} onClick={() => setPantalla({ tipo: "detalle", id: v.id })}>
              <div>
                <h3>{v.titulo}</h3>
                <p className="suave">{corregimiento(v.corregimiento)} · {dinero(v.salario_mensual)} · {v.cupos} cupo(s)</p>
              </div>
              <span className={"estado-chip " + v.estado}>{ESTADOS[v.estado]}</span>
            </button>
          </li>
        ))}
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
