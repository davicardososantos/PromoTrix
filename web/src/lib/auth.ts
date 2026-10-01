import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { authConfig } from "@/lib/auth.config";

const credenciais = z.object({ email: z.string().email(), password: z.string().min(1) });

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
    Credentials({
      credentials: {
        email: { label: "E-mail", type: "email" },
        password: { label: "Senha", type: "password" },
      },
      authorize: async (bruto) => {
        const dados = credenciais.safeParse(bruto);
        if (!dados.success) return null;
        const user = await prisma.user.findUnique({ where: { email: dados.data.email.toLowerCase() } });
        if (!user || !(await bcrypt.compare(dados.data.password, user.passwordHash))) return null;
        return { id: user.id, name: user.nome, email: user.email };
      },
    }),
  ],
});
