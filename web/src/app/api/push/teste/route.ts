import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { avisarCelulares } from "@/lib/push";

/** Manda uma notificação de teste para os aparelhos do usuário logado. */
export async function POST() {
  const sessao = await auth();
  if (!sessao?.user?.id) return NextResponse.json({ erro: "não autorizado" }, { status: 401 });
  const entregues = await avisarCelulares(
    { title: "PromoTrix: teste", body: "Se chegou, as promoções importantes vão chegar aqui também.", url: "/" },
    sessao.user.id,
  );
  return NextResponse.json({ ok: true, entregues });
}
