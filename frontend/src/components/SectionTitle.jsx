import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

/**
 * Subtítulo de seção com uma linha fina na cor do tema logo abaixo —
 * versão mais discreta de PageTitle, para os títulos que organizam o
 * conteúdo dentro de uma página (não o título da página em si).
 */
export default function SectionTitle({ children, variant = "h6", component, sx }) {
  return (
    <Box sx={{ mb: 1.5, ...sx }}>
      <Typography variant={variant} component={component}>
        {children}
      </Typography>
      <Box sx={{ width: 36, height: 3, borderRadius: 2, bgcolor: "primary.main", mt: 0.5 }} />
    </Box>
  );
}
