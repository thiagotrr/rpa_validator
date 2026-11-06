import { useEffect, useState } from "react";
import { MESES, partesDaCompetencia } from "../competencia";

type Props = { valor: string; aoMudar: (competencia: string) => void; rotulo?: string };

/** Mês (lista) + ano (campo numérico): funciona em qualquer navegador, sem depender de <input type="month">. */
export function SeletorCompetencia({ valor, aoMudar, rotulo = "Competência" }: Props) {
  const { ano, mes } = partesDaCompetencia(valor);
  const [anoTexto, setAnoTexto] = useState(ano);
  useEffect(() => setAnoTexto(ano), [ano]);

  function mudarAno(texto: string) {
    setAnoTexto(texto);
    if (/^\d{4}$/.test(texto)) aoMudar(`${texto}-${mes}`);
  }

  return (
    <fieldset className="competencia">
      <legend>{rotulo}</legend>
      <select aria-label="Mês" value={mes} onChange={(e) => aoMudar(`${ano}-${e.target.value}`)}>
        {MESES.map((nome, i) => {
          const numero = String(i + 1).padStart(2, "0");
          return <option key={numero} value={numero}>{nome}</option>;
        })}
      </select>
      <input
        aria-label="Ano"
        type="number"
        inputMode="numeric"
        min={2000}
        max={2100}
        value={anoTexto}
        onChange={(e) => mudarAno(e.target.value)}
      />
    </fieldset>
  );
}
