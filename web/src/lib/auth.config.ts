import type { NextAuthConfig } from "next-auth";

/**
 * Config base do Auth.js, SEM Prisma/bcrypt, para poder rodar no middleware (Edge runtime).
 * O provider Credentials (que consulta o banco) entra só em auth.ts. Mesmo padrão do Fintrix.
 */
export const authConfig = {
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: [],
  callbacks: {
    session: ({ session, token }) => {
      if (session.user && token.sub) session.user.id = token.sub;
      return session;
    },
  },
} satisfies NextAuthConfig;
