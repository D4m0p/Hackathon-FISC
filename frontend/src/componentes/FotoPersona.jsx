import { useEffect, useState } from "react";
import { urlFoto } from "../api.js";
import { numeroCorto } from "../nombres.js";

// Foto del joven si quien mira tiene permiso (el propio joven, el orientador o la empresa con
// entrevista aprobada); si no, un círculo con su número. Al aparecer, la foto se "revela".
export default function FotoPersona({ jovenId, tamano = 64, version = 0, revelar = false }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let vivo = true, actual = null;
    urlFoto(jovenId).then((u) => { actual = u; if (vivo) setUrl(u); else if (u) URL.revokeObjectURL(u); });
    return () => { vivo = false; if (actual) URL.revokeObjectURL(actual); };
  }, [jovenId, version]);
  const estilo = { width: tamano, height: tamano };
  if (!url) return <span className="foto-persona sin-foto" style={{ ...estilo, fontSize: tamano * 0.3 }} aria-hidden="true">{numeroCorto(jovenId)}</span>;
  return <img className={"foto-persona" + (revelar ? " revelar" : "")} style={estilo} src={url} alt="Foto de la persona" />;
}
