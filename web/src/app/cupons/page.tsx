import Link from "next/link";
import { prisma } from "@/lib/db";
import { Topo } from "@/components/topo";
import { CartaoCupom } from "@/components/cartao-cupom";
import { Alerta } from "@/components/icones";
import { haQuanto, maiorDesconto } from "@/lib/formato";

export const dynamic = "force-dynamic";

const UM_DIA = 24 * 60 * 60 * 1000;

/**
 * Cupons de loja ativos no Pelando, da última coleta. Primeiro os que podem servir nos itens das
 * regras (maior desconto no item primeiro), depois os outros, dos mais votados para os menos.
 */
export default async function Cupons({ searchParams }: { searchParams: Promise<{ loja?: string }> }) {
  const { loja: filtro } = await searchParams;
  const ultima = await prisma.coleta.findFirst({ orderBy: { em: "desc" } });
  const todos = ultima
    ? await prisma.cupom.findMany({ where: { ultimaColetaId: ultima.id }, orderBy: { temperatura: "desc" } })
    : [];
  const lojas = [...new Set(todos.map((c) => c.loja))].sort();
  const visiveis = filtro && lojas.includes(filtro) ? todos.filter((c) => c.loja === filtro) : todos;
  const servem = visiveis
    .filter((c) => maiorDesconto(c.servem) > 0)
    .sort((a, b) => maiorDesconto(b.servem) - maiorDesconto(a.servem));
  const outros = visiveis.filter((c) => maiorDesconto(c.servem) === 0);
  const ehNovo = (d: Date | null) => !!d && Date.now() - d.getTime() < UM_DIA;

  return (
    <>
      <Topo />
      <main className="pagina">
        <div className="cabeca">
          <div>
            <h1>Cupons</h1>
            <p>Cupons de loja ativos no Pelando e no Promobit. Os que podem servir nos seus itens vêm primeiro.</p>
          </div>
          {ultima && (
            <span className="status" title="Última coleta do PC">
              <span className="ponto" />
              Coletado <b>{haQuanto(ultima.em)}</b> · <b>{todos.length}</b> cupons
            </span>
          )}
        </div>

        <div className="aviso">
          <Alerta /> O desconto de cada item é calculado no preço normal dele (ou no alvo da regra). Confira no
          carrinho: muitos cupons valem só para itens selecionados.
        </div>

        <nav className="filtros" aria-label="Filtrar por loja">
          <Link href="/cupons" className={`filtro${!filtro ? " ativo" : ""}`}>
            Todas<span className="n">{todos.length}</span>
          </Link>
          {lojas.map((l) => (
            <Link key={l} href={`/cupons?loja=${encodeURIComponent(l)}`} className={`filtro${filtro === l ? " ativo" : ""}`}>
              {l}
              <span className="n">{todos.filter((c) => c.loja === l).length}</span>
            </Link>
          ))}
        </nav>

        <section className="secao">
          <div className="secao-cabeca">
            <h2>Servem nos seus itens</h2>
            <span className="contagem">{servem.length}</span>
          </div>
          {servem.length ? (
            <div className="grade grade-cupons">
              {servem.map((c) => (
                <CartaoCupom key={c.id} c={c} novo={ehNovo(c.avisadoEm)} />
              ))}
            </div>
          ) : (
            <p className="vazio">Nenhum cupom ativo serve nos itens das suas regras agora.</p>
          )}
        </section>

        <section className="secao">
          <div className="secao-cabeca">
            <h2>Outros cupons, os mais votados</h2>
            <span className="contagem">{outros.length}</span>
          </div>
          {outros.length ? (
            <div className="grade grade-cupons">
              {outros.map((c) => (
                <CartaoCupom key={c.id} c={c} novo={false} />
              ))}
            </div>
          ) : (
            <p className="vazio">
              {todos.length ? "Nada além dos de cima." : "Ainda não chegou nenhum cupom. O PC confere a cada 15 minutos."}
            </p>
          )}
        </section>
      </main>
    </>
  );
}
