import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api, ApiError } from "../../api/client";
import ImagesPanel from "./ImagesPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminListImages: vi.fn(),
    adminCreateImage: vi.fn(),
    adminRetryPull: vi.fn(),
    adminUpdateImage: vi.fn(),
    adminDisableImage: vi.fn(),
    adminEnableImage: vi.fn(),
    adminEditImage: vi.fn(),
    adminUploadImageIcon: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(status, detail) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

function imagemBase(overrides = {}) {
  return {
    id: 1,
    display_name: "Webtop",
    repository: "lscr.io/linuxserver/webtop",
    tag: "latest",
    enabled: true,
    pull_state: "ready",
    pull_progress: null,
    pull_error: null,
    icon_url: null,
    image_version: null,
    provision_kind: "pull",
    created_at: "2024-01-01 00:00:00",
    ...overrides,
  };
}

test("imagem em download mostra há quanto tempo começou e o progresso bruto, não só 'Baixando' parado", async () => {
  const dezMinutosAtras = new Date(Date.now() - 10 * 60 * 1000).toISOString().replace("T", " ").slice(0, 19);
  api.adminListImages.mockResolvedValue([
    {
      id: 1,
      display_name: "Ubuntu KDE",
      repository: "lscr.io/linuxserver/webtop",
      tag: "ubuntu-kde",
      enabled: true,
      pull_state: "pulling",
      pull_progress: "[====>    ] 1.8GB/7.2GB",
      pull_error: null,
      created_at: dezMinutosAtras,
    },
  ]);

  render(<ImagesPanel />);

  expect(await screen.findByText("Baixando")).toBeInTheDocument();
  expect(await screen.findByText(/há 10 minutos/)).toBeInTheDocument();
  expect(screen.getByText(/1\.8GB\/7\.2GB/)).toBeInTheDocument();
});

test("imagem pronta não mostra progresso nem tempo decorrido", async () => {
  api.adminListImages.mockResolvedValue([
    {
      id: 1,
      display_name: "Webtop",
      repository: "lscr.io/linuxserver/webtop",
      tag: "latest",
      enabled: true,
      pull_state: "ready",
      pull_progress: null,
      pull_error: null,
      created_at: "2024-01-01 00:00:00",
    },
  ]);

  render(<ImagesPanel />);

  expect(await screen.findByText("Pronta")).toBeInTheDocument();
  expect(screen.queryByText(/há .* minuto/)).not.toBeInTheDocument();
});

test("imagem em falha mostra a mensagem de erro", async () => {
  api.adminListImages.mockResolvedValue([
    {
      id: 1,
      display_name: "Webtop",
      repository: "lscr.io/linuxserver/webtop",
      tag: "latest",
      enabled: true,
      pull_state: "failed",
      pull_progress: null,
      pull_error: "registro indisponível",
      created_at: "2024-01-01 00:00:00",
    },
  ]);

  render(<ImagesPanel />);

  expect(await screen.findByText("registro indisponível")).toBeInTheDocument();
});

test("envio de capa bem-sucedido recarrega a lista", async () => {
  const user = userEvent.setup();
  api.adminListImages.mockResolvedValue([imagemBase()]);
  api.adminUploadImageIcon.mockResolvedValue(imagemBase({ icon_url: "/uploads/1-abc.png" }));

  render(<ImagesPanel />);
  await screen.findByText("Webtop");
  const chamadasAntes = api.adminListImages.mock.calls.length;

  await user.click(screen.getByRole("button", { name: "Enviar capa" }));
  const arquivo = new File(["conteudo"], "capa.png", { type: "image/png" });
  await user.upload(screen.getByTestId("icon-file-input"), arquivo);

  expect(api.adminUploadImageIcon).toHaveBeenCalledWith(1, arquivo);
  await waitFor(() => {
    expect(api.adminListImages.mock.calls.length).toBeGreaterThan(chamadasAntes);
  });
});

test("erro no envio de capa é exibido ao administrador", async () => {
  // applyAccept: false — o backend é quem decide o que é uma imagem válida
  // (por assinatura de arquivo); este teste simula um arquivo que passou
  // pela seleção do usuário mas foi recusado pela validação do servidor.
  const user = userEvent.setup({ applyAccept: false });
  api.adminListImages.mockResolvedValue([imagemBase()]);
  api.adminUploadImageIcon.mockRejectedValue(new ApiError(400, "arquivo enviado não é uma imagem reconhecida"));

  render(<ImagesPanel />);
  await screen.findByText("Webtop");

  await user.click(screen.getByRole("button", { name: "Enviar capa" }));
  const arquivo = new File(["conteudo"], "capa.txt", { type: "text/plain" });
  await user.upload(screen.getByTestId("icon-file-input"), arquivo);

  expect(await screen.findByText("arquivo enviado não é uma imagem reconhecida")).toBeInTheDocument();
});

test("desabilitar exige confirmação descrevendo a retirada da oferta", async () => {
  const user = userEvent.setup();
  api.adminListImages.mockResolvedValue([imagemBase()]);
  api.adminDisableImage.mockResolvedValue();

  render(<ImagesPanel />);
  await user.click(await screen.findByRole("button", { name: /desabilitar/i }));

  expect(api.adminDisableImage).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Desabilitar Webtop?")).toBeInTheDocument();
  expect(within(dialog).getByText(/deixa de aparecer no catálogo/)).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: /^desabilitar$/i }));

  expect(api.adminDisableImage).toHaveBeenCalledWith(1);
});

test("entrada pronta de pull oferece atualizar imagem e recarrega a lista após o disparo", async () => {
  const user = userEvent.setup();
  api.adminListImages.mockResolvedValue([imagemBase()]);
  api.adminUpdateImage.mockResolvedValue(imagemBase({ pull_state: "pulling" }));

  render(<ImagesPanel />);
  const chamadasAntes = api.adminListImages.mock.calls.length;

  await user.click(await screen.findByRole("button", { name: /atualizar imagem/i }));

  expect(api.adminUpdateImage).toHaveBeenCalledWith(1);
  await waitFor(() => {
    expect(api.adminListImages.mock.calls.length).toBeGreaterThan(chamadasAntes);
  });
});

test("entrada pronta de build não oferece atualização de imagem (ciclo próprio de rebuild)", async () => {
  api.adminListImages.mockResolvedValue([imagemBase({ provision_kind: "build" })]);

  render(<ImagesPanel />);
  await screen.findByText("Webtop");

  expect(screen.queryByRole("button", { name: /atualizar imagem/i })).not.toBeInTheDocument();
});

test("erro na atualização de imagem é exibido ao administrador", async () => {
  const user = userEvent.setup();
  api.adminListImages.mockResolvedValue([imagemBase()]);
  api.adminUpdateImage.mockRejectedValue(new ApiError(409, "atualização de imagem só vale para entradas de pull"));

  render(<ImagesPanel />);
  await user.click(await screen.findByRole("button", { name: /atualizar imagem/i }));

  expect(await screen.findByText("atualização de imagem só vale para entradas de pull")).toBeInTheDocument();
});

test("versão registrada aparece junto à referência da entrada", async () => {
  api.adminListImages.mockResolvedValue([imagemBase({ image_version: "1.143.1-ls31" })]);

  render(<ImagesPanel />);

  expect(await screen.findByText(/versão 1\.143\.1-ls31/)).toBeInTheDocument();
});

test("editar abre diálogo preenchido e submete só os campos alterados", async () => {
  api.adminListImages.mockResolvedValue([
    imagemBase({ shm_size_mb: 1024, mem_limit_mb: 2048, cpu_limit: 2, port: 3000 }),
  ]);
  api.adminEditImage.mockResolvedValue({ id: 1 });

  render(<ImagesPanel />);
  await screen.findByText("Webtop");

  await userEvent.click(screen.getByRole("button", { name: /editar/i }));
  const dialog = await screen.findByRole("dialog");
  const nome = within(dialog).getByLabelText(/nome de exibição/i);
  expect(nome).toHaveValue("Webtop");

  await userEvent.clear(nome);
  await userEvent.type(nome, "Webtop Editado");
  await userEvent.click(within(dialog).getByRole("button", { name: /salvar/i }));

  await waitFor(() => {
    expect(api.adminEditImage).toHaveBeenCalledWith(1, { display_name: "Webtop Editado" });
  });
});

test("entrada desabilitada oferece reativar que chama a API", async () => {
  api.adminListImages.mockResolvedValue([imagemBase({ enabled: false })]);
  api.adminEnableImage.mockResolvedValue(null);

  render(<ImagesPanel />);
  await screen.findByText("Webtop");

  expect(screen.queryByRole("button", { name: /desabilitar/i })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /reativar/i }));

  await waitFor(() => {
    expect(api.adminEnableImage).toHaveBeenCalledWith(1);
  });
});
