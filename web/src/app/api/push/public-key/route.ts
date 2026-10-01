import { NextResponse } from "next/server";

/** Chave pública VAPID em runtime (evita fixar NEXT_PUBLIC_* no build do Docker). */
export async function GET() {
  return NextResponse.json({ key: process.env.VAPID_PUBLIC_KEY ?? "" });
}
