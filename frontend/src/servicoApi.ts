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

type OpcoesEnvio = {
  /** bytes enviados / total do corpo; quando informado o envio usa XMLHttpRequest (o fetch não reporta progresso de upload) */
  progresso?: (enviados: number, total: number) => void;
  sinal?: AbortSignal;
};

function enviarComProgresso(caminho: string, init: RequestInit, opcoes: OpcoesEnvio): Promise<Response> {
  return new Promise((resolve, reject) => {
    const cancelado = () => new DOMException("Envio cancelado.", "AbortError");
    if (opcoes.sinal?.aborted) return reject(cancelado());
    const xhr = new XMLHttpRequest();
    xhr.open(init.method ?? "POST", caminho);
    new Headers(init.headers).forEach((valor, nome) => xhr.setRequestHeader(nome, valor));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opcoes.progresso?.(e.loaded, e.total);
    };
    xhr.onload = () =>
      resolve(
        new Response(xhr.responseText, {
          status: xhr.status,
          headers: { "Content-Type": xhr.getResponseHeader("Content-Type") ?? "application/json" },
        }),
      );
    xhr.onerror = () => reject(new ErroApi(0, "Falha de conexão durante o envio. Tente de novo."));
    xhr.onabort = () => reject(cancelado());
    opcoes.sinal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(init.body as XMLHttpRequestBodyInit | null);
  });
}

async function requisitar(
  caminho: string,
  init: RequestInit = {},
  tentouRenovar = false,
  envio?: OpcoesEnvio,
): Promise<Response> {
  let atual = sessao.obter();
  if (atual && new Date(atual.expira_em).getTime() - Date.now() < MARGEM_RENOVACAO_MS && !tentouRenovar) {
    if (await renovarSessao()) atual = sessao.obter();
  }
  const headers = new Headers(init.headers);
  if (atual) headers.set("Authorization", `Bearer ${atual.id_token}`);
  const r = envio?.progresso ? await enviarComProgresso(caminho, { ...init, headers }, envio) : await fetch(caminho, { ...init, headers });
  if (r.status === 401 && atual) {
    if (!tentouRenovar && (await renovarSessao())) return requisitar(caminho, init, true, envio);
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
  opcoes: { progresso?: (fracao: number) => void; sinal?: AbortSignal } = {},
): Promise<ResultadoPlanilha> {
  const form = new FormData();
  form.append("arquivo", arquivo);
  form.append("competencia", competencia);
  if (prevalece) form.append("prevalece", prevalece);
  const { progresso, sinal } = opcoes;
  const r = await requisitar(
    "/api/planilhas",
    { method: "POST", body: form },
    false,
    progresso ? { progresso: (enviados, total) => progresso(total ? enviados / total : 0), sinal } : undefined,
  );
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
  opcoes: {
    substituir?: boolean;
    progresso?: (enviados: number) => void;
    /** fração (0 a 1) já enviada de cada arquivo; estimada pela ordem e pelo tamanho dos arquivos dentro do lote */
    progressoArquivo?: (indice: number, fracao: number) => void;
    /** chamado ao fim de cada lote, com os resultados e o intervalo [inicio, fim) de arquivos */
    aoLote?: (resultados: ResultadoArquivo[], inicio: number, fim: number) => void;
    sinal?: AbortSignal;
  } = {},
): Promise<ResultadoArquivo[]> {
  const todos: ResultadoArquivo[] = [];
  for (let i = 0; i < arquivos.length; i += TAMANHO_LOTE) {
    const lote = arquivos.slice(i, i + TAMANHO_LOTE);
    const form = new FormData();
    form.append("competencia", competencia);
    form.append("substituir", opcoes.substituir ? "true" : "false");
    lote.forEach((a) => form.append("arquivos", a));
    const { progressoArquivo, sinal } = opcoes;
    const r = await requisitar(
      "/api/rpas",
      { method: "POST", body: form },
      false,
      progressoArquivo
        ? {
            sinal,
            progresso: (enviados, total) => {
              // o corpo leva os arquivos em sequência: distribui os bytes enviados pela ordem e pelo tamanho
              let restante = total ? (enviados / total) * lote.reduce((s, a) => s + a.size, 0) : 0;
              lote.forEach((a, j) => {
                const parte = Math.min(Math.max(restante, 0), a.size);
                progressoArquivo(i + j, a.size ? parte / a.size : 1);
                restante -= a.size;
              });
            },
          }
        : undefined,
    );
    const resultados: ResultadoArquivo[] = (await r.json()).resultados;
    todos.push(...resultados);
    opcoes.aoLote?.(resultados, i, i + lote.length);
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
