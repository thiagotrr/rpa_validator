import { fireEvent, render, screen } from "@testing-library/react";
import { competenciaAtual } from "../competencia";
import { SeletorCompetencia } from "./SeletorCompetencia";

test("a competência padrão é o mês e o ano atuais", () => {
  expect(competenciaAtual(new Date(2026, 10, 5))).toBe("2026-11");
  expect(competenciaAtual(new Date(2027, 0, 31))).toBe("2027-01");
});

test("mostra mês e ano e troca o mês", () => {
  const aoMudar = vi.fn();
  render(<SeletorCompetencia valor="2026-11" aoMudar={aoMudar} />);
  expect(screen.getByLabelText("Mês")).toHaveValue("11");
  expect(screen.getByLabelText("Ano")).toHaveValue(2026);
  fireEvent.change(screen.getByLabelText("Mês"), { target: { value: "03" } });
  expect(aoMudar).toHaveBeenCalledWith("2026-03");
});

test("só aceita ano completo de 4 dígitos", () => {
  const aoMudar = vi.fn();
  render(<SeletorCompetencia valor="2026-11" aoMudar={aoMudar} />);
  fireEvent.change(screen.getByLabelText("Ano"), { target: { value: "202" } });
  expect(aoMudar).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Ano"), { target: { value: "2027" } });
  expect(aoMudar).toHaveBeenCalledWith("2027-11");
});
