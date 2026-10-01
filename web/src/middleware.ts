import NextAuth from "next-auth";
import { NextResponse } from "next/server";
import { authConfig } from "@/lib/auth.config";

const { auth } = NextAuth(authConfig);

// Tudo exige login, menos a tela de login, o Auth.js e a API do coletor (protegida por token).
export default auth((req) => {
  const { pathname } = req.nextUrl;
  const publico =
    pathname.startsWith("/login") || pathname.startsWith("/api/auth") || pathname.startsWith("/api/coletor");

  if (!req.auth && !publico) return NextResponse.redirect(new URL("/login", req.nextUrl));
  if (req.auth && pathname === "/login") return NextResponse.redirect(new URL("/", req.nextUrl));
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|manifest.webmanifest|sw.js|icons).*)"],
};
