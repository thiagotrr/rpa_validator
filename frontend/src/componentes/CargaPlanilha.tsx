import { useCallback, useEffect, useRef, useState } from "react";
import { competenciaAtual } from "../competencia";
import { novoId } from "../identificador";
import { ErroApi, enviarPlanilha, obterSituacaoPlanilha } from "../servicoApi";
import type { ItemUpload, Prevalece, ResultadoPlanilha, SituacaoPlanilha } from "../tipos";
import { AreaArquivos } from "./AreaArquivos";
import { PainelArquivos } from "./PainelArquivos";
import { SeletorCompetencia } from "./SeletorCompetencia";

type Divergente = { arquivo: File; competencia_arquivo: string; competencia_informada: string };

export function CargaPlanilha({ aoCarregar }: { aoCarregar: () => void }) {
  const [competencia, setCompetencia] = useState(competenciaAtual);
  const [situacao, setSituacao] = useState<SituacaoPlanilha | null>(null);
  const [resultado, setResultado] = useState<ResultadoPlanilha | null>(null);
  const [item, setItem] = useState<ItemUpload | null>(null);
  const [pendente, setPendente] = useState<Divergente | null>(null);
  const [enviando, setEnviando] = useState(false);
  const controle = useRef<AbortController | null>(null);

  const ajustar = (parte: Partial<ItemUpload>) => setItem((atual) => (atual ? { ...atual, ...parte } : atual));

  const atualizarSituacao = useCallback(async (c: string) => {
    try {
      setSituacao(await obterSituacaoPlanilha(c));
    } catch {
      setSituacao(null);
    }
  }, []);

  useEffect(() => {
    void atualizarSituacao(competencia);
  }, [competencia, atualizarSituacao]);

  async function enviar(arquivo: File, prevalece?: Prevalece) {
    setResultado(null);
    setPendente(null);
    setEnviando(true);
    ajustar({ estado: "enviando", progresso: 0, mensagem: undefined });
    controle.current = new AbortController();
    try {
      const r = await enviarPlanilha(arquivo, competencia, prevalece, {
        progresso: (f) => ajustar({ progresso: Math.round(f * 100) }),
        sinal: controle.current.signal,
      });
      ajustar({ estado: "ok", progresso: 100 });
      setResultado(r);
      setCompetencia(r.competencia);
      await atualizarSituacao(r.competencia);
      aoCarregar();
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      if (e instanceof ErroApi && e.status === 409 && e.detalhe?.codigo === "competencia_divergente") {
        ajustar({ estado: "pendente", progresso: 0 });
        setPendente({
          arquivo,
          competencia_arquivo: String(e.detalhe.competencia_arquivo),
          competencia_informada: String(e.detalhe.competencia_informada),
        });
      } else {
        ajustar({ estado: "erro", mensagem: (e as Error).message });
      }
    } finally {
      setEnviando(false);
    }
  }

  function escolher(arquivo: File) {
    setResultado(null);
    setPendente(null);
    setItem({ id: novoId(), arquivo, estado: "pendente", progresso: 0 });
  }

  function cancelar() {
    controle.current?.abort();
    setItem(null);
    setPendente(null);
    setEnviando(false);
  }

  return (
    <section className="cartao">
      <h2>Carga da planilha</h2>
      <SeletorCompetencia valor={competencia} aoMudar={setCompetencia} />
      {situacao?.carregada && (
        <p className="aviso">
          Já existe planilha para {competencia} ({situacao.qtd_linhas} linhas, {situacao.empresas.length} empresa(s)). A
          nova carga substitui tudo desta competência.
        </p>
      )}
      <AreaArquivos
        rotulo="Planilha de conferência (.xlsx)"
        aceita={[".xlsx"]}
        multiplo={false}
        desabilitado={enviando}
        aoEscolher={([arquivo]) => escolher(arquivo)}
      />
      <PainelArquivos
        itens={item ? [item] : []}
        tipo="planilha"
        rotuloEnviar="Enviar planilha"
        enviando={enviando}
        desabilitadoEnviar={enviando || item?.estado === "ok"}
        aoEnviar={() => item && void enviar(item.arquivo)}
        aoTentarNovamente={() => item && void enviar(item.arquivo)}
        aoRemover={cancelar}
        aoCancelar={cancelar}
      />
      {pendente && (
        <div className="aviso" role="alertdialog" aria-label="Competência divergente">
          <p>
            A planilha é de <strong>{pendente.competencia_arquivo}</strong>, mas você escolheu{" "}
            <strong>{pendente.competencia_informada}</strong>. Qual vale?
          </p>
          <button onClick={() => void enviar(pendente.arquivo, "arquivo")}>
            Usar a da planilha ({pendente.competencia_arquivo})
          </button>
          <button onClick={() => void enviar(pendente.arquivo, "tela")}>
            Usar a escolhida ({pendente.competencia_informada})
          </button>
          <button className="secundario" onClick={() => setPendente(null)}>Cancelar</button>
        </div>
      )}
      {resultado && (
        <div>
          <p>
            Competência {resultado.competencia} carregada:{" "}
            {resultado.abas.map((a) => `${a.aba} (empresa ${a.codigo_empresa}: ${a.qtd_linhas} linhas)`).join("; ")}.
            {resultado.qtd_linhas_substituidas > 0 && ` Substituiu ${resultado.qtd_linhas_substituidas} linhas anteriores.`}
          </p>
          {resultado.erros_abas.length > 0 && (
            <ul className="erros" aria-label="Abas com erro">
              {resultado.erros_abas.map((e) => (
                <li key={e.aba}>Aba {e.aba} não importada: {e.mensagem}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
