import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { api } from "../api/client";
import ConfirmDialog from "../components/ConfirmDialog";

/**
 * Chave SSH própria do usuário, gerada e guardada pelo portal — nunca uma
 * chave que o usuário já tivesse em outro lugar (ver proposal.md). Esta é
 * a primeira área de "configurações" do portal: até agora só existiam
 * telas de administração.
 */
export default function SshIdentityPage() {
  const [publicKey, setPublicKey] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [confirmingRegenerate, setConfirmingRegenerate] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [propagationFailures, setPropagationFailures] = useState([]);

  useEffect(() => {
    api
      .getSshIdentity()
      .then((identity) => setPublicKey(identity.public_key))
      .finally(() => setLoading(false));
  }, []);

  async function handleCopy() {
    await navigator.clipboard.writeText(publicKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleRegenerateConfirmed() {
    setConfirmingRegenerate(false);
    setRegenerating(true);
    try {
      const result = await api.regenerateSshIdentity();
      setPublicKey(result.public_key);
      setPropagationFailures(result.propagation_failures);
    } finally {
      setRegenerating(false);
    }
  }

  if (loading) return null;

  return (
    <Box sx={{ p: 3, maxWidth: 720 }}>
      <Typography variant="h5" component="h2" sx={{ mb: 2 }}>
        Identidade SSH
      </Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>
        Esta chave pública é injetada automaticamente em toda instância sua
        (de agente ou webtop), para que o <code>git</code> dentro do
        container autentique com repositórios remotos. Cadastre-a como
        "deploy key" no GitHub, GitLab ou Bitbucket.
      </Typography>

      {propagationFailures.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          A nova chave não pôde ser aplicada a {propagationFailures.length}{" "}
          instância(s) existente(s). Pare e religue essas instâncias para
          que recebam a chave nova.
        </Alert>
      )}

      <Stack direction="row" spacing={1} alignItems="flex-start" sx={{ mb: 2 }}>
        <TextField
          label="Chave pública"
          value={publicKey}
          multiline
          fullWidth
          slotProps={{ input: { readOnly: true } }}
        />
        <Button onClick={handleCopy} sx={{ whiteSpace: "nowrap" }}>
          {copied ? "Copiado!" : "Copiar"}
        </Button>
      </Stack>

      <Button color="error" disabled={regenerating} onClick={() => setConfirmingRegenerate(true)}>
        Regenerar identidade
      </Button>

      <ConfirmDialog
        open={confirmingRegenerate}
        title="Regenerar identidade SSH?"
        description="Isto substitui sua chave SSH por uma nova. A chave antiga para de funcionar — se você a cadastrou em algum git host, precisará cadastrar a nova lá também."
        confirmLabel="Regenerar"
        onCancel={() => setConfirmingRegenerate(false)}
        onConfirm={handleRegenerateConfirmed}
      />
    </Box>
  );
}
