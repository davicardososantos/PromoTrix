"use client";

import { useActionState } from "react";
import { entrar } from "./actions";

export default function Login() {
  const [erro, acao, enviando] = useActionState(entrar, undefined);
  return (
    <main>
      <form action={acao} className="login">
        <h1>PromoTrix</h1>
        <label>
          E-mail
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <label>
          Senha
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {erro && <p className="erro">{erro}</p>}
        <button className="botao" type="submit" disabled={enviando}>
          {enviando ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </main>
  );
}
