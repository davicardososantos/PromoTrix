import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { tokenValido } from "@/lib/coletor";
import { avisarCelulares } from "@/lib/push";
import { reais } from "@/lib/formato";

const coletaSchema = z.object({
  lidas: z.number().int().nonnegative(),
  dentro: z.array(
    z.object({
      id: z.string().min(1),
      titulo: z.string(),
      preco: z.number().nullable(),
      loja: z.string(),
      temperatura: z.number().default(0),
      criada: z.string().nullable().optional(),
      link: z.string().url(),
      regra_id: z.string().nullable().optional(),
      regra_nome: z.string(),
      cupom: z.string().nullable().optional(),
    }),
  ),
  novos: z.array(z.string()).default([]),
});

/**
 * O coletor do PC manda aqui, a cada execução, as promoções ativas que bateram nas regras e quais
 * delas ele acabou de avisar. As novas de prioridade "alta" também vão para o celular (push).
 */
export async function POST(req: Request) {
  if (!tokenValido(req)) return NextResponse.json({ erro: "token inválido" }, { status: 401 });
  const dados = coletaSchema.safeParse(await req.json().catch(() => null));
  if (!dados.success) return NextResponse.json({ erro: dados.error.flatten() }, { status: 400 });
  const { lidas, dentro, novos } = dados.data;

  const coleta = await prisma.coleta.create({ data: { lidas, dentro: dentro.length, novos: novos.length } });
  const regras = await prisma.regra.findMany();
  const porId = new Map(regras.map((r) => [r.id, r]));
  const porNome = new Map(regras.map((r) => [r.nome, r]));
  const agora = new Date();
  const novosSet = new Set(novos);
  let pushes = 0;

  for (const p of dentro) {
    const regra = (p.regra_id && porId.get(p.regra_id)) || porNome.get(p.regra_nome) || null;
    const postadaEm = p.criada ? new Date(p.criada) : null;
    const comum = {
      titulo: p.titulo,
      preco: p.preco,
      loja: p.loja,
      temperatura: p.temperatura,
      link: p.link,
      regraId: regra?.id ?? null,
      ultimaVez: agora,
      ultimaColetaId: coleta.id,
      ...(p.cupom ? { cupom: p.cupom } : {}),
      ...(novosSet.has(p.id) ? { avisadaEm: agora } : {}),
    };
    await prisma.promocao.upsert({
      where: { id: p.id },
      create: { id: p.id, postadaEm, primeiraVez: agora, ...comum },
      update: comum,
    });
    if (novosSet.has(p.id) && regra?.prioridade === "alta") {
      pushes += await avisarCelulares({
        title: `${regra.nome}: ${reais(p.preco)}`,
        body: `${p.loja} · ${p.titulo}${p.cupom ? ` · cupom ${p.cupom}` : ""}`,
        url: p.link,
        tag: `promotrix-${p.id}`,
      });
    }
  }
  return NextResponse.json({ ok: true, coleta: coleta.id, pushes });
}
