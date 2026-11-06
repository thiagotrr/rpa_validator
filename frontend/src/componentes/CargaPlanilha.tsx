import { useCallback, useEffect, useState } from "react";
import { competenciaAtual } from "../competencia";
import { ErroApi, enviarPlanilha, obterSituacaoPlanilha } from "../servicoApi";
import type { Prevalece, ResultadoPlanilha, SituacaoPlanilha } from "../tipos";
import { AreaArquivos } from "./AreaArquivos";
import { SeletorCompetencia } from "./SeletorCompetencia";

type Divergente = { arquivo: File; competencia_arquivo: string; competencia_informada: string };

export function CargaPlanilha({ aoCarregar }: { aoCarregar: () => void }) {
  const [competencia, setCompetencia] = useState(competenciaAtual);
  const [situacao, setSituacao] = useState<SituacaoPlanilha | null>(null);
  const [resultado, setResultado] = useState<ResultadoPlanilha | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [pendente, setPendente] = useState<Divergente | null>(null);
  const [enviando, setEnviando] = useState(false);

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
    setErro(null);
    setResultado(null);
    setPendente(null);
    setEnviando(true);
    try {
      const r = await enviarPlanilha(arquivo, competencia, prevalece);
      setResultado(r);
      setCompetencia(r.competencia);
      await atualizarSituacao(r.competencia);
      aoCarregar();
    } catch (e) {
      if (e instanceof ErroApi && e.status === 409 && e.detalhe?.codigo === "competencia_divergente") {
        setPendente({
          arquivo,
          competencia_arquivo: String(e.detalhe.competencia_arquivo),
          competencia_informada: String(e.detalhe.competencia_informada),
        });
      } else {
        setErro((e as Error).message);
      }
    } finally {
      setEnviando(false);
    }
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
        aoEscolher={([arquivo]) => void enviar(arquivo)}
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
      {erro && <p className="erro" role="alert">{erro}</p>}
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
