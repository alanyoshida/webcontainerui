import Typography from "@mui/material/Typography";

/**
 * Wrapper de cada seção administrativa roteada (ver AdminPage.jsx e
 * adminSections.js): título h4 com o nome da seção, acima do painel
 * existente, sem alterá-lo.
 */
export default function AdminSectionPage({ title, Panel }) {
  return (
    <>
      <Typography variant="h4" component="h1" gutterBottom>
        {title}
      </Typography>
      <Panel />
    </>
  );
}
