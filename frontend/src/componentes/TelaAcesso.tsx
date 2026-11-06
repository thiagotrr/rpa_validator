import { useState, type FormEvent } from "react";
import { ErroApi, entrar } from "../servicoApi";

export function TelaAcesso({ aoEntrar }: { aoEntrar: () => void }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function submeter(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email, senha);
      aoEntrar();
    } catch (err) {
      setErro(err instanceof ErroApi && err.status === 429
          ? "Muitas tentativas. Aguarde e tente de novo."
          : err instanceof ErroApi && err.status === 503
            ? "Autenticação indisponível no momento."
            : "E-mail ou senha inválidos.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="cartao login" onSubmit={submeter}>
      <h1>Validador de RPAs</h1>
      <p className="meta">Acesso somente para e-mails autorizados.</p>
      <label>
        E-mail
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
      </label>
      <label>
        Senha
        <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required autoComplete="current-password" />
      </label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <button disabled={enviando}>{enviando ? "Entrando…" : "Entrar"}</button>
    </form>
  );
}
