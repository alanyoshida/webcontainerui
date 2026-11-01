import Container from "@mui/material/Container";
import { Outlet } from "react-router-dom";

/**
 * Layout do console administrativo: cada seção (ver adminSections.js) vive
 * no seu próprio endereço sob `/admin` e é renderizada aqui via `Outlet`.
 */
export default function AdminPage() {
  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Outlet />
    </Container>
  );
}
