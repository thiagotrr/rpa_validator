import { exportarRelatorio } from "../servicoApi";
import { ROTULOS_CAMPO, ROTULOS_TIPO, type Relatorio } from "../tipos";
import { Indicadores } from "./Indicadores";

export function TelaRelatorio({ r }: { r: Relatorio }) {
  return (
    <section className="cartao">
      <div className="titulo">
        <h2>Relatório — {r.competencia}</h2>
        <div>
          <button onClick={() => exportarRelatorio(r.competencia, "pdf")}>Exportar PDF</button>
          <button onClick={() => exportarRelatorio(r.competencia, "md")}>Exportar Markdown</button>
        </div>
      </div>
      <Indicadores r={r} />
      {r.divergencias.length === 0 ? (
        <p>Nenhuma divergência encontrada.</p>
      ) : (
        <table>
          <thead>
            <tr><th>RPA</th><th>Empresa</th><th>Nome</th><th>Campo</th><th>Tipo</th><th>Planilha</th><th>Documento</th></tr>
          </thead>
          <tbody>
            {r.divergencias.map((d) => (
              <tr key={`${d.numero_rpa}-${d.campo}`}>
                <td>{d.numero_rpa}</td><td>{d.codigo_empresa}</td><td>{d.nome}</td>
                <td>{ROTULOS_CAMPO[d.campo] ?? d.campo}</td><td>{ROTULOS_TIPO[d.tipo] ?? d.tipo}</td>
                <td>{d.valor_planilha}</td><td>{d.valor_documento}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="meta">Gerado em {new Date(r.gerado_em).toLocaleString("pt-BR")}</p>
    </section>
  );
}
