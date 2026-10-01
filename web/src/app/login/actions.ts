"use server";

import { AuthError } from "next-auth";
import { signIn } from "@/lib/auth";

export async function entrar(_anterior: string | undefined, dados: FormData): Promise<string | undefined> {
  try {
    await signIn("credentials", {
      email: dados.get("email"),
      password: dados.get("password"),
      redirectTo: "/",
    });
  } catch (erro) {
    if (erro instanceof AuthError) return "E-mail ou senha incorretos.";
    throw erro; // o redirect do signIn chega aqui como exceção e precisa seguir
  }
}
