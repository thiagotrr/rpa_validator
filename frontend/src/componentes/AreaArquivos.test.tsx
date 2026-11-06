import { fireEvent, render, screen } from "@testing-library/react";
import { AreaArquivos } from "./AreaArquivos";

const arquivo = (nome: string) => new File(["x"], nome);
const soltar = (...arquivos: File[]) =>
  fireEvent.drop(screen.getByTestId("area-arquivos"), { dataTransfer: { files: arquivos } });

test("modo único aceita um .xlsx arrastado", () => {
  const aoEscolher = vi.fn();
  render(<AreaArquivos rotulo="Planilha" aceita={[".xlsx"]} multiplo={false} aoEscolher={aoEscolher} />);
  soltar(arquivo("Nova Lima.XLSX"));
  expect(aoEscolher).toHaveBeenCalledWith([expect.objectContaining({ name: "Nova Lima.XLSX" })]);
});

test("modo único recusa mais de um arquivo", () => {
  const aoEscolher = vi.fn();
  render(<AreaArquivos rotulo="Planilha" aceita={[".xlsx"]} multiplo={false} aoEscolher={aoEscolher} />);
  soltar(arquivo("a.xlsx"), arquivo("b.xlsx"));
  expect(aoEscolher).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("único arquivo");
});

test("formato não aceito não é enviado", () => {
  const aoEscolher = vi.fn();
  render(<AreaArquivos rotulo="Planilha" aceita={[".xlsx"]} multiplo={false} aoEscolher={aoEscolher} />);
  soltar(arquivo("a.csv"));
  expect(aoEscolher).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("Formato não aceito");
});

test("modo múltiplo aceita o conjunto e avisa dos ignorados", () => {
  const aoEscolher = vi.fn();
  render(<AreaArquivos rotulo="RPAs" aceita={[".doc", ".docx"]} multiplo aoEscolher={aoEscolher} />);
  soltar(arquivo("a.doc"), arquivo("b.docx"), arquivo("c.pdf"));
  expect(aoEscolher.mock.calls[0][0].map((f: File) => f.name)).toEqual(["a.doc", "b.docx"]);
  expect(screen.getByRole("alert")).toHaveTextContent("1 arquivo(s) ignorado(s)");
});

test("o botão de escolha também funciona", () => {
  const aoEscolher = vi.fn();
  render(<AreaArquivos rotulo="RPAs" aceita={[".doc"]} multiplo aoEscolher={aoEscolher} />);
  fireEvent.change(screen.getByLabelText("RPAs"), { target: { files: [arquivo("a.doc")] } });
  expect(aoEscolher).toHaveBeenCalledTimes(1);
});

test("mostra o botão 'Escolher arquivos' e a lista de formatos aceitos", () => {
  render(<AreaArquivos rotulo="RPAs" aceita={[".doc", ".docx"]} multiplo aoEscolher={() => {}} />);
  expect(screen.getByText("Escolher arquivos")).toBeInTheDocument();
  expect(screen.getByText(/\.doc, \.docx/)).toBeInTheDocument();
});

test("no modo único o botão se chama 'Escolher arquivo'", () => {
  render(<AreaArquivos rotulo="Planilha" aceita={[".xlsx"]} multiplo={false} aoEscolher={() => {}} />);
  expect(screen.getByText("Escolher arquivo")).toBeInTheDocument();
});
