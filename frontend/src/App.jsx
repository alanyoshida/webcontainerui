import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { AdminRoute, ProtectedRoute } from "./components/ProtectedRoute";
import TopBar from "./components/TopBar";
import AdminPage from "./pages/AdminPage";
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
              />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
