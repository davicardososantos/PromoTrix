import { timingSafeEqual } from "crypto";
import { prisma } from "@/lib/db";
import { lista } from "@/lib/formato";

/** A API do coletor usa um segredo simples: Authorization: Bearer <COLETOR_TOKEN>. */
export function tokenValido(req: Request): boolean {
  const esperado = process.env.COLETOR_TOKEN;
  const veio = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!esperado || !veio || esperado.length !== veio.length) return false;
  return timingSafeEqual(Buffer.from(esperado), Buffer.from(veio));
}

/** Config no mesmo formato do coletor/config.json, para o coletor do PC não precisar mudar a lógica. */
export async function configParaColetor() {
  const [buscas, regras] = await Promise.all([
    prisma.busca.findMany({ where: { ativa: true }, orderBy: { ordem: "asc" } }),
    prisma.regra.findMany({ where: { ativa: true }, orderBy: { ordem: "asc" } }),
  ]);
  return {
    pausa_entre_buscas_s: 1.5,
    buscas: buscas.map((b) => ({ termo: b.termo, ...(b.ate ? { ate: b.ate } : {}) })),
    regras: regras.map((r) => ({
      id: r.id,
      grupo: r.grupo,
      nome: r.nome,
      prioridade: r.prioridade,
      precisa: lista(r.precisa),
      qualquer: lista(r.qualquer),
      nao_pode: lista(r.naoPode),
      ...(r.precoMin != null ? { preco_min: r.precoMin } : {}),
      ...(r.precoMax != null ? { preco_max: r.precoMax } : {}),
      ...(r.temperaturaMin != null ? { temperatura_min: r.temperaturaMin } : {}),
      ...(r.precoReferencia != null ? { preco_referencia: r.precoReferencia } : {}),
      ...(r.descontoMin != null ? { desconto_min: r.descontoMin } : {}),
      ...(r.ate ? { ate: r.ate } : {}),
    })),
  };
}
