/** Tamanho legível em B, KB ou MB (vírgula decimal, como no restante da interface). */
export function formatarTamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const casas = (n: number) => n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (bytes < 1024 * 1024) return `${casas(bytes / 1024)} KB`;
  return `${casas(bytes / (1024 * 1024))} MB`;
}
