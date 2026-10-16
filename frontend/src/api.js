// Único punto de contacto con la API. Guarda el token y traduce errores a mensajes.
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8010";
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
  constructor(estado, mensaje) {
    super(mensaje);
    this.estado = estado;
  }
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
  if (!r.ok) throw new ErrorApi(r.status, mensajeDeError(r.status, datos));
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

  deslizar: (actor, joven_id, vacante_id, le_interesa) =>
    pedir("POST", "/deslizar", { actor, joven_id, vacante_id, le_interesa }),
};
