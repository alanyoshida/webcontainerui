import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { Link as RouterLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function TopBar() {
  const { user, logout } = useAuth();

  return (
    <AppBar position="static" color="primary" enableColorOnDark>
      <Toolbar>
        <Typography variant="h6" component={RouterLink} to="/" sx={{ color: "inherit", textDecoration: "none", flexGrow: 1 }}>
          webcontainerui
        </Typography>
        {user && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            {user.is_admin && (
              <Button color="inherit" component={RouterLink} to="/admin">
                Administração
              </Button>
            )}
            <Typography variant="body2">{user.email}</Typography>
            <Button color="inherit" onClick={logout}>
              Sair
            </Button>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
}
