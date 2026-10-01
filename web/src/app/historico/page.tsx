import { prisma } from "@/lib/db";
import { Topo } from "@/components/topo";
import { quando, reais } from "@/lib/formato";

export const dynamic = "force-dynamic";

/** Tudo o que já bateu em cada regra, com o menor preço visto: serve para calibrar os alvos. */
export default async function Historico() {
  const regras = await prisma.regra.findMany({
    orderBy: { ordem: "asc" },
    include: { promocoes: { orderBy: { primeiraVez: "desc" }, take: 30 } },
  });

  return (
    <>
      <Topo />
      <main className="pagina">
        <div className="cabeca">
          <div>
            <h1>Histórico</h1>
            <p>As últimas 30 ofertas de cada regra. A barra mostra o preço em relação à mais cara.</p>
          </div>
        </div>
        {regras.map((r) => {
          const precos = r.promocoes.map((p) => p.preco).filter((v): v is number => v != null);
          const menor = precos.length ? Math.min(...precos) : null;
          const maior = precos.length ? Math.max(...precos) : null;
          return (
            <section key={r.id} className="hist">
              <h2>{r.nome}</h2>
              <p className="resumo">
                {r.grupo}
                {r.promocoes.length
                  ? ` · ${r.promocoes.length} oferta(s) · menor ${reais(menor)} · alvo ${r.precoMax != null ? reais(r.precoMax) : "qualquer preço"}`
                  : " · nenhuma oferta ainda"}
                {r.precoReferencia != null ? ` · preço normal ${reais(r.precoReferencia)}` : ""}
              </p>
              {r.promocoes.map((p) => (
                <div key={p.id} className="linha">
                  <span className={`valor${p.preco != null && p.preco === menor ? " menor" : ""}`}>{reais(p.preco)}</span>
                  <div>
                    <a href={p.link} target="_blank" rel="noreferrer">
                      {p.titulo}
                    </a>
                    <div>
                      <small>
                        {p.loja} · {quando(p.primeiraVez)}
                        {p.desconto ? ` · -${Math.round(p.desconto)}%` : ""}
                        {p.cupom ? ` · cupom ${p.cupom}` : ""}
                      </small>
                    </div>
                    {p.preco != null && maior ? (
                      <div className="barra">
                        <span style={{ width: `${Math.max(4, (p.preco / maior) * 100)}%` }} />
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </section>
          );
        })}
      </main>
    </>
  );
}
