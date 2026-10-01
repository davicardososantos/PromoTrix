"use client";

import { useActionState } from "react";
import { Etiqueta } from "@/components/icones";
import { entrar } from "./actions";

export default function Login() {
  const [erro, acao, enviando] = useActionState(entrar, undefined);
  return (
    <main className="login-fundo">
      <form action={acao} className="login">
        <span className="marca-icone" style={{ width: 44, height: 44, borderRadius: 13 }}>
          <Etiqueta tamanho={22} />
        </span>
        <div>
          <h1>PromoTrix</h1>
          <p>As promoções que importam, dentro dos seus alvos.</p>
        </div>
        <label>
          E-mail
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <label>
          Senha
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {erro && <p className="erro">{erro}</p>}
        <button className="btn btn-primario" type="submit" disabled={enviando}>
          {enviando ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </main>
  );
}
