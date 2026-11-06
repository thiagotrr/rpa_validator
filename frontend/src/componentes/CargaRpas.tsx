import { useEffect, useState } from "react";
import { avisosDoEnvio } from "../avisosEnvio";
import { competenciaAtual } from "../competencia";
import { enviarRpas, verificarEnvioRpas } from "../servicoApi";
import { ROTULOS_CAMPO, type ResultadoArquivo, type VerificacaoEnvio } from "../tipos";
import { AreaArquivos } from "./AreaArquivos";
import { SeletorCompetencia } from "./SeletorCompetencia";

export function CargaRpas({ aoCarregar }: { aoCarregar: () => void }) {
  const [competencia, setCompetencia] = useState(competenciaAtual);
  const [selecionados, setSelecionados] = useState<File[]>([]);
  const [verificacao, setVerificacao] = useState<VerificacaoEnvio | null>(null);
  const [substituir, setSubstituir] = useState(false);
  const [resultados, setResultados] = useState<ResultadoArquivo[]>([]);
  const [progresso, setProgresso] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Antes de carregar: a planilha existe? o quantitativo confere? (só os nomes vão ao servidor)
  useEffect(() => {
    let atual = true;
    verificarEnvioRpas(competencia, selecionados)
      .then((v) => atual && (setVerificacao(v), setErro(null)))
      .catch((e: Error) => atual && (setVerificacao(null), setErro(e.message)));
    return () => {
      atual = false;
    };
  }, [competencia, selecionados]);

  async function carregar() {
    setEnviando(true);
    setErro(null);
    setResultados([]);
    try {
      const r = await enviarRpas(competencia, selecionados, {
        substituir,
        progresso: (n) => setProgresso(`${n}/${selecionados.length} enviados`),
      });
      setResultados(r);
      setSelecionados([]);
      setSubstituir(false);
      aoCarregar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setEnviando(false);
      setProgresso(null);
    }
  }

  const avisos = verificacao ? avisosDoEnvio(verificacao, substituir) : [];
  const bloqueado = !verificacao?.planilha_carregada;
  const qtd = (status: ResultadoArquivo["status"]) => resultados.filter((r) => r.status === status).length;
  const detalhes = resultados.filter((r) => r.status === "erro" || r.campos_ausentes?.length);

  return (
    <section className="cartao">
      <h2>Carga dos RPAs</h2>
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
        aoEscolher={setSelecionados}
      />
      {selecionados.length > 0 && <p className="meta">{selecionados.length} arquivo(s) escolhido(s).</p>}
      {(verificacao?.qtd_ja_existentes_no_envio ?? 0) > 0 && (
        <label className="linha">
          <input type="checkbox" checked={substituir} onChange={(e) => setSubstituir(e.target.checked)} />
          Substituir RPAs já carregados
        </label>
      )}
      <button disabled={enviando || bloqueado || selecionados.length === 0} onClick={() => void carregar()}>
        {enviando ? "Carregando…" : `Carregar ${selecionados.length} arquivo(s)`}
      </button>
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
