import { useCallback, useEffect, useState } from "react";
import { competenciaAtual } from "./competencia";
import { ErroApi, obterRelatorio, sessao } from "./servicoApi";
import { CargaPlanilha } from "./componentes/CargaPlanilha";
import { CargaRpas } from "./componentes/CargaRpas";
import { SeletorCompetencia } from "./componentes/SeletorCompetencia";
import { TelaAcesso } from "./componentes/TelaAcesso";
import { TelaRelatorio } from "./componentes/TelaRelatorio";
import type { Relatorio } from "./tipos";

export function Aplicacao() {
  const [logado, setLogado] = useState(() => sessao.obter() !== null);
  const [competencia, setCompetencia] = useState(competenciaAtual); // do relatório; cada carga tem a sua
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    const sair = () => setLogado(false);
    window.addEventListener("sessao-expirada", sair);
    return () => window.removeEventListener("sessao-expirada", sair);
  }, []);

  const atualizar = useCallback(async () => {
    setAviso(null);
    try {
      setRelatorio(await obterRelatorio(competencia));
    } catch (e) {
      setRelatorio(null);
      setAviso(e instanceof ErroApi && e.status === 404 ? "Nada carregado para esta competência ainda." : (e as Error).message);
    }
  }, [competencia]);

  useEffect(() => {
    if (logado) void atualizar();
  }, [logado, atualizar]);

  if (!logado) return <TelaAcesso aoEntrar={() => setLogado(true)} />;
  return (
    <main>
      <header>
        <h1>Validador de RPAs</h1>
        <button onClick={() => { sessao.sair(); setLogado(false); }}>Sair</button>
      </header>
      <CargaPlanilha aoCarregar={atualizar} />
      <CargaRpas aoCarregar={atualizar} />
      <section className="cartao">
        <div className="titulo">
          <h2>Relatório</h2>
          <SeletorCompetencia valor={competencia} aoMudar={setCompetencia} />
        </div>
        {aviso && <p>{aviso}</p>}
      </section>
      {relatorio && <TelaRelatorio r={relatorio} />}
    </main>
  );
}
