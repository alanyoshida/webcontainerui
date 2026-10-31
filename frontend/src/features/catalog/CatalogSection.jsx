import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import ImageIcon from "@mui/icons-material/Image";
import { api } from "../../api/client";

const COVER_HEIGHT = 140;

export default function CatalogSection({ onStart }) {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [startingId, setStartingId] = useState(null);

  useEffect(() => {
    api
      .getCatalog()
      .then(setImages)
      .catch(() => setError("Não foi possível carregar o catálogo."))
      .finally(() => setLoading(false));
  }, []);

  async function handleStart(imageId) {
    setStartingId(imageId);
    try {
      await onStart(imageId);
    } finally {
      setStartingId(null);
    }
  }

  return (
    <section aria-label="Catálogo de imagens">
      <Typography variant="h5" component="h2" gutterBottom>
        Catálogo
      </Typography>

      {loading && <CircularProgress size={24} />}
      {error && <Alert severity="error">{error}</Alert>}

      {!loading && !error && images.length === 0 && (
        <Alert severity="info">
          Nenhuma imagem disponível para você ainda. Peça ao administrador para liberar o acesso a um
          grupo com permissão sobre alguma imagem.
        </Alert>
      )}

      <Grid container spacing={2}>
        {images.map((image) => (
          <Grid item xs={12} sm={6} md={4} key={image.id}>
            <Card variant="outlined">
              {image.icon_url ? (
                <CardMedia
                  component="img"
                  src={image.icon_url}
                  alt={image.display_name}
                  sx={{ height: COVER_HEIGHT, objectFit: "contain" }}
                />
              ) : (
                <Box
                  sx={{
                    height: COVER_HEIGHT,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    bgcolor: "action.hover",
                  }}
                >
                  <ImageIcon color="disabled" sx={{ fontSize: 48 }} />
                </Box>
              )}
              <CardContent>
                <Typography variant="h6">{image.display_name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {image.repository}:{image.tag}
                </Typography>
              </CardContent>
              <CardActions>
                <Button
                  size="small"
                  variant="contained"
                  disabled={startingId === image.id}
                  onClick={() => handleStart(image.id)}
                >
                  {startingId === image.id ? "Iniciando..." : "Iniciar"}
                </Button>
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
    </section>
  );
}
