import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { configParaColetor, tokenValido } from "@/lib/coletor";

/** O coletor do PC busca aqui as buscas e regras ativas (mesmo formato do coletor/config.json). */
export async function GET(req: Request) {
  if (!tokenValido(req)) return NextResponse.json({ erro: "token inválido" }, { status: 401 });
  return NextResponse.json(await configParaColetor());
}

const termos = z.array(z.string()).default([]);
const configSchema = z.object({
  buscas: z.array(z.object({ termo: z.string().min(1), ate: z.string().optional() })),
  regras: z.array(
    z.object({
      grupo: z.string().min(1),
      nome: z.string().min(1),
      prioridade: z.enum(["alta", "normal"]).default("normal"),
      precisa: termos,
      qualquer: termos,
      nao_pode: termos,
      preco_min: z.number().optional(),
      preco_max: z.number().optional(),
      temperatura_min: z.number().optional(),
      ate: z.string().optional(),
    }),
  ),
});

/**
 * Importa um config.json do coletor (`python promotrix.py --enviar-config`).
 * Só substitui o que já existe com ?substituir=1, para não apagar regras editadas no painel.
 */
export async function PUT(req: Request) {
  if (!tokenValido(req)) return NextResponse.json({ erro: "token inválido" }, { status: 401 });
  const dados = configSchema.safeParse(await req.json().catch(() => null));
  if (!dados.success) return NextResponse.json({ erro: dados.error.flatten() }, { status: 400 });

  const substituir = new URL(req.url).searchParams.get("substituir") === "1";
  if (!substituir && (await prisma.regra.count()) > 0) {
    return NextResponse.json({ erro: "já existem regras; use ?substituir=1" }, { status: 409 });
  }

  const { buscas, regras } = dados.data;
  await prisma.$transaction([
    prisma.busca.deleteMany(),
    prisma.regra.deleteMany(),
    ...buscas.map((b, i) => prisma.busca.create({ data: { termo: b.termo, ate: b.ate ?? null, ordem: i } })),
    ...regras.map((r, i) =>
      prisma.regra.create({
        data: {
          grupo: r.grupo,
          nome: r.nome,
          prioridade: r.prioridade,
          precisa: JSON.stringify(r.precisa),
          qualquer: JSON.stringify(r.qualquer),
          naoPode: JSON.stringify(r.nao_pode),
          precoMin: r.preco_min ?? null,
          precoMax: r.preco_max ?? null,
          temperaturaMin: r.temperatura_min ?? null,
          ate: r.ate ?? null,
          ordem: i,
        },
      }),
    ),
  ]);
  return NextResponse.json({ ok: true, buscas: buscas.length, regras: regras.length });
}
