import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // ".." deja leer datos/corregimientos.csv (coordenadas con fuente) sin copiarlo al frontend.
  server: { port: 5173, fs: { allow: [".."] } },
});
