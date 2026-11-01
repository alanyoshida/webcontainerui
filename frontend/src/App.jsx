import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { AdminRoute, ProtectedRoute } from "./components/ProtectedRoute";
import TopBar from "./components/TopBar";
import { ADMIN_SECTIONS } from "./features/admin/adminSections";
import AdminPage from "./pages/AdminPage";
import AdminSectionPage from "./pages/AdminSectionPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import SshIdentityPage from "./pages/SshIdentityPage";
import theme from "./theme";

function AppLayout({ children }) {
  return (
    <>
      <TopBar />
      {children}
    </>
  );
}

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route
                path="/"
                element={
                  <AppLayout>
                    <HomePage />
                  </AppLayout>
                }
              />
              <Route
                path="/ssh-identity"
                element={
                  <AppLayout>
                    <SshIdentityPage />
                  </AppLayout>
                }
              />
            </Route>
            <Route element={<AdminRoute />}>
              <Route
                path="/admin"
                element={
                  <AppLayout>
                    <AdminPage />
                  </AppLayout>
                }
              >
                <Route index element={<Navigate to={ADMIN_SECTIONS[0].path} replace />} />
                {ADMIN_SECTIONS.map(({ path, label, Panel }) => (
                  <Route key={path} path={path} element={<AdminSectionPage title={label} Panel={Panel} />} />
                ))}
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
