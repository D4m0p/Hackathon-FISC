// Nombres legibles para códigos de la API.
const CORREGIMIENTOS = {
  arraijan: "Arraiján", bella_vista: "Bella Vista", juan_diaz: "Juan Díaz",
  la_chorrera: "La Chorrera", san_francisco: "San Francisco",
  san_miguelito: "San Miguelito", tocumen: "Tocumen",
};

export const TURNOS = {
  manana: "Mañana", tarde: "Tarde", noche: "Noche", fin_de_semana: "Fin de semana",
};

export function corregimiento(codigo) {
  return CORREGIMIENTOS[codigo] ||
    codigo.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export function dinero(n) {
  return `B/. ${Number(n).toFixed(2)}`;
}

export const NIVELES = { 1: "Básico", 2: "Con práctica", 3: "Avanzado" };

// El desglose del puntaje en palabras: minutos, pasaje, lo que le queda y qué ya sabe.
// Lee los motivos que escribe el Matching; si cambia su redacción, cae a null y la
// tarjeta muestra los motivos tal cual.
export function enPalabras(desglose) {
  const ms = desglose.motivos;
  const viaje = ms.map((m) => m.match(/Traslado de (\d+) min, B\/\.\s?([\d.]+) por semana/)).find(Boolean);
  const neto = ms.map((m) => m.match(/Salario neto de transporte: B\/\.\s?([\d.]+)/)).find(Boolean);
  const total = desglose.total;
  return {
    etiqueta: total >= 0.85 ? "Muy buena opción para usted" : total >= 0.7 ? "Buena opción para usted" : "Puede servirle",
    nivel: total >= 0.85 ? "alta" : total >= 0.7 ? "media" : "baja",
    minutos: viaje ? Number(viaje[1]) : null,
    pasajeSemana: viaje ? Number(viaje[2]) : null,
    neto: neto ? Number(neto[1]) : null,
    sabe: ms.map((m) => m.match(/^Tiene (\w+)/)?.[1]).filter(Boolean),
  };
}

export const AGENTES = {
  mercado: "Mercado", perfil: "Perfil", matching: "Matching", formacion: "Formación",
  auditor: "Auditor", orquestador: "Sistema", orientador: "Orientadora",
};

// Reemplaza códigos de habilidad dentro de un texto ("Tiene manejo_caja") por su nombre.
// Los códigos de una sola palabra ("ventas") solo cuando aparecen como habilidad, para no
// tocar títulos como «Asistente de ventas» o «Técnicas de ventas».
export function conNombres(texto, habilidades) {
  return texto.split(/(«[^»]*»)/).map((parte) => (parte.startsWith("«") ? parte : parte
    .replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (c) => habilidades[c] || c)
    .replace(/(^|Tiene |obligatoria |: |, )([a-z]+)\b/g, (m, antes, c) => (habilidades[c] ? antes + habilidades[c] : m))
  )).join("");
}
