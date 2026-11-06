/** Competência no formato AAAA-MM em toda a aplicação. */
export const competenciaAtual = (agora: Date = new Date()): string =>
  `${agora.getFullYear()}-${String(agora.getMonth() + 1).padStart(2, "0")}`;

export const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

export const partesDaCompetencia = (c: string): { ano: string; mes: string } => {
  const [ano, mes] = c.split("-");
  return { ano, mes };
};
