import { useCallback, useEffect, useState } from "react";
import Ayuda from "../../componentes/Ayuda.jsx";
import { api } from "../../api.js";
import FormMotivo from "../../componentes/FormMotivo.jsx";
import { corregimiento, dinero } from "../../nombres.js";
import { nombreRegla } from "../empresa/Hallazgos.jsx";

// Ofertas que el Auditor bloqueó. Los hallazgos salen de su última traza; el orientador
// puede publicar una igual si es un falso positivo, siempre con motivo.
export default function Bloqueadas() {
  const [vacantes, setVacantes] = useState(null);
  const [auditorias, setAuditorias] = useState({});
  const [abierta, setAbierta] = useState(null);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    Promise.all([api.vacantesEstado("bloqueada"), api.trazas("auditor")]).then(([vs, ts]) => {
      const ultima = {};
      for (const t of ts) {   // vienen de la más nueva a la más vieja
        const id = t.entrada?.vacante_id;
        if (t.accion === "auditar_oferta" && id && !ultima[id]) ultima[id] = t.salida?.resultado;
      }
      setAuditorias(ultima);
      setVacantes(vs);
    }).catch((e) => setError(e.message));
  }, []);
  useEffect(cargar, [cargar]);

  if (error) return <p className="error">{error}</p>;
  if (!vacantes) return <p className="centro">Cargando…</p>;
  return (
    <>
      <p className="suave intro">
        Ofertas que el Auditor no dejó publicar porque piden algo que puede discriminar (edad, género,
        apariencia…). <Ayuda>El Auditor revisa cada oferta con reglas fijas, no con IA. Si se equivocó
        (falso positivo), usted puede publicarla igual explicando por qué; queda registrado.</Ayuda>
      </p>
      {aviso && <p className="aviso" role="status">{aviso}</p>}
      {vacantes.length === 0 ? <p className="vacio">No hay ofertas bloqueadas.</p> : (
        <ul className="lista">
          {vacantes.map((v) => {
            const r = auditorias[v.id];
            return (
              <li key={v.id} className="item">
                <div className="entrevista-cabeza">
                  <h3>{v.titulo}</h3>
                  <span className="estado-chip bloqueada">Bloqueada</span>
                </div>
                <p className="suave">{v.empresa_id} · {corregimiento(v.corregimiento)} · {dinero(v.salario_mensual)}</p>
                {v.texto_original && <p className="cita">{v.texto_original}</p>}
                {r?.hallazgos?.length > 0 && (
                  <ul className="lista">
                    {r.hallazgos.map((h, i) => (
                      <li key={i} className="item hallazgo">
                        <span className="etiqueta-regla">{nombreRegla(h.regla)}</span>
                        {h.fragmento && <q className="fragmento">…{h.fragmento.trim()}…</q>}
                        <p>{h.detalle}</p>
                      </li>
                    ))}
                  </ul>
                )}
                {abierta === v.id ? (
                  <FormMotivo pregunta="¿Por qué la publica a pesar del bloqueo?" textoBoton="Publicar igual"
                              opciones={["Falso positivo: el texto no discrimina", "La empresa ya corrigió por teléfono"]}
                              nota="Úselo solo si el Auditor se equivocó. Queda en la traza con su motivo."
                              onCancelar={() => setAbierta(null)}
                              onConfirmar={async (m) => { await api.publicarBloqueada(v.id, m); setAbierta(null); setAviso(`«${v.titulo}» publicada.`); cargar(); }} />
                ) : (
                  <div className="acciones-item">
                    <button className="boton secundario" onClick={() => setAbierta(v.id)}>Publicar igual</button>
                    <span className="nota">Lo normal es que la empresa la corrija desde su cuenta.</span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
