import { brl, ROTULOS_CAMPO, type Relatorio } from "../tipos";

export function Indicadores({ r }: { r: Relatorio }) {
  return (
    <>
      <div className="cards">
        <div className="card"><span>Documentos</span><strong>{r.qtd_documentos}</strong></div>
        <div className="card"><span>Valor total dos documentos</span><strong>{brl(r.valor_total_documentos)}</strong></div>
        <div className="card"><span>Linhas na planilha</span><strong>{r.qtd_linhas_referencia}</strong></div>
        <div className={`card ${r.qtd_divergencias ? "alerta" : "ok"}`}><span>Divergências</span><strong>{r.qtd_divergencias}</strong><small>diferenças até {brl(r.tolerancia_centavos)} ignoradas</small></div>
      </div>
      {Object.keys(r.divergencias_por_campo).length > 0 && (
        <div className="cards">
          {Object.entries(r.divergencias_por_campo).map(([campo, qtd]) => (
            <div className="card pequeno" key={campo}>
              <span>{ROTULOS_CAMPO[campo] ?? campo}</span>
              <strong>{qtd}</strong>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
