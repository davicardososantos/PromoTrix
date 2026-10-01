import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

/** Registra (ou atualiza) a inscrição de push do aparelho atual para o usuário logado. */
export async function POST(req: Request) {
  const sessao = await auth();
  if (!sessao?.user?.id) return NextResponse.json({ erro: "não autorizado" }, { status: 401 });

  const corpo = await req.json().catch(() => null);
  const endpoint: string | undefined = corpo?.endpoint;
  const p256dh: string | undefined = corpo?.keys?.p256dh;
  const chave: string | undefined = corpo?.keys?.auth;
  if (!endpoint || !p256dh || !chave) return NextResponse.json({ erro: "inválido" }, { status: 400 });

  await prisma.pushSubscription.upsert({
    where: { endpoint },
    create: { userId: sessao.user.id, endpoint, p256dh, auth: chave },
    update: { userId: sessao.user.id, p256dh, auth: chave },
  });
  return NextResponse.json({ ok: true });
}
