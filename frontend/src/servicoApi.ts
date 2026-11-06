import type {
  Prevalece,
  Relatorio,
  ResultadoArquivo,
  ResultadoPlanilha,
  SituacaoPlanilha,
  VerificacaoEnvio,
} from "./tipos";

const CHAVE = "rpa-sessao";
const TAMANHO_LOTE = 10; // Cloud Run limita o corpo da requisição a 32 MB
const MARGEM_RENOVACAO_MS = 60_000;

type Sessao = { id_token: string; refresh_token: string; expira_em: string };

export class ErroApi extends Error {
  constructor(
    public status: number,
    message: string,
    public detalhe?: Record<string, unknown>, // `detail` quando a API devolve um objeto (ex.: competência divergente)
  ) {
    super(message);
  }
}

export const sessao = {
  obter: (): Sessao | null => {
    const bruto = sessionStorage.getItem(CHAVE);
    return bruto ? (JSON.parse(bruto) as Sessao) : null;
  },
  salvar: (s: Sessao) => sessionStorage.setItem(CHAVE, JSON.stringify(s)),
  sair: () => sessionStorage.removeItem(CHAVE),
};

async function lerErro(r: Response): Promise<ErroApi> {
  const corpo = await r.json().catch(() => ({}));
  if (typeof corpo.detail === "string") return new ErroApi(r.status, corpo.detail);
  if (corpo.detail && typeof corpo.detail === "object") {
    return new ErroApi(r.status, corpo.detail.mensagem ?? `erro ${r.status}`, corpo.detail);
  }
  return new ErroApi(r.status, `erro ${r.status}`);
}

function encerrarSessao() {
  sessao.sair();
  window.dispatchEvent(new Event("sessao-expirada"));
}

let renovacaoEmAndamento: Promise<boolean> | null = null;

async function renovarSessao(): Promise<boolean> {
  const atual = sessao.obter();
  if (!atual) return false;
  renovacaoEmAndamento ??= (async () => {
    const r = await fetch("/api/acesso/renovar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: atual.refresh_token }),
    });
    if (!r.ok) return false;
    sessao.salvar(await r.json());
    return true;
  })().finally(() => (renovacaoEmAndamento = null));
  return renovacaoEmAndamento;
}

async function requisitar(caminho: string, init: RequestInit = {}, tentouRenovar = false): Promise<Response> {
  let atual = sessao.obter();
  if (atual && new Date(atual.expira_em).getTime() - Date.now() < MARGEM_RENOVACAO_MS && !tentouRenovar) {
    if (await renovarSessao()) atual = sessao.obter();
  }
  const headers = new Headers(init.headers);
  if (atual) headers.set("Authorization", `Bearer ${atual.id_token}`);
  const r = await fetch(caminho, { ...init, headers });
  if (r.status === 401 && atual) {
    if (!tentouRenovar && (await renovarSessao())) return requisitar(caminho, init, true);
    encerrarSessao();
  }
  if (!r.ok) throw await lerErro(r);
  return r;
}

export async function entrar(email: string, senha: string): Promise<void> {
  const r = await fetch("/api/acesso/entrar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, senha }),
  });
  if (!r.ok) throw await lerErro(r);
  sessao.salvar(await r.json());
}

export async function enviarPlanilha(
  arquivo: File,
  competencia: string,
  prevalece?: Prevalece,
): Promise<ResultadoPlanilha> {
  const form = new FormData();
  form.append("arquivo", arquivo);
  form.append("competencia", competencia);
  if (prevalece) form.append("prevalece", prevalece);
  const r = await requisitar("/api/planilhas", { method: "POST", body: form });
  return r.json();
}

export async function obterSituacaoPlanilha(competencia: string): Promise<SituacaoPlanilha> {
  return (await requisitar(`/api/planilhas/${competencia}`)).json();
}

/** Só os NOMES dos arquivos vão na verificação: o número do RPA está no nome e nada pesado trafega. */
export async function verificarEnvioRpas(competencia: string, arquivos: File[]): Promise<VerificacaoEnvio> {
  const r = await requisitar("/api/rpas/verificacao", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ competencia, arquivos: arquivos.map((a) => a.name) }),
  });
  return r.json();
}

export async function enviarRpas(
  competencia: string,
  arquivos: File[],
  opcoes: { substituir?: boolean; progresso?: (enviados: number) => void } = {},
): Promise<ResultadoArquivo[]> {
  const todos: ResultadoArquivo[] = [];
  for (let i = 0; i < arquivos.length; i += TAMANHO_LOTE) {
    const form = new FormData();
    form.append("competencia", competencia);
    form.append("substituir", opcoes.substituir ? "true" : "false");
    arquivos.slice(i, i + TAMANHO_LOTE).forEach((a) => form.append("arquivos", a));
    const r = await requisitar("/api/rpas", { method: "POST", body: form });
    todos.push(...(await r.json()).resultados);
    opcoes.progresso?.(Math.min(i + TAMANHO_LOTE, arquivos.length));
  }
  return todos;
}

export async function obterRelatorio(competencia: string): Promise<Relatorio> {
  return (await requisitar(`/api/relatorios/${competencia}`)).json();
}

export async function exportarRelatorio(competencia: string, formato: "pdf" | "md"): Promise<void> {
  const r = await requisitar(`/api/relatorios/${competencia}/exportar?formato=${formato}`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `validacao-rpa-${competencia}.${formato}`;
  a.click();
  URL.revokeObjectURL(url);
}
