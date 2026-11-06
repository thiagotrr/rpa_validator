import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CargaRpas } from "./CargaRpas";
import * as api from "../servicoApi";
import type { VerificacaoEnvio } from "../tipos";

vi.mock("../servicoApi");

const verificacao = (extra: Partial<VerificacaoEnvio> = {}): VerificacaoEnvio => ({
  competencia: "2026-11",
  planilha_carregada: true,
  qtd_linhas_planilha: 25,
  qtd_arquivos: 0,
  qtd_sem_numero: 0,
  qtd_repetidos_no_envio: 0,
  qtd_ja_carregados: 0,
  qtd_ja_existentes_no_envio: 0,
  qtd_novos: 0,
  qtd_total_apos_envio: 0,
  diferenca: -25,
  confere: false,
  ...extra,
});
const escolher = (...nomes: string[]) =>
  fireEvent.change(screen.getByLabelText("RPAs (.doc/.docx)"), {
    target: { files: nomes.map((n) => new File(["x"], n)) },
  });

beforeEach(() => {
  vi.mocked(api.enviarRpas).mockResolvedValue([{ arquivo: "a", status: "ok" }]);
});

test("sem planilha na competência, não deixa carregar e explica", async () => {
  vi.mocked(api.verificarEnvioRpas).mockResolvedValue(
    verificacao({ planilha_carregada: false, qtd_linhas_planilha: 0 }),
  );
  render(<CargaRpas aoCarregar={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Nenhuma planilha carregada");
  expect(screen.getByRole("button", { name: /Carregar/ })).toBeDisabled();
});

test("avisa da divergência de quantitativo ANTES de carregar e não bloqueia", async () => {
  vi.mocked(api.verificarEnvioRpas).mockImplementation(async (_c, arquivos) =>
    verificacao({
      qtd_arquivos: arquivos.length,
      qtd_novos: arquivos.length,
      qtd_total_apos_envio: arquivos.length,
      diferenca: arquivos.length - 25,
    }),
  );
  const aoCarregar = vi.fn();
  render(<CargaRpas aoCarregar={aoCarregar} />);
  escolher("RPA - A - 15000001.doc", "RPA - B - 15000002.doc");
  expect(await screen.findByText(/faltam 23/)).toBeInTheDocument();
  expect(api.enviarRpas).not.toHaveBeenCalled(); // avisou antes de enviar
  const botao = screen.getByRole("button", { name: "Carregar 2 arquivo(s)" });
  expect(botao).toBeEnabled();
  fireEvent.click(botao);
  await waitFor(() => expect(api.enviarRpas).toHaveBeenCalledTimes(1));
  expect(await screen.findByText(/1 processados/)).toBeInTheDocument();
  expect(aoCarregar).toHaveBeenCalled();
});

test("RPAs já existentes: por padrão são ignorados; a caixa pede para substituir", async () => {
  vi.mocked(api.verificarEnvioRpas).mockResolvedValue(
    verificacao({ qtd_arquivos: 1, qtd_ja_existentes_no_envio: 1, qtd_ja_carregados: 1, qtd_total_apos_envio: 1 }),
  );
  render(<CargaRpas aoCarregar={() => {}} />);
  escolher("RPA - A - 15000001.doc");
  expect(await screen.findByText(/já estão carregados e serão ignorados/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Substituir RPAs já carregados"));
  expect(await screen.findByText(/serão substituídos/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Carregar 1/ }));
  await waitFor(() => expect(api.enviarRpas).toHaveBeenCalled());
  expect(vi.mocked(api.enviarRpas).mock.calls[0][2]).toMatchObject({ substituir: true });
});
