import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

/**
 * Título de página com uma linha na cor do tema logo abaixo, marcando
 * visualmente o início do conteúdo de cada seção/página.
 */
export default function PageTitle({ children, variant = "h4", component = "h1", sx }) {
  return (
    <Box sx={{ mb: 3, ...sx }}>
      <Typography variant={variant} component={component}>
        {children}
      </Typography>
      <Box sx={{ width: 56, height: 4, borderRadius: 2, bgcolor: "primary.main", mt: 1 }} />
    </Box>
  );
}
