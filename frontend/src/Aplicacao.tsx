import { useCallback, useEffect, useState } from "react";
import { competenciaAtual } from "./competencia";
import { ErroApi, obterRelatorio, sessao } from "./servicoApi";
import { CargaPlanilha } from "./componentes/CargaPlanilha";
import { CargaRpas } from "./componentes/CargaRpas";
import { SeletorCompetencia } from "./componentes/SeletorCompetencia";
import { TelaAcesso } from "./componentes/TelaAcesso";
import { TelaRelatorio } from "./componentes/TelaRelatorio";
import { IconePlanilhaMenu, IconeRelatorio, IconeRpasMenu, IconeSair } from "./componentes/Icones";
import type { Relatorio } from "./tipos";

type Secao = "planilha" | "rpas" | "relatorio";
const SECOES = [
  { id: "planilha", rotulo: "Carga da planilha", Icone: IconePlanilhaMenu },
  { id: "rpas", rotulo: "Carga dos RPAs", Icone: IconeRpasMenu },
  { id: "relatorio", rotulo: "Relatório", Icone: IconeRelatorio },
] as const;

export function Aplicacao() {
  const [logado, setLogado] = useState(() => sessao.obter() !== null);
  const [competencia, setCompetencia] = useState(competenciaAtual); // do relatório; cada carga tem a sua
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [secao, setSecao] = useState<Secao>("planilha");

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
    <div className="layout">
      <aside className="lateral">
        <div className="marca">Validador de RPAs</div>
        <nav aria-label="Menu principal">
          <ul>
            {SECOES.map(({ id, rotulo, Icone }) => (
              <li key={id}>
                <button
                  type="button"
                  className="item-menu"
                  aria-current={secao === id ? "page" : undefined}
                  onClick={() => setSecao(id)}
                >
                  <Icone />
                  <span>{rotulo}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <button type="button" className="item-menu sair" onClick={() => { sessao.sair(); setLogado(false); }}>
          <IconeSair />
          <span>Sair</span>
        </button>
      </aside>
      <main>
        {/* as seções ficam montadas: trocar de menu não perde a lista de arquivos nem o andamento do envio */}
        <div hidden={secao !== "planilha"}>
          <CargaPlanilha aoCarregar={atualizar} />
        </div>
        <div hidden={secao !== "rpas"}>
          <CargaRpas aoCarregar={atualizar} />
        </div>
        <div hidden={secao !== "relatorio"}>
          <section className="cartao" aria-labelledby="titulo-relatorio">
            <div className="titulo">
              <h2 id="titulo-relatorio">Relatório</h2>
              <SeletorCompetencia valor={competencia} aoMudar={setCompetencia} />
            </div>
            {aviso && <p>{aviso}</p>}
          </section>
          {relatorio && <TelaRelatorio r={relatorio} />}
        </div>
      </main>
    </div>
  );
}
