// Único punto de contacto con la API. Guarda el token y traduce errores a mensajes.
// Por defecto, la API en la misma máquina desde donde se abrió la página (localhost en la
// laptop; la IP de la laptop si se abre desde un celular en la misma red).
const BASE = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8010`;
const CLAVE_TOKEN = "empleo_token";

export function leerToken() {
  try { return localStorage.getItem(CLAVE_TOKEN); } catch { return null; }
}

export function guardarToken(token) {
  try {
    if (token) localStorage.setItem(CLAVE_TOKEN, token);
    else localStorage.removeItem(CLAVE_TOKEN);
  } catch { /* sin almacenamiento: el token vive solo en esta pestaña */ }
}

export class ErrorApi extends Error {
  constructor(estado, mensaje, cuerpo = null) {
    super(mensaje);
    this.estado = estado;
    this.cuerpo = cuerpo;   // p. ej. {detail, faltantes} cuando a una oferta le faltan datos
  }
}

// Id corto para registros nuevos. randomUUID solo existe en https o localhost.
export function nuevoId(prefijo) {
  const azar = globalThis.crypto?.randomUUID?.().slice(0, 8) || Math.random().toString(36).slice(2, 10);
  return `${prefijo}-${azar}`;
}

function mensajeDeError(estado, cuerpo) {
  const d = cuerpo?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return "Revise los datos: " + d.map((e) => e.msg).join("; ");
  if (estado === 401) return "Su sesión no es válida; vuelva a entrar.";
  if (estado === 403) return "No tiene permiso para esta acción.";
  if (estado === 404) return "No se encontró lo que buscaba.";
  return "Ocurrió un error con el servidor.";
}

async function pedir(metodo, ruta, cuerpo, token = leerToken()) {
  const cabeceras = { "Content-Type": "application/json" };
  if (token) cabeceras.Authorization = `Bearer ${token}`;
  let r;
  try {
    r = await fetch(BASE + ruta, {
      method: metodo, headers: cabeceras,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new ErrorApi(0, `No se pudo conectar con la API (${BASE}). ¿Está encendida?`);
  }
  if (r.status === 204) return null;
  const datos = await r.json().catch(() => null);
  if (!r.ok) throw new ErrorApi(r.status, mensajeDeError(r.status, datos), datos);
  return datos;
}

export const api = {
  yo: (token) => pedir("GET", "/yo", undefined, token),
  habilidades: () => pedir("GET", "/habilidades"),
  traslados: () => pedir("GET", "/traslados"),
  cursos: () => pedir("GET", "/cursos"),

  // Perfil
  preguntas: () => pedir("GET", "/perfil/preguntas"),
  perfilDesdeCv: (cuerpo) => pedir("POST", "/perfil/cv", cuerpo),
  perfilDesdeEntrevista: (respuestas) => pedir("POST", "/perfil/entrevista", { respuestas }),

  // Joven
  registrarJoven: (joven, datos) => pedir("POST", "/jovenes", { joven, datos }),
  joven: (id) => pedir("GET", `/jovenes/${id}`),
  tarjetasJoven: (id) => pedir("GET", `/jovenes/${id}/tarjetas`),
  casiCalifica: (id) => pedir("GET", `/jovenes/${id}/casi-califica`),
  plan: (id) => pedir("GET", `/jovenes/${id}/plan`),
  historia: (id) => pedir("GET", `/jovenes/${id}/historia`),

  vacantes: () => pedir("GET", "/vacantes"),

  // Empresa
  publicarVacante: (vacante) => pedir("POST", "/vacantes", vacante),
  publicarOferta: (texto, empresa_id) => pedir("POST", "/ofertas", { texto, empresa_id }),
  candidatos: (vacante_id) => pedir("GET", `/vacantes/${vacante_id}/tarjetas`),
  asignaciones: () => pedir("GET", "/asignaciones"),
  retirar: (joven_id, vacante_id, motivo) =>
    pedir("POST", `/asignaciones/${joven_id}/${vacante_id}/liberar`, { tipo: "retiro_empresa", motivo }),
  cerrarVacante: (vacante_id, motivo) => pedir("POST", `/vacantes/${vacante_id}/cerrar`, { motivo }),

  // Orientador
  matching: () => pedir("POST", "/matching"),
  asignacionesEstado: (estado) => pedir("GET", `/asignaciones?estado=${estado}`),
  decidir: (joven_id, vacante_id, aprobar, motivo = "") =>
    pedir("POST", `/asignaciones/${joven_id}/${vacante_id}/decision`, { aprobar, motivo }),
  inasistencia: (joven_id, vacante_id, motivo) =>
    pedir("POST", `/asignaciones/${joven_id}/${vacante_id}/liberar`, { tipo: "inasistencia", motivo }),
  vacantesEstado: (estado) => pedir("GET", `/vacantes?estado=${estado}`),
  publicarBloqueada: (vacante_id, motivo) => pedir("POST", `/vacantes/${vacante_id}/publicar-bloqueada`, { motivo }),
  jovenes: () => pedir("GET", "/jovenes"),
  planes: () => pedir("GET", "/planes"),
  trazas: (agente) => pedir("GET", `/trazas?limite=300${agente ? `&agente=${agente}` : ""}`),
  mensajes: () => pedir("GET", "/mensajes"),
  contrafactual: (joven_id) => pedir("GET", `/auditoria/contrafactual/${joven_id}`),
  tendencias: (top = 5) => pedir("GET", `/mercado/tendencias?top=${top}`),
  pesos: () => pedir("GET", "/pesos"),
  simularPesos: (pesos) => pedir("POST", "/pesos/simular", pesos),
  cambiarPesos: (pesos, motivo) => pedir("PUT", "/pesos", { pesos, motivo }),
  cancelar: (joven_id, vacante_id, motivo) =>
    pedir("POST", `/asignaciones/${joven_id}/${vacante_id}/liberar`, { tipo: "cancelacion_joven", motivo }),
  reprogramar: (joven_id, vacante_id, motivo) =>
    pedir("POST", `/asignaciones/${joven_id}/${vacante_id}/reprogramar`, { motivo }),

  deslizar: (actor, joven_id, vacante_id, le_interesa) =>
    pedir("POST", "/deslizar", { actor, joven_id, vacante_id, le_interesa }),
};
