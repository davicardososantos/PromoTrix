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
const siglas = z.array(z.string().regex(/^[A-Z]{3}$/)).min(1);
/** Trecho de passagem aérea: a regra deixa de olhar o Pelando e passa a ler o Google Flights. */
const vooSchema = z.object({
  origens: siglas,
  destinos: siglas,
  datas: z.array(z.string().regex(/^\d{4}-\d{2}-\d{2}$/)).min(1),
  max_paradas: z.number().int().min(0).max(3).optional(),
  intervalo_h: z.number().min(1).max(72).optional(),
});
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
      preco_referencia: z.number().optional(),
      desconto_min: z.number().optional(),
      voo: vooSchema.optional(),
      ate: z.string().optional(),
    }),
  ),
});

/**
 * Importa um config.json do coletor (`python promotrix.py --enviar-config`).
 * Só mexe no que já existe com ?substituir=1, para não apagar regras editadas no painel.
 * Regras e buscas casam pelo nome/termo: as que continuam são atualizadas no lugar (o histórico de
 * preços e o liga/desliga ficam), as novas são criadas e só as que saíram do arquivo são apagadas.
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
  const [regrasAtuais, buscasAtuais] = await Promise.all([prisma.regra.findMany(), prisma.busca.findMany()]);
  const regraPorNome = new Map(regrasAtuais.map((r) => [r.nome, r.id]));
  const buscaPorTermo = new Map(buscasAtuais.map((b) => [b.termo, b.id]));
  const nomes = new Set(regras.map((r) => r.nome));
  const termosNovos = new Set(buscas.map((b) => b.termo));

  await prisma.$transaction([
    prisma.regra.deleteMany({ where: { nome: { notIn: [...nomes] } } }),
    prisma.busca.deleteMany({ where: { termo: { notIn: [...termosNovos] } } }),
    ...buscas.map((b, i) => {
      const data = { termo: b.termo, ate: b.ate ?? null, ordem: i };
      const id = buscaPorTermo.get(b.termo);
      return id ? prisma.busca.update({ where: { id }, data }) : prisma.busca.create({ data });
    }),
    ...regras.map((r, i) => {
      const data = {
        grupo: r.grupo,
        nome: r.nome,
        prioridade: r.prioridade,
        precisa: JSON.stringify(r.precisa),
        qualquer: JSON.stringify(r.qualquer),
        naoPode: JSON.stringify(r.nao_pode),
        precoMin: r.preco_min ?? null,
        precoMax: r.preco_max ?? null,
        temperaturaMin: r.temperatura_min ?? null,
        precoReferencia: r.preco_referencia ?? null,
        descontoMin: r.desconto_min ?? null,
        voo: r.voo ? JSON.stringify(r.voo) : null,
        ate: r.ate ?? null,
        ordem: i,
      };
      const id = regraPorNome.get(r.nome);
      return id ? prisma.regra.update({ where: { id }, data }) : prisma.regra.create({ data });
    }),
  ]);
  const mantidas = regras.filter((r) => regraPorNome.has(r.nome)).length;
  return NextResponse.json({ ok: true, buscas: buscas.length, regras: regras.length, mantidas, novas: regras.length - mantidas });
}
