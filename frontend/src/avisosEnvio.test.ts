import { avisosDoEnvio } from "./avisosEnvio";
import type { VerificacaoEnvio } from "./tipos";

const base: VerificacaoEnvio = {
  competencia: "2026-10",
  planilha_carregada: true,
  qtd_linhas_planilha: 25,
  qtd_arquivos: 20,
  qtd_sem_numero: 0,
  qtd_repetidos_no_envio: 0,
  qtd_ja_carregados: 0,
  qtd_ja_existentes_no_envio: 0,
  qtd_novos: 20,
  qtd_total_apos_envio: 20,
  diferenca: -5,
  confere: false,
};

test("sem planilha é bloqueio", () => {
  const [a] = avisosDoEnvio({ ...base, planilha_carregada: false, qtd_linhas_planilha: 0 }, false);
  expect(a.nivel).toBe("bloqueio");
  expect(a.texto).toContain("Nenhuma planilha carregada para 2026-10");
});

test("divergência de quantitativo é aviso, não bloqueio", () => {
  const avisos = avisosDoEnvio(base, false);
  expect(avisos.map((a) => a.nivel)).toEqual(["aviso"]);
  expect(avisos[0].texto).toContain("faltam 5");
  expect(avisos[0].texto).toContain("complementar depois");
});

test("sobram RPAs, repetidos, já carregados e sem número", () => {
  const v = {
    ...base,
    qtd_total_apos_envio: 27,
    diferenca: 2,
    qtd_repetidos_no_envio: 1,
    qtd_sem_numero: 2,
    qtd_ja_existentes_no_envio: 3,
  };
  const textos = avisosDoEnvio(v, false).map((a) => a.texto).join(" | ");
  expect(textos).toContain("sobram 2");
  expect(textos).toContain("3 arquivo(s) já estão carregados e serão ignorados");
  expect(textos).toContain("1 arquivo(s) repetido(s)");
  expect(textos).toContain("2 arquivo(s) sem número");
  expect(avisosDoEnvio(v, true).map((a) => a.texto).join(" ")).toContain("serão substituídos");
});

test("quantitativo que confere vira informação", () => {
  const v = { ...base, qtd_arquivos: 25, qtd_total_apos_envio: 25, diferenca: 0, confere: true };
  expect(avisosDoEnvio(v, false).map((a) => a.nivel)).toEqual(["info"]);
});
