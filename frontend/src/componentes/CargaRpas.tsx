import { useEffect, useRef, useState } from "react";
import { avisosDoEnvio } from "../avisosEnvio";
import { competenciaAtual } from "../competencia";
import { novoId } from "../identificador";
import { enviarRpas, verificarEnvioRpas } from "../servicoApi";
import { ROTULOS_CAMPO, type ItemUpload, type ResultadoArquivo, type VerificacaoEnvio } from "../tipos";
import { AreaArquivos } from "./AreaArquivos";
import { PainelArquivos } from "./PainelArquivos";
import { SeletorCompetencia } from "./SeletorCompetencia";

const FINALIZADOS = ["ok", "ignorado"];

function itemDoResultado(item: ItemUpload, r: ResultadoArquivo | undefined): ItemUpload {
  if (!r) return { ...item, estado: "erro", mensagem: "O servidor não respondeu sobre este arquivo." };
  if (r.status === "ok") return { ...item, estado: "ok", progresso: 100, mensagem: undefined };
  if (r.status === "ja_carregado") return { ...item, estado: "ignorado", progresso: 100, mensagem: undefined };
  return { ...item, estado: "erro", mensagem: r.erro ?? "Erro ao processar o arquivo." };
}

export function CargaRpas({ aoCarregar }: { aoCarregar: () => void }) {
  const [competencia, setCompetencia] = useState(competenciaAtual);
  const [itens, setItens] = useState<ItemUpload[]>([]);
  const [verificacao, setVerificacao] = useState<VerificacaoEnvio | null>(null);
  const [substituir, setSubstituir] = useState(false);
  const [resultados, setResultados] = useState<ResultadoArquivo[]>([]);
  const [progresso, setProgresso] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const itensRef = useRef<ItemUpload[]>([]);
  const controle = useRef<AbortController | null>(null);
  itensRef.current = itens;

  const pendentes = itens.filter((i) => i.estado === "pendente");
  const chavePendentes = pendentes.map((i) => i.id).join("|");

  // Antes de carregar: a planilha existe? o quantitativo confere? (só os nomes vão ao servidor)
  useEffect(() => {
    let atual = true;
    const arquivos = itensRef.current.filter((i) => i.estado === "pendente").map((i) => i.arquivo);
    verificarEnvioRpas(competencia, arquivos)
      .then((v) => atual && (setVerificacao(v), setErro(null)))
      .catch((e: Error) => atual && (setVerificacao(null), setErro(e.message)));
    return () => {
      atual = false;
    };
  }, [competencia, chavePendentes]);

  const alterar = (ids: string[], mudar: (i: ItemUpload) => ItemUpload) =>
    setItens((todos) => todos.map((i) => (ids.includes(i.id) ? mudar(i) : i)));

  async function carregar(ids: string[]) {
    const alvo = itensRef.current.filter((i) => ids.includes(i.id));
    if (alvo.length === 0) return;
    setEnviando(true);
    setErro(null);
    controle.current = new AbortController();
    alterar(ids, (i) => ({ ...i, estado: "enviando", progresso: 0, mensagem: undefined }));
    const guardar = (novos: ResultadoArquivo[]) =>
      setResultados((antigos) => [...antigos.filter((a) => !novos.some((n) => n.arquivo === a.arquivo)), ...novos]);
    const aplicar = (trecho: ItemUpload[], r: ResultadoArquivo[]) => {
      const idsTrecho = trecho.map((i) => i.id);
      alterar(idsTrecho, (i) => itemDoResultado(i, r.find((x) => x.arquivo === i.arquivo.name)));
    };
    try {
      const todos = await enviarRpas(
        competencia,
        alvo.map((i) => i.arquivo),
        {
          substituir,
          sinal: controle.current.signal,
          progresso: (n) => setProgresso(`${n}/${alvo.length} enviados`),
          progressoArquivo: (indice, fracao) =>
            alterar([alvo[indice]?.id], (i) => ({ ...i, progresso: Math.round(fracao * 100) })),
          aoLote: (r, inicio, fim) => {
            aplicar(alvo.slice(inicio, fim), r);
            guardar(r);
          },
        },
      );
      guardar(todos);
      // o que não foi fechado lote a lote (ex.: resposta única) é fechado aqui, pelo nome do arquivo
      setItens((atuais) =>
        atuais.map((i) =>
          ids.includes(i.id) && i.estado === "enviando"
            ? itemDoResultado(i, todos.find((x) => x.arquivo === i.arquivo.name))
            : i,
        ),
      );
      setSubstituir(false);
      aoCarregar();
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        const mensagem = (e as Error).message;
        setItens((atuais) =>
          atuais.map((i) => (ids.includes(i.id) && i.estado === "enviando" ? { ...i, estado: "erro", mensagem } : i)),
        );
      }
    } finally {
      setEnviando(false);
      setProgresso(null);
    }
  }

  function escolher(arquivos: File[]) {
    setResultados([]);
    setItens((atuais) => [
      ...atuais,
      ...arquivos.map((arquivo): ItemUpload => ({ id: novoId(), arquivo, estado: "pendente", progresso: 0 })),
    ]);
  }

  function cancelar() {
    controle.current?.abort();
    setEnviando(false);
    setItens((atuais) => {
      const aberto = atuais.some((i) => !FINALIZADOS.includes(i.estado));
      return aberto ? atuais.filter((i) => FINALIZADOS.includes(i.estado)) : [];
    });
  }

  const avisos = verificacao ? avisosDoEnvio(verificacao, substituir) : [];
  const bloqueado = !verificacao?.planilha_carregada;
  const qtd = (status: ResultadoArquivo["status"]) => resultados.filter((r) => r.status === status).length;
  const detalhes = resultados.filter((r) => r.status === "erro" || r.campos_ausentes?.length);

  return (
    <section className="cartao" aria-labelledby="titulo-rpas">
      <h2 id="titulo-rpas">Carga dos RPAs</h2>
      <SeletorCompetencia valor={competencia} aoMudar={setCompetencia} />
      {avisos.map((a) => (
        <p key={a.texto} className={a.nivel === "info" ? "meta" : "aviso"} role={a.nivel === "bloqueio" ? "alert" : undefined}>
          {a.texto}
        </p>
      ))}
      <AreaArquivos
        rotulo="RPAs (.doc/.docx)"
        aceita={[".doc", ".docx"]}
        multiplo
        desabilitado={enviando || bloqueado}
        aoEscolher={escolher}
      />
      {(verificacao?.qtd_ja_existentes_no_envio ?? 0) > 0 && (
        <label className="linha">
          <input type="checkbox" checked={substituir} onChange={(e) => setSubstituir(e.target.checked)} />
          Substituir RPAs já carregados
        </label>
      )}
      <PainelArquivos
        itens={itens}
        tipo="word"
        rotuloEnviar={enviando ? "Carregando…" : `Carregar ${pendentes.length} arquivo(s)`}
        enviando={enviando}
        desabilitadoEnviar={enviando || bloqueado || pendentes.length === 0}
        aoEnviar={() => void carregar(pendentes.map((i) => i.id))}
        aoTentarNovamente={(id) => void carregar([id])}
        aoRemover={(id) => setItens((atuais) => atuais.filter((i) => i.id !== id))}
        aoCancelar={cancelar}
      />
      {progresso && <p className="meta">{progresso}</p>}
      {erro && <p className="erro" role="alert">{erro}</p>}
      {resultados.length > 0 && (
        <p>
          {qtd("ok")} processados, {qtd("ja_carregado")} já carregados (ignorados), {qtd("erro")} com erro.
        </p>
      )}
      {detalhes.length > 0 && (
        <ul className="erros">
          {detalhes.map((r) => (
            <li key={r.arquivo}>
              {r.arquivo}:{" "}
              {r.erro ?? `campos não extraídos: ${r.campos_ausentes!.map((c) => ROTULOS_CAMPO[c] ?? c).join(", ")}`}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
