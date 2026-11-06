import { afterEach, expect, test, vi } from "vitest";
import {
  ErroApi,
  entrar,
  enviarPlanilha,
  enviarRpas,
  obterRelatorio,
  sessao,
  verificarEnvioRpas,
} from "./servicoApi";

afterEach(() => {
  vi.restoreAllMocks();
  sessao.sair();
});

const json = (corpo: unknown, status = 200) =>
  new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
const daquiA = (ms: number) => new Date(Date.now() + ms).toISOString();
const logar = () => sessao.salvar({ id_token: "t", refresh_token: "r", expira_em: daquiA(3_600_000) });

test("entrar guarda a sessão e as chamadas seguintes enviam Bearer", async () => {
  const f = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ id_token: "abc", refresh_token: "r", expira_em: daquiA(3_600_000) }))
    .mockResolvedValueOnce(json({ competencia: "2026-10" }));
  await entrar("a@x.com", "senha");
  await obterRelatorio("2026-10");
  expect(new Headers(f.mock.calls[1][1]!.headers).get("Authorization")).toBe("Bearer abc");
});

test("401 renova a sessão uma vez e repete a chamada", async () => {
  sessao.salvar({ id_token: "velho", refresh_token: "r", expira_em: daquiA(3_600_000) });
  const f = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ detail: "token inválido" }, 401))
    .mockResolvedValueOnce(json({ id_token: "novo", refresh_token: "r2", expira_em: daquiA(3_600_000) }))
    .mockResolvedValueOnce(json({ competencia: "2026-10" }));
  await obterRelatorio("2026-10");
  expect(f.mock.calls[1][0]).toBe("/api/acesso/renovar");
  expect(new Headers(f.mock.calls[2][1]!.headers).get("Authorization")).toBe("Bearer novo");
});

test("se a renovação falha, a sessão é encerrada", async () => {
  sessao.salvar({ id_token: "velho", refresh_token: "r", expira_em: daquiA(3_600_000) });
  const ouvinte = vi.fn();
  window.addEventListener("sessao-expirada", ouvinte);
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ detail: "token inválido" }, 401))
    .mockResolvedValueOnce(json({ detail: "sessão expirada" }, 401));
  await expect(obterRelatorio("2026-10")).rejects.toThrow("token inválido");
  expect(sessao.obter()).toBeNull();
  expect(ouvinte).toHaveBeenCalled();
});

test("token perto de expirar é renovado antes da chamada", async () => {
  sessao.salvar({ id_token: "quase", refresh_token: "r", expira_em: daquiA(10_000) });
  const f = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ id_token: "novo", refresh_token: "r2", expira_em: daquiA(3_600_000) }))
    .mockResolvedValueOnce(json({ competencia: "2026-10" }));
  await obterRelatorio("2026-10");
  expect(f.mock.calls[0][0]).toBe("/api/acesso/renovar");
});

test("RPAs são enviados em lotes de 10", async () => {
  logar();
  const f = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async () => json({ resultados: [{ arquivo: "x", status: "ok" }] }));
  const arquivos = Array.from({ length: 23 }, (_, i) => new File(["x"], `RPA ${i}.doc`));
  expect(await enviarRpas("2026-10", arquivos)).toHaveLength(3);
  expect(f).toHaveBeenCalledTimes(3);
});

test("cada lote de RPAs leva a opção de substituir", async () => {
  logar();
  const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ resultados: [] }));
  await enviarRpas("2026-10", [new File(["x"], "RPA 15000001.doc")], { substituir: true });
  const form = f.mock.calls[0][1]!.body as FormData;
  expect([form.get("competencia"), form.get("substituir")]).toEqual(["2026-10", "true"]);
});

test("a planilha vai com a competência escolhida e, se houver, qual delas prevalece", async () => {
  logar();
  const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ competencia: "2026-10" }));
  await enviarPlanilha(new File(["x"], "p.xlsx"), "2026-11", "tela");
  const form = f.mock.calls[0][1]!.body as FormData;
  expect([form.get("competencia"), form.get("prevalece")]).toEqual(["2026-11", "tela"]);
});

test("competência divergente chega como ErroApi com o detalhe", async () => {
  logar();
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    json({ detail: { codigo: "competencia_divergente", mensagem: "diverge", competencia_arquivo: "2026-10" } }, 409),
  );
  const erro = await enviarPlanilha(new File(["x"], "p.xlsx"), "2026-11").catch((e) => e);
  expect(erro).toBeInstanceOf(ErroApi);
  expect([erro.status, erro.message, erro.detalhe.codigo]).toEqual([409, "diverge", "competencia_divergente"]);
});

test("a verificação envia só os nomes dos arquivos", async () => {
  logar();
  const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ confere: true }));
  await verificarEnvioRpas("2026-10", [new File(["conteudo"], "RPA - A - 15000001.doc")]);
  expect(f.mock.calls[0][0]).toBe("/api/rpas/verificacao");
  expect(JSON.parse(f.mock.calls[0][1]!.body as string)).toEqual({
    competencia: "2026-10",
    arquivos: ["RPA - A - 15000001.doc"],
  });
});

class XhrFalso {
  static ultimo: XhrFalso;
  static progresso = { loaded: 50, total: 100 };
  upload: { onprogress?: (e: unknown) => void } = {};
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  status = 200;
  responseText = JSON.stringify({ competencia: "2026-10", resultados: [] });
  cabecalhos: Record<string, string> = {};
  metodo = "";
  url = "";
  corpo: unknown;
  abortado = false;
  open(metodo: string, url: string) {
    this.metodo = metodo;
    this.url = url;
  }
  setRequestHeader(k: string, v: string) {
    this.cabecalhos[k] = v;
  }
  getResponseHeader() {
    return "application/json";
  }
  send(corpo: unknown) {
    XhrFalso.ultimo = this;
    this.corpo = corpo;
    queueMicrotask(() => {
      if (this.abortado) return;
      this.upload.onprogress?.({ lengthComputable: true, ...XhrFalso.progresso });
      this.onload?.();
    });
  }
  abort() {
    this.abortado = true;
    this.onabort?.();
  }
}

test("a planilha com progresso usa XMLHttpRequest, com Bearer, e reporta a fração enviada", async () => {
  logar();
  vi.stubGlobal("XMLHttpRequest", XhrFalso);
  const fetchEspiao = vi.spyOn(globalThis, "fetch");
  const fracoes: number[] = [];
  const r = await enviarPlanilha(new File(["x"], "p.xlsx"), "2026-10", undefined, {
    progresso: (f) => fracoes.push(f),
  });
  expect(r.competencia).toBe("2026-10");
  expect(fetchEspiao).not.toHaveBeenCalled();
  expect(XhrFalso.ultimo.cabecalhos["authorization"]).toBe("Bearer t");
  expect(XhrFalso.ultimo.url).toBe("/api/planilhas");
  expect(fracoes).toContain(0.5);
  vi.unstubAllGlobals();
});

test("os RPAs com progresso por arquivo distribuem os bytes enviados na ordem do lote", async () => {
  logar();
  vi.stubGlobal("XMLHttpRequest", XhrFalso);
  const chamadas: [number, number][] = [];
  const lotes: number[][] = [];
  await enviarRpas("2026-10", [new File(["xxxx"], "a.doc"), new File(["xxxx"], "b.doc")], {
    progressoArquivo: (i, f) => chamadas.push([i, f]),
    aoLote: (_r, inicio, fim) => lotes.push([inicio, fim]),
  });
  expect(chamadas).toContainEqual([0, 1]);
  expect(chamadas).toContainEqual([1, 0]);
  expect(lotes).toEqual([[0, 2]]);
  vi.unstubAllGlobals();
});

test("o envio com progresso pode ser cancelado", async () => {
  logar();
  vi.stubGlobal("XMLHttpRequest", XhrFalso);
  const controle = new AbortController();
  const promessa = enviarPlanilha(new File(["x"], "p.xlsx"), "2026-10", undefined, {
    progresso: () => {},
    sinal: controle.signal,
  });
  controle.abort();
  await expect(promessa).rejects.toMatchObject({ name: "AbortError" });
  vi.unstubAllGlobals();
});

test("falha de rede no envio com progresso vira ErroApi legível", async () => {
  logar();
  class XhrRede extends XhrFalso {
    send() {
      queueMicrotask(() => this.onerror?.());
    }
  }
  vi.stubGlobal("XMLHttpRequest", XhrRede);
  const erro = await enviarPlanilha(new File(["x"], "p.xlsx"), "2026-10", undefined, { progresso: () => {} }).catch(
    (e) => e,
  );
  expect(erro).toBeInstanceOf(ErroApi);
  expect(erro.message).toContain("conexão");
  vi.unstubAllGlobals();
});
