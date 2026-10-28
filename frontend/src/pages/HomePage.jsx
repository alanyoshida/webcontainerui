import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import CatalogSection from "../features/catalog/CatalogSection";
import InstancesSection from "../features/instances/InstancesSection";
import { useInstances } from "../features/instances/useInstances";

export default function HomePage() {
  const { instances, loading, error, create, stop, remove } = useInstances();

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Stack spacing={4}>
        <CatalogSection onStart={create} />
        <InstancesSection
          instances={instances}
          loading={loading}
          error={error}
          onStart={create}
          onStop={stop}
          onDelete={remove}
        />
      </Stack>
    </Container>
  );
}
