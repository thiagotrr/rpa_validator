import { useState, type DragEvent } from "react";

type Props = {
  rotulo: string; // nome acessível do botão de escolha
  aceita: string[]; // extensões, ex.: [".xlsx"]
  multiplo: boolean;
  aoEscolher: (arquivos: File[]) => void;
  desabilitado?: boolean;
};

const extensao = (nome: string) => nome.slice(nome.lastIndexOf(".")).toLowerCase();

/** Arrastar e soltar OU botão de escolha. No modo único, mais de um arquivo é recusado (nada é enviado). */
export function AreaArquivos({ rotulo, aceita, multiplo, aoEscolher, desabilitado = false }: Props) {
  const [sobre, setSobre] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  function receber(lista: FileList | File[] | null | undefined) {
    const arquivos = Array.from(lista ?? []);
    setAviso(null);
    if (arquivos.length === 0) return;
    if (!multiplo && arquivos.length > 1) {
      setAviso("Envie um único arquivo por vez.");
      return;
    }
    const validos = arquivos.filter((a) => aceita.includes(extensao(a.name)));
    if (validos.length === 0) {
      setAviso(`Formato não aceito. Use ${aceita.join(" ou ")}.`);
      return;
    }
    if (validos.length < arquivos.length) {
      setAviso(`${arquivos.length - validos.length} arquivo(s) ignorado(s): formato não aceito.`);
    }
    aoEscolher(validos);
  }

  function soltar(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setSobre(false);
    if (!desabilitado) receber(e.dataTransfer.files);
  }

  return (
    <div
      className={`area-arquivos${sobre ? " sobre" : ""}`}
      data-testid="area-arquivos"
      onDragOver={(e) => {
        e.preventDefault();
        if (!desabilitado) setSobre(true);
      }}
      onDragLeave={() => setSobre(false)}
      onDrop={soltar}
    >
      <p>Arraste {multiplo ? "os arquivos" : "o arquivo"} para cá ou</p>
      <input
        type="file"
        aria-label={rotulo}
        accept={aceita.join(",")}
        multiple={multiplo}
        disabled={desabilitado}
        onChange={(e) => {
          receber(e.target.files);
          e.target.value = ""; // permite escolher o mesmo arquivo de novo
        }}
      />
      {aviso && <p className="erro" role="alert">{aviso}</p>}
    </div>
  );
}
