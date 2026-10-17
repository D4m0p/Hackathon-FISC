// Ubicaciones de los corregimientos para el mapa. Vienen de datos/corregimientos.csv (OpenStreetMap,
// con fuente y fecha por fila). Solo sirven para dibujar: los tiempos y costos de viaje salen de la
// tabla de traslados.
import csv from "../../datos/corregimientos.csv?raw";

function leerCsv(texto) {
  const [cabecera, ...filas] = texto.trim().split(/\r?\n/);
  const campos = cabecera.split(",");
  return filas.map((f) => Object.fromEntries(f.split(",").map((v, i) => [campos[i], v])));
}

const CON_FUENTE = Object.fromEntries(leerCsv(csv).map((r) => [r.codigo, [Number(r.lon), Number(r.lat)]]));

// Distritos que la demo usa como si fueran corregimientos: no tienen un punto único con fuente,
// así que se dibujan en un lugar aproximado y el mapa lo dice.
const APROXIMADAS = {
  la_chorrera: [-79.78, 8.885], barrio_colon: [-79.78, 8.885], barrio_balboa: [-79.795, 8.895],
  san_miguelito: [-79.497, 9.035],
};

export const POSICIONES = { ...APROXIMADAS, ...CON_FUENTE };

export function esAproximada(codigo) {
  return !(codigo in CON_FUENTE) && codigo in APROXIMADAS;
}

// Caja del dibujo (oeste, este, sur, norte) y tamaño del lienzo SVG.
const CAJA = { o: -79.86, e: -79.33, s: 8.84, n: 9.16 };
export const ANCHO = 600, ALTO = 360;

export function proyectar([lon, lat]) {
  return [((lon - CAJA.o) / (CAJA.e - CAJA.o)) * ANCHO, ((CAJA.n - lat) / (CAJA.n - CAJA.s)) * ALTO];
}

// Costa del Pacífico y Canal muy simplificados: solo referencia visual, no son datos.
const COSTA = [[-79.86, 8.845], [-79.80, 8.855], [-79.74, 8.87], [-79.68, 8.895], [-79.62, 8.925],
  [-79.585, 8.94], [-79.555, 8.952], [-79.525, 8.962], [-79.495, 8.975], [-79.46, 8.995],
  [-79.42, 9.02], [-79.38, 9.045], [-79.34, 9.065], [-79.33, 9.068]];
export const TIERRA = "M" + [[-79.86, 9.16], ...COSTA, [-79.33, 9.16]].map((p) => proyectar(p).map((v) => v.toFixed(1)).join(" ")).join(" L ") + " Z";
export const CANAL = "M" + [[-79.62, 9.16], [-79.60, 9.08], [-79.575, 9.0], [-79.567, 8.947]].map((p) => proyectar(p).map((v) => v.toFixed(1)).join(" ")).join(" L ");
