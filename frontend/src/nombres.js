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

// Reemplaza códigos de habilidad dentro de un texto ("Tiene manejo_caja") por su nombre.
export function conNombres(texto, habilidades) {
  return texto.replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (c) => habilidades[c] || c);
}
