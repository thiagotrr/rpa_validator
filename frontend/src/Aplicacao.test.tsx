import { fireEvent, render, screen, within } from "@testing-library/react";
import { Aplicacao } from "./Aplicacao";
import * as api from "./servicoApi";

vi.mock("./servicoApi", async (importar) => ({
  ...(await importar<typeof import("./servicoApi")>()),
  obterRelatorio: vi.fn(),
  obterSituacaoPlanilha: vi.fn(),
  verificarEnvioRpas: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(api.obterRelatorio).mockRejectedValue(new api.ErroApi(404, "não encontrado"));
  vi.mocked(api.obterSituacaoPlanilha).mockResolvedValue({ competencia: "x", carregada: false, qtd_linhas: 0, empresas: [] });
  vi.mocked(api.verificarEnvioRpas).mockResolvedValue({
    competencia: "x", planilha_carregada: false, qtd_linhas_planilha: 0, qtd_arquivos: 0, qtd_sem_numero: 0,
    qtd_repetidos_no_envio: 0, qtd_ja_carregados: 0, qtd_ja_existentes_no_envio: 0, qtd_novos: 0,
    qtd_total_apos_envio: 0, diferenca: 0, confere: true,
  });
});
afterEach(() => api.sessao.sair());

const logar = () =>
  api.sessao.salvar({ id_token: "t", refresh_token: "r", expira_em: new Date(Date.now() + 3_600_000).toISOString() });

test("sem sessão mostra a tela de acesso", () => {
  render(<Aplicacao />);
  expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
});

test("o menu fica na lateral, com ícone em cada opção", () => {
  logar();
  render(<Aplicacao />);
  const menu = screen.getByRole("navigation", { name: "Menu principal" });
  for (const nome of ["Carga da planilha", "Carga dos RPAs", "Relatório"]) {
    const opcao = within(menu).getByRole("button", { name: nome });
    expect(opcao.querySelector("svg")).not.toBeNull();
  }
  expect(menu.closest("aside")).not.toBeNull();
});

test("o menu troca a seção mostrada e marca a opção atual", () => {
  logar();
  render(<Aplicacao />);
  const menu = screen.getByRole("navigation", { name: "Menu principal" });
  expect(within(menu).getByRole("button", { name: "Carga da planilha" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("heading", { name: "Carga da planilha" })).toBeVisible();
  fireEvent.click(within(menu).getByRole("button", { name: "Carga dos RPAs" }));
  expect(within(menu).getByRole("button", { name: "Carga dos RPAs" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("heading", { name: "Carga dos RPAs" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Carga da planilha" })).not.toBeInTheDocument();
});

test("sair encerra a sessão", () => {
  logar();
  render(<Aplicacao />);
  fireEvent.click(screen.getByRole("button", { name: "Sair" }));
  expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
  expect(api.sessao.obter()).toBeNull();
});
