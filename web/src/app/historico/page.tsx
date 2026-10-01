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
      <main>
        <h1>Histórico</h1>
        <p className="suave">As últimas 30 promoções de cada regra que o PC encontrou.</p>
        {regras.map((r) => {
          const comPreco = r.promocoes.filter((p) => p.preco != null);
          const menor = comPreco.reduce<(typeof comPreco)[number] | null>(
            (m, p) => (m == null || p.preco! < m.preco! ? p : m),
            null,
          );
          return (
            <section key={r.id}>
              <h2>
                {r.grupo} · {r.nome}
              </h2>
              {r.promocoes.length === 0 ? (
                <p className="vazio">Nenhuma promoção ainda.</p>
              ) : (
                <>
                  {menor && (
                    <p className="suave">
                      Menor preço visto: <b>{reais(menor.preco)}</b> em {quando(menor.postadaEm ?? menor.primeiraVez)} (
                      {menor.loja}). Alvo atual: {r.precoMax != null ? reais(r.precoMax) : "qualquer preço"}.
                    </p>
                  )}
                  <table>
                    <thead>
                      <tr>
                        <th>Preço</th>
                        <th>Promoção</th>
                        <th>Loja</th>
                        <th>Visto em</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.promocoes.map((p) => (
                        <tr key={p.id}>
                          <td className="valor">{reais(p.preco)}</td>
                          <td>
                            <a href={p.link} target="_blank" rel="noreferrer">
                              {p.titulo}
                            </a>
                            {p.cupom && (
                              <>
                                {" "}
                                <span className="cupom">{p.cupom}</span>
                              </>
                            )}
                          </td>
                          <td>{p.loja}</td>
                          <td className="suave">{quando(p.primeiraVez)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </section>
          );
        })}
      </main>
    </>
  );
}
