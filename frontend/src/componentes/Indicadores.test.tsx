import { render, screen } from "@testing-library/react";
import { Indicadores } from "./Indicadores";
import type { Relatorio } from "../tipos";

const base: Relatorio = {
  competencia: "2026-10", gerado_em: "2026-11-04T15:00:00+00:00", tolerancia_centavos: 2, qtd_documentos: 25,
  valor_total_documentos: 16575424, qtd_linhas_referencia: 25, qtd_divergencias: 2,
  divergencias_por_campo: { inss: 1, sest_senat: 1 }, divergencias: [],
};

test("mostra totais e divergências por campo", () => {
  render(<Indicadores r={base} />);
  expect(screen.getByText("R$ 165.754,24")).toBeInTheDocument();
  expect(screen.getByText("SEST/SENAT")).toBeInTheDocument();
  expect(screen.getByText("Divergências").nextSibling).toHaveTextContent("2");
  expect(screen.getByText("diferenças até R$ 0,02 ignoradas")).toBeInTheDocument();
});

test("sem divergências não mostra cards por campo", () => {
  render(<Indicadores r={{ ...base, qtd_divergencias: 0, divergencias_por_campo: {} }} />);
  expect(screen.queryByText("INSS")).not.toBeInTheDocument();
});
