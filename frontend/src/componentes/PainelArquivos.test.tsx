import { fireEvent, render, screen, within } from "@testing-library/react";
import { PainelArquivos } from "./PainelArquivos";
import type { ItemUpload } from "../tipos";

const item = (extra: Partial<ItemUpload> = {}): ItemUpload => ({
  id: "1",
  arquivo: new File(["x".repeat(1536)], "RPA - A - 15000001.doc"),
  estado: "pendente",
  progresso: 0,
  ...extra,
});

const montar = (itens: ItemUpload[], extra: Record<string, unknown> = {}) => {
  const acoes = { aoEnviar: vi.fn(), aoCancelar: vi.fn(), aoRemover: vi.fn(), aoTentarNovamente: vi.fn() };
  render(<PainelArquivos itens={itens} tipo="word" rotuloEnviar="Carregar 1 arquivo(s)" {...acoes} {...extra} />);
  return acoes;
};

test("mostra nome com extensão, tamanho e barra de progresso acessível", () => {
  montar([item({ estado: "enviando", progresso: 40 })]);
  expect(screen.getByRole("heading", { name: "Arquivos enviados" })).toBeInTheDocument();
  expect(screen.getByText("RPA - A - 15000001.doc")).toBeInTheDocument();
  expect(screen.getByText("1,5 KB")).toBeInTheDocument();
  const barra = screen.getByRole("progressbar", { name: /RPA - A - 15000001\.doc/ });
  expect(barra).toHaveAttribute("aria-valuenow", "40");
  expect(barra).toHaveAttribute("aria-valuemin", "0");
  expect(barra).toHaveAttribute("aria-valuemax", "100");
  expect(screen.getByText("40%")).toBeInTheDocument();
});

test("falha aparece em vermelho com a mensagem e o botão de tentar de novo", () => {
  const { aoTentarNovamente } = montar([item({ estado: "erro", mensagem: "Falha de conexão" })]);
  expect(screen.getByRole("alert")).toHaveTextContent("Falha de conexão");
  fireEvent.click(screen.getByRole("button", { name: "Tentar de novo: RPA - A - 15000001.doc" }));
  expect(aoTentarNovamente).toHaveBeenCalledWith("1");
});

test("remove o arquivo e dispara cancelar e enviar", () => {
  const { aoRemover, aoCancelar, aoEnviar } = montar([item()]);
  fireEvent.click(screen.getByRole("button", { name: "Remover RPA - A - 15000001.doc" }));
  expect(aoRemover).toHaveBeenCalledWith("1");
  fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(aoCancelar).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Carregar 1 arquivo(s)" }));
  expect(aoEnviar).toHaveBeenCalled();
});

test("enviado e ignorado mostram o estado e não oferecem nova tentativa", () => {
  montar([
    item({ id: "a", estado: "ok", progresso: 100 }),
    item({ id: "b", estado: "ignorado", progresso: 100, arquivo: new File(["x"], "b.docx") }),
  ]);
  expect(screen.getByText("Enviado")).toBeInTheDocument();
  expect(screen.getByText("Já carregado (ignorado)")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Tentar de novo/ })).not.toBeInTheDocument();
});

test("o ícone muda conforme o tipo: Word ou planilha", () => {
  const { container } = render(
    <PainelArquivos itens={[item()]} tipo="planilha" rotuloEnviar="Enviar" aoEnviar={() => {}} aoCancelar={() => {}} aoRemover={() => {}} aoTentarNovamente={() => {}} />,
  );
  expect(container.querySelector('svg[data-icone="planilha"]')).not.toBeNull();
  expect(within(container).queryByText("Arquivos enviados")).toBeInTheDocument();
});

test("sem itens o envio fica desabilitado", () => {
  montar([], { rotuloEnviar: "Enviar" });
  expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
});
