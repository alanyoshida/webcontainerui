import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1565c0" },
    secondary: { main: "#546e7a" },
  },
  shape: { borderRadius: 8 },
});

export default theme;
