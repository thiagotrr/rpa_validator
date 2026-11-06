import type { ReactNode } from "react";

type Props = { tamanho?: number; className?: string };

function Svg({ tamanho = 20, className, icone, children }: Props & { icone: string; children: ReactNode }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={tamanho}
      height={tamanho}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      data-icone={icone}
      className={className}
    >
      {children}
    </svg>
  );
}

export const IconePlanilhaMenu = (p: Props) => (
  <Svg {...p} icone="menu-planilha">
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 10h18M3 15h18M9 4v16" />
  </Svg>
);

export const IconeRpasMenu = (p: Props) => (
  <Svg {...p} icone="menu-rpas">
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h6" />
  </Svg>
);

export const IconeRelatorio = (p: Props) => (
  <Svg {...p} icone="menu-relatorio">
    <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" />
  </Svg>
);

export const IconeSair = (p: Props) => (
  <Svg {...p} icone="sair">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
  </Svg>
);

export const IconeEnviar = (p: Props) => (
  <Svg {...p} icone="enviar">
    <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />
  </Svg>
);

export const IconeLixeira = (p: Props) => (
  <Svg {...p} icone="lixeira">
    <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6" />
  </Svg>
);

export const IconeRepetir = (p: Props) => (
  <Svg {...p} icone="repetir">
    <path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5" />
  </Svg>
);

/** Documento do Word (.doc/.docx): folha com o "W" em destaque. */
export const IconeWord = ({ tamanho = 32, className }: Props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    width={tamanho}
    height={tamanho}
    aria-hidden="true"
    focusable="false"
    data-icone="word"
    className={className}
  >
    <path d="M8 2h12l6 6v20a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#ffffff" stroke="#2b579a" strokeWidth="1.6" />
    <path d="M20 2v6h6" fill="#dbe6f7" stroke="#2b579a" strokeWidth="1.6" strokeLinejoin="round" />
    <rect x="2" y="12" width="16" height="12" rx="2" fill="#2b579a" />
    <path d="M5 15l1.7 6 1.8-5 1.8 5 1.7-6" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/** Planilha (.xlsx): folha com o "X" em destaque. */
export const IconePlanilha = ({ tamanho = 32, className }: Props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    width={tamanho}
    height={tamanho}
    aria-hidden="true"
    focusable="false"
    data-icone="planilha"
    className={className}
  >
    <path d="M8 2h12l6 6v20a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#ffffff" stroke="#217346" strokeWidth="1.6" />
    <path d="M20 2v6h6" fill="#d6ecdf" stroke="#217346" strokeWidth="1.6" strokeLinejoin="round" />
    <rect x="2" y="12" width="16" height="12" rx="2" fill="#217346" />
    <path d="M6 15.5l6 7M12 15.5l-6 7" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
    <path d="M20 16h4M20 20h4" stroke="#217346" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
);
