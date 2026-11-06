export type Divergencia = {
  numero_rpa: string;
  codigo_empresa: string | null;
  nome: string | null; // já vem ofuscado do backend
  campo: string;
  tipo: string;
  valor_planilha: string | null;
  valor_documento: string | null;
  diferenca_centavos: number | null;
};

export type Relatorio = {
  competencia: string;
  gerado_em: string;
  tolerancia_centavos: number;
  qtd_documentos: number;
  valor_total_documentos: number; // centavos
  qtd_linhas_referencia: number;
  qtd_divergencias: number;
  divergencias_por_campo: Record<string, number>;
  divergencias: Divergencia[];
};

export type ResultadoArquivo = {
  arquivo: string;
  status: "ok" | "erro" | "ja_carregado";
  numero_rpa?: string;
  metodo?: string;
  campos_ausentes?: string[];
  erro?: string;
};

export type AbaCarregada = {
  aba: string;
  codigo_empresa: string;
  cnpj: string;
  competencia: string;
  qtd_linhas: number;
  qtd_linhas_sem_recibo: number;
};

export type ResultadoPlanilha = {
  competencia: string; // onde foi gravada
  competencia_arquivo: string; // a que está na célula A2
  abas: AbaCarregada[];
  erros_abas: { aba: string; mensagem: string }[];
  qtd_linhas_substituidas: number;
};

export type SituacaoPlanilha = {
  competencia: string;
  carregada: boolean;
  qtd_linhas: number;
  empresas: string[];
};

export type VerificacaoEnvio = {
  competencia: string;
  planilha_carregada: boolean;
  qtd_linhas_planilha: number;
  qtd_arquivos: number;
  qtd_sem_numero: number;
  qtd_repetidos_no_envio: number;
  qtd_ja_carregados: number;
  qtd_ja_existentes_no_envio: number;
  qtd_novos: number;
  qtd_total_apos_envio: number;
  diferenca: number; // total após o envio - linhas da planilha (negativo = faltam RPAs)
  confere: boolean;
};

export type Prevalece = "arquivo" | "tela";

export const ROTULOS_CAMPO: Record<string, string> = {
  registro: "Registro",
  inss: "INSS",
  irrf: "IRRF",
  sest_senat: "SEST/SENAT",
  data_emissao: "Data de emissão",
  data_nascimento: "Data de nascimento",
};

export const ROTULOS_TIPO: Record<string, string> = {
  VALOR_DIFERENTE: "Valor diferente",
  DATA_DIFERENTE: "Data diferente",
  DATA_FORA_COMPETENCIA: "Emissão fora da competência",
  CAMPO_NAO_EXTRAIDO: "Campo não extraído",
  RPA_SEM_REFERENCIA: "RPA sem linha na planilha",
  REFERENCIA_SEM_RPA: "Linha da planilha sem RPA",
};

export const brl = (centavos: number) =>
  (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
