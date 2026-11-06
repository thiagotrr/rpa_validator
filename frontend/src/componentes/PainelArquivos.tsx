import { formatarTamanho } from "../formatacao";
import type { EstadoItem, ItemUpload } from "../tipos";
import { IconeEnviar, IconeLixeira, IconePlanilha, IconeRepetir, IconeWord } from "./Icones";

type Props = {
  itens: ItemUpload[];
  tipo: "word" | "planilha";
  rotuloEnviar: string;
  aoEnviar: () => void;
  aoCancelar: () => void;
  aoRemover: (id: string) => void;
  aoTentarNovamente: (id: string) => void;
  enviando?: boolean;
  desabilitadoEnviar?: boolean;
};

const ROTULO_ESTADO: Record<EstadoItem, string> = {
  pendente: "Pronto para enviar",
  enviando: "Enviando",
  ok: "Enviado",
  ignorado: "Já carregado (ignorado)",
  erro: "Falha no envio",
};

/** Lista "Arquivos enviados": ícone, nome com extensão, tamanho, progresso, falha com nova tentativa e remoção. */
export function PainelArquivos({
  itens,
  tipo,
  rotuloEnviar,
  aoEnviar,
  aoCancelar,
  aoRemover,
  aoTentarNovamente,
  enviando = false,
  desabilitadoEnviar = false,
}: Props) {
  const Icone = tipo === "word" ? IconeWord : IconePlanilha;
  return (
    <div className="painel-arquivos">
      <h3>Arquivos enviados</h3>
      {itens.length === 0 ? (
        <p className="meta">Nenhum arquivo escolhido.</p>
      ) : (
        <ul className="lista-arquivos">
          {itens.map((it) => {
            const nome = it.arquivo.name;
            return (
              <li key={it.id} className={`arquivo ${it.estado}`}>
                <Icone className="arquivo-icone" />
                <div className="arquivo-corpo">
                  <div className="arquivo-linha">
                    <span className="arquivo-nome" title={nome}>{nome}</span>
                    <span className="arquivo-tamanho">{formatarTamanho(it.arquivo.size)}</span>
                  </div>
                  <div className="barra-linha">
                    <div
                      className="barra"
                      role="progressbar"
                      aria-label={`Progresso do envio de ${nome}`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(it.progresso)}
                    >
                      <div className="barra-preenchida" style={{ width: `${it.progresso}%` }} />
                    </div>
                    <span className="percentual">{Math.round(it.progresso)}%</span>
                  </div>
                  {it.estado === "erro" ? (
                    <p className="arquivo-estado erro" role="alert">{it.mensagem ?? ROTULO_ESTADO.erro}</p>
                  ) : (
                    <p className="arquivo-estado">{ROTULO_ESTADO[it.estado]}</p>
                  )}
                </div>
                <div className="arquivo-acoes">
                  {it.estado === "erro" && (
                    <button
                      type="button"
                      className="icone"
                      aria-label={`Tentar de novo: ${nome}`}
                      title="Tentar de novo"
                      disabled={enviando}
                      onClick={() => aoTentarNovamente(it.id)}
                    >
                      <IconeRepetir />
                    </button>
                  )}
                  <button
                    type="button"
                    className="icone perigo"
                    aria-label={`Remover ${nome}`}
                    title="Remover"
                    disabled={it.estado === "enviando"}
                    onClick={() => aoRemover(it.id)}
                  >
                    <IconeLixeira />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <div className="painel-rodape">
        <button type="button" className="secundario" onClick={aoCancelar}>Cancelar</button>
        <button type="button" disabled={desabilitadoEnviar || itens.length === 0} onClick={aoEnviar}>
          <IconeEnviar tamanho={16} /> {rotuloEnviar}
        </button>
      </div>
    </div>
  );
}
