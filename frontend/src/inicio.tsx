import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Aplicacao } from "./Aplicacao";
import "./estilos.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Aplicacao />
  </StrictMode>,
);
