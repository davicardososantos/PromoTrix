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
      imagem: z.string().url().nullable().optional(),
      desconto: z.number().nullable().optional(),
      desconto_origem: z.string().max(120).nullable().optional(),
    }),
  ),
  novos: z.array(z.string()).default([]),
  // Coletor antigo não manda cupons: os dois campos são opcionais.
  cupons: z
    .array(
      z.object({
        id: z.string().min(1),
        titulo: z.string(),
        loja: z.string(),
        link: z.string().url(),
        criada: z.string().nullable().optional(),
        temperatura: z.number().default(0),
        codigo: z.string().nullable().optional(),
        porcentagem: z.number().nullable().optional(),
        valor_fixo: z.number().nullable().optional(),
        minimo: z.number().nullable().optional(),
        limite: z.number().nullable().optional(),
        condicoes: z.array(z.string()).default([]),
        valor_txt: z.string().max(40),
        regras_txt: z.string().max(200).default(""),
        servem: z
          .array(
            z.object({
              regra_id: z.string().nullable().optional(),
              regra_nome: z.string(),
              prioridade: z.string().default("normal"),
              valor: z.number(),
              base: z.number(),
              base_tipo: z.string(),
            }),
          )
          .default([]),
      }),
    )
    .default([]),
  cupons_novos: z.array(z.string()).default([]),
});

/**
 * O coletor do PC manda aqui, a cada execução, as promoções ativas que bateram nas regras e quais
 * delas ele acabou de avisar. As novas de prioridade "alta" também vão para o celular (push).
 * Junto vêm os cupons de loja ativos; o cupom novo que serve num item de prioridade "alta" também
 * vai para o celular.
 */
export async function POST(req: Request) {
  if (!tokenValido(req)) return NextResponse.json({ erro: "token inválido" }, { status: 401 });
  const dados = coletaSchema.safeParse(await req.json().catch(() => null));
  if (!dados.success) return NextResponse.json({ erro: dados.error.flatten() }, { status: 400 });
  const { lidas, dentro, novos, cupons, cupons_novos } = dados.data;

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
      imagem: p.imagem ?? null,
      desconto: p.desconto ?? null,
      descontoOrigem: p.desconto_origem ?? null,
      ...(p.cupom ? { cupom: p.cupom } : {}),
      ...(novosSet.has(p.id) ? { avisadaEm: agora } : {}),
    };
    await prisma.promocao.upsert({
      where: { id: p.id },
      create: { id: p.id, postadaEm, primeiraVez: agora, ...comum },
      update: comum,
    });
    // Série de preços do painel. Só grava quando muda: uma passagem lida de 4 em 4 horas passa a
    // maior parte do tempo no mesmo valor, e um ponto por leitura só encheria o gráfico de repetição.
    if (p.preco != null) {
      const ultimo = await prisma.preco.findFirst({ where: { promocaoId: p.id }, orderBy: { em: "desc" } });
      if (ultimo?.valor !== p.preco) {
        await prisma.preco.create({ data: { promocaoId: p.id, valor: p.preco, em: agora } });
      }
    }
    if (novosSet.has(p.id) && regra?.prioridade === "alta") {
      pushes += await avisarCelulares({
        title: `${regra.nome}: ${reais(p.preco)}${p.desconto ? ` (-${Math.round(p.desconto)}%)` : ""}`,
        body: `${p.loja} · ${p.titulo}${p.cupom ? ` · cupom ${p.cupom}` : ""}`,
        url: p.link,
        tag: `promotrix-${p.id}`,
      });
    }
  }

  const cuponsNovos = new Set(cupons_novos);
  for (const c of cupons) {
    const novo = cuponsNovos.has(c.id);
    const comum = {
      titulo: c.titulo,
      loja: c.loja,
      link: c.link,
      porcentagem: c.porcentagem ?? null,
      valorFixo: c.valor_fixo ?? null,
      minimo: c.minimo ?? null,
      limite: c.limite ?? null,
      valorTxt: c.valor_txt,
      regrasTxt: c.regras_txt,
      condicoes: JSON.stringify(c.condicoes),
      servem: JSON.stringify(c.servem),
      temperatura: c.temperatura,
      ultimaVez: agora,
      ultimaColetaId: coleta.id,
      ...(c.codigo ? { codigo: c.codigo } : {}),
      ...(novo ? { avisadoEm: agora } : {}),
    };
    await prisma.cupom.upsert({
      where: { id: c.id },
      create: { id: c.id, postadoEm: c.criada ? new Date(c.criada) : null, primeiraVez: agora, ...comum },
      update: comum,
    });
    if (novo && c.servem.some((s) => s.prioridade === "alta")) {
      const nomes = c.servem.map((s) => s.regra_nome);
      pushes += await avisarCelulares({
        title: `Cupom ${c.loja}: ${c.valor_txt}`,
        body:
          `Pode servir em ${nomes.slice(0, 3).join(", ")}${nomes.length > 3 ? ` e mais ${nomes.length - 3}` : ""}` +
          ` · ${c.regras_txt}${c.codigo ? ` · cupom ${c.codigo}` : ""}`,
        url: c.link,
        tag: `promotrix-cupom-${c.id}`,
        silencioso: true,
      });
    }
  }
  return NextResponse.json({ ok: true, coleta: coleta.id, pushes });
}
