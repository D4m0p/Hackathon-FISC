import { useEffect, useState } from "react";
import { api } from "../../api.js";
import Ayuda from "../../componentes/Ayuda.jsx";
import { conNombres, etiquetaJoven } from "../../nombres.js";

// Acciones que ningún humano disparó: el sistema reaccionó a algo que pasó.
// Se leen de /trazas; las que agregue el orquestador (auto_matching, auto_aviso) aparecen solas.
const ACCIONES = {
  auto_matching: ["⚡", (t) => t.motivo],
  auto_aviso: ["🔔", (t) => t.motivo],
  reacomodar: ["🔄", (t) => `Se liberó un cupo y el sistema volvió a buscar solo.${t.motivo.includes("Propuestas nuevas:")
    ? " Propuestas nuevas:" + t.motivo.split("Propuestas nuevas:")[1] : ""}`],
  auditar_oferta: ["🛡️", (t, c) => t.motivo.startsWith("Bloqueada")
    ? `El Auditor bloqueó «${c.titulo(t.entrada?.vacante_id)}» apenas se publicó`
    : `El Auditor revisó «${c.titulo(t.entrada?.vacante_id)}» al publicarse: sin requisitos discriminatorios`],
  normalizar_oferta: ["📝", () => "Mercado ordenó una oferta escrita en texto libre (puesto, horario, salario y habilidades)"],
  oferta_incompleta: ["📝", () => "Mercado detectó que a una oferta le faltan datos y pidió completarla"],
  interes_mutuo: ["🤝", (t, c) => `${c.joven(t.entrada?.joven_id)} y «${c.titulo(t.entrada?.vacante_id)}» dijeron que sí: interés mutuo`],
  planificar: ["📚", (t, c) => `Formación armó una ruta de cursos para ${c.joven(t.entrada?.joven_id)}`],
  auditar_matching: ["⚖️", (t) => `El Auditor revisó que las propuestas no tengan sesgo: ${t.motivo.toLowerCase()}`],
  retirar_propuesta: ["↩️", (t) => `Retiró una propuesta que ya no aplica: ${t.motivo}`],
};

function hace(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "hace un momento";
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  return `hace ${Math.round(s / 86400)} día(s)`;
}

export default function Automaticas({ cat, refrescar }) {
  const [trazas, setTrazas] = useState([]);
  const [todas, setTodas] = useState(false);

  useEffect(() => {
    const cargar = () => api.trazas().then((ts) => setTrazas(ts.filter((t) => ACCIONES[t.accion]))).catch(() => {});
    cargar();
    const intervalo = setInterval(cargar, 10000);
    return () => clearInterval(intervalo);
  }, [refrescar]);

  if (!trazas.length) return null;
  const c = {
    titulo: (id) => cat.vacantes[id]?.titulo || "una vacante",
    joven: (id) => (id ? etiquetaJoven(id, cat.jovenes) : "un joven"),
  };
  const visibles = trazas.slice(0, todas ? 15 : 4);
  return (
    <section className="automaticas">
      <h4>Lo que el sistema hizo solo
        <Ayuda>Nadie tocó un botón para esto: el sistema reaccionó a lo que pasó (una oferta nueva, un
        cupo liberado, un interés mutuo). Usted sigue aprobando cada propuesta antes de que llegue a
        una entrevista.</Ayuda>
      </h4>
      <ul>
        {visibles.map((t, i) => {
          const [icono, texto] = ACCIONES[t.accion];
          return (
            <li key={i}>
              <span className="icono" aria-hidden="true">{icono}</span>
              <span>{conNombres(texto(t, c), cat.habilidades)}</span>
              <span className="hora">{hace(t.fecha)}</span>
            </li>
          );
        })}
      </ul>
      {trazas.length > 4 && (
        <button className="enlace" onClick={() => setTodas(!todas)}>{todas ? "Ver menos" : "Ver más"}</button>
      )}
    </section>
  );
}
