// Avisa de los commits nuevos de los compañeros: al abrir sesión, después de
// cada respuesta y cada 2 minutos. Muestra un aviso en pantalla y, si hay una
// sesión activa, lo deja también en el contexto del asistente.
export const Novedades = async ({ client, $, directory }) => {
  let sesionActual = null

  const revisar = async (forzar = false) => {
    const args = forzar ? ["--ya"] : []
    const salida = (await $`${directory}/scripts/novedades.sh ${args}`.nothrow().quiet().text()).trim()
    if (!salida) return
    await client.tui.showToast({ body: { message: salida, variant: "info" } }).catch(() => {})
    if (sesionActual) {
      await client.session
        .prompt({
          path: { id: sesionActual },
          body: { noReply: true, parts: [{ type: "text", text: salida }] },
        })
        .catch(() => {})
    }
  }

  setInterval(() => revisar().catch(() => {}), 120_000)

  return {
    event: async ({ event }) => {
      const id = event.properties?.sessionID ?? event.properties?.info?.id
      if (event.type === "session.created") {
        sesionActual = id ?? sesionActual
        await revisar(true)
      }
      if (event.type === "session.idle") {
        sesionActual = id ?? sesionActual
        await revisar()
      }
    },
  }
}
