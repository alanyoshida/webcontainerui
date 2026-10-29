import Box from "@mui/material/Box";

/**
 * Embute a sessão de desktop num iframe same-origin. O caminho é relativo
 * à própria origem do portal (`/i/<id>/`), nunca um endereço de container —
 * é isso que permite embutir sem relaxar o CSP padrão do Selkies
 * (`frame-ancestors 'self'`), ver design.md D1.
 */
export default function InstanceSession({ instanceId }) {
  return (
    <Box
      component="iframe"
      title={`Sessão da instância ${instanceId}`}
      src={`/i/${instanceId}/`}
      sx={{ width: "100%", height: "100%", border: 0, display: "block" }}
    />
  );
}
