// Componentes del puntaje (0 a 1) como barras: qué tanto aportó cada uno.
const PARTES = [["habilidades", "Habilidades"], ["traslado", "Traslado"], ["salario", "Salario"]];

export default function Barras({ desglose }) {
  return (
    <div className="barras">
      {PARTES.map(([k, nombre]) => (
        <div key={k} className="barra-fila">
          <span>{nombre}</span>
          <div className="pista"><div style={{ width: `${Math.round(desglose[k] * 100)}%` }} /></div>
          <span className="num">{Math.round(desglose[k] * 100)}</span>
        </div>
      ))}
    </div>
  );
}
