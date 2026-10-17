// Posiciones APROXIMADAS de corregimientos de Panamá y Panamá Oeste (longitud, latitud), solo para
// dibujar un mapa esquemático. No son datos oficiales ni sirven para calcular distancias: los
// tiempos y costos de viaje salen de la tabla de traslados.
export const POSICIONES = {
  la_chorrera: [-79.78, 8.885], barrio_colon: [-79.78, 8.885], barrio_balboa: [-79.795, 8.895],
  guadalupe: [-79.805, 8.87], vista_alegre: [-79.70, 8.93], arraijan: [-79.655, 8.95],
  burunga: [-79.635, 8.955], ancon: [-79.565, 8.965], calidonia: [-79.535, 8.968],
  bella_vista: [-79.522, 8.982], san_francisco: [-79.505, 8.992], betania: [-79.528, 9.01],
  amelia_denis_icaza: [-79.507, 9.03], san_miguelito: [-79.497, 9.035], belisario_porras: [-79.488, 9.047],
  omar_torrijos: [-79.492, 9.062], jose_domingo_espinar: [-79.472, 9.062], belisario_frias: [-79.47, 9.05],
  rufina_alfaro: [-79.457, 9.052], juan_diaz: [-79.452, 9.032], las_cumbres: [-79.53, 9.09],
  tocumen: [-79.375, 9.078], veinticuatro_diciembre: [-79.345, 9.098],
};

// Caja del dibujo (oeste, este, sur, norte) y tamaño del lienzo SVG.
const CAJA = { o: -79.86, e: -79.31, s: 8.84, n: 9.13 };
export const ANCHO = 600, ALTO = 330;

export function proyectar([lon, lat]) {
  return [((lon - CAJA.o) / (CAJA.e - CAJA.o)) * ANCHO, ((CAJA.n - lat) / (CAJA.n - CAJA.s)) * ALTO];
}

// Costa del Pacífico y Canal, muy simplificados (solo referencia visual).
const COSTA = [[-79.86, 8.845], [-79.80, 8.855], [-79.74, 8.87], [-79.68, 8.895], [-79.62, 8.925],
  [-79.585, 8.94], [-79.555, 8.952], [-79.525, 8.962], [-79.495, 8.975], [-79.46, 8.995],
  [-79.42, 9.02], [-79.38, 9.045], [-79.34, 9.065], [-79.31, 9.072]];
export const TIERRA = "M" + [[-79.86, 9.13], ...COSTA, [-79.31, 9.13]].map((p) => proyectar(p).map((v) => v.toFixed(1)).join(" ")).join(" L ") + " Z";
export const CANAL = "M" + [[-79.60, 9.13], [-79.59, 9.06], [-79.575, 9.0], [-79.567, 8.947]].map((p) => proyectar(p).map((v) => v.toFixed(1)).join(" ")).join(" L ");

export function tienePosicion(codigo) {
  return codigo in POSICIONES;
}
