import { useState } from "react";

// Accesos de demostración, en el orden de la historia que se cuenta en la demo.
export const DEMO = [
  { token: "demo-j11", texto: "Joven (Lucía)" },
  { token: "demo-e_tienda", texto: "Empresa (Tienda)" },
  { token: "demo-e_hotel", texto: "Empresa (Hotel)" },
  { token: "demo-inadeh", texto: "Centro (INADEH)" },
  { token: "demo-orientador", texto: "Orientador" },
  { token: "demo-j07", texto: "Joven sin match" },
];

export default function Entrada({ onEntrar, onNuevo, error }) {
  const [token, setToken] = useState("");

  return (
    <section className="entrada">
      <h1>Encuentre trabajo cerca de usted</h1>
      <p className="suave">
        Deslice vacantes que de verdad le convienen: el sistema calcula traslado, pasaje y salario
        por usted, y una persona orientadora revisa cada match antes de la entrevista.
      </p>

      <button className="boton grande" onClick={onNuevo}>Soy joven y quiero registrarme</button>

      <form className="tarjeta-form" onSubmit={(e) => { e.preventDefault(); if (token.trim()) onEntrar(token.trim()); }}>
        <label>Ya tengo un código de acceso
          <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Pegue su código" />
        </label>
        <button className="boton secundario" type="submit">Entrar</button>
        {error && <p className="error">{error}</p>}
      </form>

      <div className="demo">
        <span className="suave">Accesos de demostración:</span>
        <div className="chips">
          {DEMO.map((d) => (
            <button key={d.token} className="chip" onClick={() => onEntrar(d.token)}>{d.texto}</button>
          ))}
        </div>
      </div>
    </section>
  );
}
