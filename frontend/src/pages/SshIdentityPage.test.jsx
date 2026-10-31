import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import SshIdentityPage from "./SshIdentityPage";

vi.mock("../api/client", () => ({
  api: {
    getSshIdentity: vi.fn(),
    regenerateSshIdentity: vi.fn(),
  },
}));

beforeEach(() => {
  api.getSshIdentity.mockResolvedValue({ public_key: "ssh-ed25519 AAAA... chave-original" });
});

// `userEvent.setup()` instala o próprio stub de clipboard; definir o mock
// só depois disso evita que ele seja sobrescrito antes da asserção.
function mockClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return writeText;
}

test("exibe a chave pública retornada pela API", async () => {
  render(<SshIdentityPage />);

  expect(await screen.findByDisplayValue("ssh-ed25519 AAAA... chave-original")).toBeInTheDocument();
});

test("copiar coloca a chave na área de transferência", async () => {
  const user = userEvent.setup();
  const writeText = mockClipboard();
  render(<SshIdentityPage />);
  await screen.findByDisplayValue("ssh-ed25519 AAAA... chave-original");

  await user.click(screen.getByRole("button", { name: "Copiar" }));

  expect(writeText).toHaveBeenCalledWith("ssh-ed25519 AAAA... chave-original");
  expect(await screen.findByRole("button", { name: "Copiado!" })).toBeInTheDocument();
});

test("regenerar pede confirmação e, sem confirmar, não chama a API", async () => {
  const user = userEvent.setup();
  render(<SshIdentityPage />);
  await screen.findByDisplayValue("ssh-ed25519 AAAA... chave-original");

  await user.click(screen.getByRole("button", { name: "Regenerar identidade" }));
  const dialog = screen.getByRole("dialog");
  await user.click(within(dialog).getByRole("button", { name: "Cancelar" }));

  expect(api.regenerateSshIdentity).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

test("regenerar confirmado atualiza a chave exibida", async () => {
  api.regenerateSshIdentity.mockResolvedValue({
    public_key: "ssh-ed25519 BBBB... chave-nova",
    propagation_failures: [],
  });
  const user = userEvent.setup();
  render(<SshIdentityPage />);
  await screen.findByDisplayValue("ssh-ed25519 AAAA... chave-original");

  await user.click(screen.getByRole("button", { name: "Regenerar identidade" }));
  const dialog = screen.getByRole("dialog");
  await user.click(within(dialog).getByRole("button", { name: "Regenerar" }));

  expect(await screen.findByDisplayValue("ssh-ed25519 BBBB... chave-nova")).toBeInTheDocument();
});

test("falha de propagação mostra aviso ao usuário", async () => {
  api.regenerateSshIdentity.mockResolvedValue({
    public_key: "ssh-ed25519 BBBB... chave-nova",
    propagation_failures: ["inst-1"],
  });
  const user = userEvent.setup();
  render(<SshIdentityPage />);
  await screen.findByDisplayValue("ssh-ed25519 AAAA... chave-original");

  await user.click(screen.getByRole("button", { name: "Regenerar identidade" }));
  await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Regenerar" }));

  expect(await screen.findByText(/não pôde ser aplicada a 1 instância/)).toBeInTheDocument();
});
