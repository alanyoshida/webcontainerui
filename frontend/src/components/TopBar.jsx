import { useState } from "react";
import AppBar from "@mui/material/AppBar";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { ChevronDown, KeyRound, LogOut, Palette } from "lucide-react";
import { Link as RouterLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ADMIN_SECTIONS } from "../features/admin/adminSections";
import { THEME_MODES } from "../theme";
import { useThemeMode } from "../theme/ThemeModeContext";
import { emailInitials } from "../utils/initials";

const THEME_LABEL = { light: "Light", dark: "Dark", pastel: "Pastel" };

/**
 * Barra superior em três zonas (ver design.md D4): à esquerda o menu
 * "Administração" (só para admins), ao centro a logo, à direita o seletor
 * de tema e o menu do usuário (avatar). O e-mail nunca fica solto na barra
 * — vive só no cabeçalho do menu do usuário — e todo filho usa
 * `minWidth: 0`/`noWrap`, o que elimina a causa-raiz do transbordo em
 * telas estreitas (antes, 611px de largura mínima).
 */
export default function TopBar() {
  const { user, logout } = useAuth();
  const { mode, setMode } = useThemeMode();
  const [adminMenuAnchor, setAdminMenuAnchor] = useState(null);
  const [themeMenuAnchor, setThemeMenuAnchor] = useState(null);
  const [userMenuAnchor, setUserMenuAnchor] = useState(null);

  return (
    <AppBar position="static" color="primary" enableColorOnDark>
      <Toolbar sx={{ gap: 1 }}>
        <Box sx={{ flexShrink: 0 }}>
          {user?.is_admin && (
            <>
              <Button
                color="inherit"
                endIcon={<ChevronDown size={16} />}
                onClick={(event) => setAdminMenuAnchor(event.currentTarget)}
                sx={{ minWidth: 0, px: { xs: 1, sm: 2 }, fontSize: { xs: "0.75rem", sm: "0.875rem" } }}
              >
                Administração
              </Button>
              <Menu anchorEl={adminMenuAnchor} open={Boolean(adminMenuAnchor)} onClose={() => setAdminMenuAnchor(null)}>
                {ADMIN_SECTIONS.map((section) => (
                  <MenuItem
                    key={section.path}
                    component={RouterLink}
                    to={`/admin/${section.path}`}
                    onClick={() => setAdminMenuAnchor(null)}
                  >
                    {section.label}
                  </MenuItem>
                ))}
              </Menu>
            </>
          )}
        </Box>

        <Typography
          variant="h6"
          component={RouterLink}
          to="/"
          noWrap
          sx={{ color: "inherit", textDecoration: "none", minWidth: 0, flexGrow: 1, overflow: "hidden", textOverflow: "ellipsis" }}
        >
          webcontainerui
        </Typography>

        {user && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexShrink: 0 }}>
            <Tooltip title="Tema">
              <IconButton
                color="inherit"
                onClick={(event) => setThemeMenuAnchor(event.currentTarget)}
                aria-label="Tema"
              >
                <Palette size={20} />
              </IconButton>
            </Tooltip>
            <Menu anchorEl={themeMenuAnchor} open={Boolean(themeMenuAnchor)} onClose={() => setThemeMenuAnchor(null)}>
              {THEME_MODES.map((themeMode) => (
                <MenuItem
                  key={themeMode}
                  selected={themeMode === mode}
                  onClick={() => {
                    setMode(themeMode);
                    setThemeMenuAnchor(null);
                  }}
                >
                  {THEME_LABEL[themeMode]}
                </MenuItem>
              ))}
            </Menu>

            <Button
              color="inherit"
              onClick={(event) => setUserMenuAnchor(event.currentTarget)}
              endIcon={<ChevronDown size={16} />}
              sx={{ minWidth: 0, px: 1 }}
              aria-label="Menu do usuário"
            >
              <Avatar sx={{ width: 28, height: 28, fontSize: 13, bgcolor: "primary.dark" }}>
                {emailInitials(user.email)}
              </Avatar>
            </Button>
            <Menu anchorEl={userMenuAnchor} open={Boolean(userMenuAnchor)} onClose={() => setUserMenuAnchor(null)}>
              <Box sx={{ px: 2, py: 1, maxWidth: 260 }}>
                <Typography variant="body2" color="text.secondary" noWrap>
                  {user.email}
                </Typography>
              </Box>
              <Divider />
              <MenuItem component={RouterLink} to="/ssh-identity" onClick={() => setUserMenuAnchor(null)}>
                <ListItemIcon>
                  <KeyRound size={18} />
                </ListItemIcon>
                <ListItemText>Identidade SSH</ListItemText>
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setUserMenuAnchor(null);
                  logout();
                }}
              >
                <ListItemIcon>
                  <LogOut size={18} />
                </ListItemIcon>
                <ListItemText>Sair</ListItemText>
              </MenuItem>
            </Menu>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
}
