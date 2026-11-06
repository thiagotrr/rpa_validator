import type { VerificacaoEnvio } from "./tipos";

export type Aviso = { nivel: "bloqueio" | "aviso" | "info"; texto: string };

/** Mensagens mostradas ANTES de carregar os RPAs. Só o 'bloqueio' (sem planilha) impede o envio. */
export function avisosDoEnvio(v: VerificacaoEnvio, substituir: boolean): Aviso[] {
  if (!v.planilha_carregada) {
    return [
      { nivel: "bloqueio", texto: `Nenhuma planilha carregada para ${v.competencia}. Carregue a planilha antes dos RPAs.` },
    ];
  }
  if (v.qtd_arquivos === 0) {
    return [
      {
        nivel: v.confere ? "info" : "aviso",
        texto: `RPAs carregados: ${v.qtd_ja_carregados} de ${v.qtd_linhas_planilha} linhas da planilha.`,
      },
    ];
  }
  const avisos: Aviso[] = [];
  if (v.confere) {
    avisos.push({ nivel: "info", texto: `O quantitativo confere: ${v.qtd_total_apos_envio} RPAs para ${v.qtd_linhas_planilha} linhas.` });
  } else {
    const d = v.diferenca;
    avisos.push({
      nivel: "aviso",
      texto:
        `A planilha tem ${v.qtd_linhas_planilha} linhas e a competência ficará com ${v.qtd_total_apos_envio} RPAs ` +
        `após este envio (${d < 0 ? `faltam ${-d}` : `sobram ${d}`}). Você pode carregar assim mesmo e complementar depois.`,
    });
  }
  if (v.qtd_ja_existentes_no_envio > 0) {
    avisos.push({
      nivel: "aviso",
      texto: substituir
        ? `${v.qtd_ja_existentes_no_envio} arquivo(s) já carregados serão substituídos.`
        : `${v.qtd_ja_existentes_no_envio} arquivo(s) já estão carregados e serão ignorados.`,
    });
  }
  if (v.qtd_repetidos_no_envio > 0) {
    avisos.push({ nivel: "aviso", texto: `${v.qtd_repetidos_no_envio} arquivo(s) repetido(s) neste envio (mesmo número de RPA).` });
  }
  if (v.qtd_sem_numero > 0) {
    avisos.push({ nivel: "aviso", texto: `${v.qtd_sem_numero} arquivo(s) sem número de RPA no nome serão recusados.` });
  }
  return avisos;
}
