import Link from "next/link";
import { prisma } from "@/lib/db";
import { Topo } from "@/components/topo";
import { AtivarPush } from "@/components/ativar-push";
import { CartaoPromo, type PromoComRegra } from "@/components/cartao-promo";
import { Alerta } from "@/components/icones";
import { haQuanto, quando, reais } from "@/lib/formato";

export const dynamic = "force-dynamic";

const UM_DIA = 24 * 60 * 60 * 1000;
const PC_PARADO = 2 * 60 * 60 * 1000;
// "Menor preço já visto" só vale com algum histórico e em regra de um produto só (a que tem preço normal):
// numa regra como "LEGO até R$ 100", o mais barato é só o LEGO mais barato, não uma baixa de preço.
const MINIMO_HISTORICO = 3;

/** Pontua uma oferta para a faixa "Grandes oportunidades": desconto, votos e menor preço já visto. */
function pontos(p: PromoComRegra, menor: boolean) {
  return (p.desconto ?? 0) + Math.min(p.temperatura, 1000) / 20 + (menor ? 15 : 0);
}

export default async function Painel({ searchParams }: { searchParams: Promise<{ grupo?: string }> }) {
  const { grupo: filtro } = await searchParams;
  const [ultima, regras] = await Promise.all([
    prisma.coleta.findFirst({ orderBy: { em: "desc" } }),
    prisma.regra.findMany({ where: { ativa: true }, orderBy: { ordem: "asc" } }),
  ]);
  const promos: PromoComRegra[] = ultima
    ? await prisma.promocao.findMany({
        where: { ultimaColetaId: ultima.id },
        include: { regra: true },
        orderBy: { preco: "asc" },
      })
    : [];

  // Menor preço já visto em cada regra (o histórico inteiro, não só a última coleta).
  const historico = await prisma.promocao.groupBy({
    by: ["regraId"],
    where: { regraId: { not: null }, preco: { not: null } },
    _min: { preco: true },
    _count: { _all: true },
  });
  const menorPorRegra = new Map(historico.map((h) => [h.regraId, h]));
  const ehMenor = (p: PromoComRegra) => {
    const h = p.regraId ? menorPorRegra.get(p.regraId) : undefined;
    return !!h && p.regra?.precoReferencia != null && h._count._all >= MINIMO_HISTORICO && p.preco != null && p.preco <= (h._min.preco ?? Infinity);
  };
  const ehNovo = (p: PromoComRegra) => !!p.avisadaEm && Date.now() - p.avisadaEm.getTime() < UM_DIA;

  const destaques = promos
    .filter((p) => (p.desconto ?? 0) >= 15 || p.temperatura >= 300 || ehMenor(p))
    .sort((a, b) => pontos(b, ehMenor(b)) - pontos(a, ehMenor(a)))
    .slice(0, 6);

  const grupos = [...new Set(regras.map((r) => r.grupo))];
  const contar = (g: string) => promos.filter((p) => p.regra?.grupo === g).length;
  const visiveis = filtro && grupos.includes(filtro) ? [filtro] : grupos;
  const parado = ultima && Date.now() - ultima.em.getTime() > PC_PARADO;

  return (
    <>
      <Topo />
      <main className="pagina">
        <div className="cabeca">
          <div>
            <h1>Promoções</h1>
            <p>O que o seu PC encontrou no Pelando dentro dos seus alvos.</p>
          </div>
          {ultima && (
            <span className={`status${parado ? " parado" : ""}`} title={quando(ultima.em)}>
              <span className="ponto" />
              Coletado <b>{haQuanto(ultima.em)}</b> · {ultima.lidas} lidas · <b>{promos.length}</b> no alvo
            </span>
          )}
        </div>

        {!ultima && (
          <div className="aviso">
            <Alerta /> Ainda não chegou nenhuma coleta. Ligue o coletor no PC (veja o README).
          </div>
        )}
        {parado && (
          <div className="aviso">
            <Alerta /> A última coleta foi {haQuanto(ultima!.em)}. Com o PC desligado ninguém lê o Pelando.
          </div>
        )}

        <AtivarPush />

        {destaques.length > 0 && !filtro && (
          <section className="destaques">
            <div className="destaques-cabeca">
              <h2>Grandes oportunidades</h2>
              <p>Maior desconto, mais votos no Pelando ou o menor preço que já apareceu.</p>
            </div>
            <div className="grade">
              {destaques.map((p) => (
                <CartaoPromo key={p.id} p={p} novo={ehNovo(p)} menorPreco={ehMenor(p)} />
              ))}
            </div>
          </section>
        )}

        <nav className="filtros" aria-label="Filtrar por grupo">
          <Link href="/" className={`filtro${!filtro ? " ativo" : ""}`}>
            Todos<span className="n">{promos.length}</span>
          </Link>
          {grupos.map((g) => (
            <Link key={g} href={`/?grupo=${encodeURIComponent(g)}`} className={`filtro${filtro === g ? " ativo" : ""}`}>
              {g}
              <span className="n">{contar(g)}</span>
            </Link>
          ))}
        </nav>

        {visiveis.map((g) => {
          const itens = promos.filter((p) => p.regra?.grupo === g);
          const regrasG = regras.filter((r) => r.grupo === g);
          return (
            <section key={g} className="secao">
              <div className="secao-cabeca">
                <h2>{g}</h2>
                <span className="contagem">{itens.length}</span>
              </div>
              <div className="alvos">
                {regrasG.map((r) => (
                  <span key={r.id} className="alvo">
                    <b>{r.nome}</b>
                    {r.precoMax != null ? ` até ${reais(r.precoMax)}` : ""}
                  </span>
                ))}
              </div>
              {itens.length ? (
                <div className="grade">
                  {itens.map((p) => (
                    <CartaoPromo key={p.id} p={p} novo={ehNovo(p)} menorPreco={ehMenor(p)} />
                  ))}
                </div>
              ) : (
                <p className="vazio">Nada dentro do alvo agora. O PC confere de novo a cada 30 minutos.</p>
              )}
            </section>
          );
        })}
      </main>
    </>
  );
}
