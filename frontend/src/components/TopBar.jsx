import { useState } from "react";
import AppBar from "@mui/material/AppBar";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import ListSubheader from "@mui/material/ListSubheader";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { ChevronDown, KeyRound, LogOut, Palette, Shield } from "lucide-react";
import { Link as RouterLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ADMIN_SECTIONS, ADMIN_SECTION_GROUPS } from "../features/admin/adminSections";
import { LOGO_FONT_FAMILY, THEME_MODES } from "../theme";
import { useThemeMode } from "../theme/ThemeModeContext";
import { emailInitials } from "../utils/initials";

const THEME_LABEL = { light: "Light", dark: "Dark", pastel: "Pastel" };

/**
 * Barra superior em três zonas (ver design.md D4): à esquerda a logo e o
 * menu "Administração" (só para admins), à direita o seletor de tema e o
 * menu do usuário (avatar). O e-mail nunca fica solto na barra — vive só
 * no cabeçalho do menu do usuário — e todo filho usa `minWidth: 0`/
 * `noWrap`, o que elimina a causa-raiz do transbordo em telas estreitas
 * (antes, 611px de largura mínima). A logo é o elemento que trunca
 * quando falta espaço; o botão "Administração" nunca encolhe.
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
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0, flexGrow: 1 }}>
          <Typography
            component={RouterLink}
            to="/"
            noWrap
            sx={{
              color: "inherit",
              textDecoration: "none",
              minWidth: 0,
              flexShrink: 1,
              overflow: "hidden",
              textOverflow: "ellipsis",
              fontFamily: LOGO_FONT_FAMILY,
              fontSize: "1.9rem",
              lineHeight: 1,
            }}
          >
            WebContainerUI
          </Typography>

          {user?.is_admin && (
            <>
              <Button
                color="inherit"
                startIcon={<Shield size={16} />}
                endIcon={<ChevronDown size={16} />}
                onClick={(event) => setAdminMenuAnchor(event.currentTarget)}
                sx={{ minWidth: 0, flexShrink: 0, px: { xs: 1, sm: 2 }, fontSize: { xs: "0.75rem", sm: "0.875rem" } }}
              >
                Administração
              </Button>
              <Menu anchorEl={adminMenuAnchor} open={Boolean(adminMenuAnchor)} onClose={() => setAdminMenuAnchor(null)}>
                {ADMIN_SECTIONS.flatMap((section, index) => {
                  const previousGroup = ADMIN_SECTIONS[index - 1]?.group;
                  const nodes = [];
                  if (section.group !== previousGroup) {
                    if (index > 0) nodes.push(<Divider key={`divider-${section.group}`} />);
                    const groupLabel = ADMIN_SECTION_GROUPS[section.group];
                    if (groupLabel) {
                      nodes.push(
                        <ListSubheader
                          key={`heading-${section.group}`}
                          sx={{
                            position: "static",
                            bgcolor: "transparent",
                            fontSize: "0.6875rem",
                            fontWeight: 600,
                            letterSpacing: "0.06em",
                            textTransform: "uppercase",
                            lineHeight: 2.5,
                          }}
                        >
                          {groupLabel}
                        </ListSubheader>
                      );
                    }
                  }
                  nodes.push(
                    <MenuItem
                      key={section.path}
                      component={RouterLink}
                      to={`/admin/${section.path}`}
                      onClick={() => setAdminMenuAnchor(null)}
                    >
                      <ListItemIcon sx={{ color: "primary.main" }}>
                        <section.Icon size={18} />
                      </ListItemIcon>
                      <ListItemText>{section.label}</ListItemText>
                    </MenuItem>
                  );
                  return nodes;
                })}
              </Menu>
            </>
          )}
        </Box>

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
