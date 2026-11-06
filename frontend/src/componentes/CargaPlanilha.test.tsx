import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CargaPlanilha } from "./CargaPlanilha";
import * as api from "../servicoApi";
import type { ResultadoPlanilha } from "../tipos";

vi.mock("../servicoApi", async (importar) => ({
  ...(await importar<typeof import("../servicoApi")>()),
  enviarPlanilha: vi.fn(),
  obterSituacaoPlanilha: vi.fn(),
}));

const resultado = (competencia: string): ResultadoPlanilha => ({
  competencia,
  competencia_arquivo: "2026-10",
  qtd_linhas_substituidas: 0,
  erros_abas: [],
  abas: [
    { aba: "Nova Lima", codigo_empresa: "671", cnpj: "x", competencia, qtd_linhas: 25, qtd_linhas_sem_recibo: 1 },
  ],
});
const soltar = () =>
  fireEvent.drop(screen.getByTestId("area-arquivos"), {
    dataTransfer: { files: [new File(["x"], "Nova Lima.xlsx")] },
  });

const enviar = () => fireEvent.click(screen.getByRole("button", { name: "Enviar planilha" }));

beforeEach(() => {
  vi.mocked(api.obterSituacaoPlanilha).mockResolvedValue({
    competencia: "2026-10",
    carregada: false,
    qtd_linhas: 0,
    empresas: [],
  });
});

test("avisa que a nova planilha substitui a competência inteira", async () => {
  vi.mocked(api.obterSituacaoPlanilha).mockResolvedValue({
    competencia: "x",
    carregada: true,
    qtd_linhas: 25,
    empresas: ["671"],
  });
  render(<CargaPlanilha aoCarregar={() => {}} />);
  expect(await screen.findByText(/substitui tudo desta competência/)).toBeInTheDocument();
});

test("competência divergente pede confirmação e reenvia com a escolha", async () => {
  const divergente = new api.ErroApi(409, "diverge", {
    codigo: "competencia_divergente",
    competencia_arquivo: "2026-10",
    competencia_informada: "2026-11",
  });
  vi.mocked(api.enviarPlanilha).mockRejectedValueOnce(divergente).mockResolvedValueOnce(resultado("2026-10"));
  const aoCarregar = vi.fn();
  render(<CargaPlanilha aoCarregar={aoCarregar} />);
  soltar();
  enviar();
  fireEvent.click(await screen.findByRole("button", { name: "Usar a da planilha (2026-10)" }));
  await waitFor(() => expect(aoCarregar).toHaveBeenCalled());
  expect(vi.mocked(api.enviarPlanilha).mock.calls[1][2]).toBe("arquivo");
  expect(await screen.findByText(/Competência 2026-10 carregada/)).toBeInTheDocument();
});

test("lista as abas que não foram importadas", async () => {
  vi.mocked(api.enviarPlanilha).mockResolvedValue({
    ...resultado("2026-10"),
    erros_abas: [{ aba: "Outra", mensagem: "código da empresa vazio em E1" }],
  });
  render(<CargaPlanilha aoCarregar={() => {}} />);
  soltar();
  enviar();
  expect(await screen.findByText(/Aba Outra não importada: código da empresa vazio em E1/)).toBeInTheDocument();
});

test("escolher o arquivo só o coloca na lista; o envio exige o botão", () => {
  render(<CargaPlanilha aoCarregar={() => {}} />);
  soltar();
  expect(screen.getByText("Nova Lima.xlsx")).toBeInTheDocument();
  expect(api.enviarPlanilha).not.toHaveBeenCalled();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
});

test("mostra o progresso do envio e fecha em 100% ao concluir", async () => {
  vi.mocked(api.enviarPlanilha).mockImplementation(async (_a, _c, _p, opcoes) => {
    opcoes?.progresso?.(0.5);
    await Promise.resolve();
    return resultado("2026-10");
  });
  render(<CargaPlanilha aoCarregar={() => {}} />);
  soltar();
  enviar();
  expect(await screen.findByText("Enviado")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
});

test("falha mostra o erro em vermelho e permite tentar de novo", async () => {
  vi.mocked(api.enviarPlanilha)
    .mockRejectedValueOnce(new api.ErroApi(0, "Falha de conexão durante o envio."))
    .mockResolvedValueOnce(resultado("2026-10"));
  render(<CargaPlanilha aoCarregar={() => {}} />);
  soltar();
  enviar();
  expect(await screen.findByRole("alert")).toHaveTextContent("Falha de conexão");
  fireEvent.click(screen.getByRole("button", { name: "Tentar de novo: Nova Lima.xlsx" }));
  expect(await screen.findByText("Enviado")).toBeInTheDocument();
  expect(api.enviarPlanilha).toHaveBeenCalledTimes(2);
});

test("remover tira o arquivo da lista e desabilita o envio", () => {
  render(<CargaPlanilha aoCarregar={() => {}} />);
  soltar();
  fireEvent.click(screen.getByRole("button", { name: "Remover Nova Lima.xlsx" }));
  expect(screen.queryByText("Nova Lima.xlsx")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Enviar planilha" })).toBeDisabled();
});
