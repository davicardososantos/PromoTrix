import { prisma } from "@/lib/db";
import { Topo } from "@/components/topo";
import { AtivarPush } from "@/components/ativar-push";
import { haQuanto, quando, reais } from "@/lib/formato";

export const dynamic = "force-dynamic";

const UM_DIA = 24 * 60 * 60 * 1000;
const PC_PARADO = 2 * 60 * 60 * 1000;

/** Painel: o que a última coleta do PC encontrou dentro dos alvos, separado por grupo. */
export default async function Painel() {
  const [ultima, regras] = await Promise.all([
    prisma.coleta.findFirst({ orderBy: { em: "desc" } }),
    prisma.regra.findMany({ where: { ativa: true }, orderBy: { ordem: "asc" } }),
  ]);
  const promos = ultima
    ? await prisma.promocao.findMany({
        where: { ultimaColetaId: ultima.id },
        include: { regra: true },
        orderBy: { preco: "asc" },
      })
    : [];

  const grupos = [...new Set(regras.map((r) => r.grupo))];
  const semGrupo = promos.filter((p) => !p.regra);
  const parado = ultima && Date.now() - ultima.em.getTime() > PC_PARADO;

  return (
    <>
      <Topo />
      <main>
        {ultima ? (
          <div className={`faixa${parado ? " alerta" : ""}`}>
            Última coleta do PC: <b>{haQuanto(ultima.em)}</b> ({quando(ultima.em)}) · {ultima.lidas} promoções lidas,{" "}
            {ultima.dentro} dentro dos alvos.
            {parado && " O PC parece desligado: com ele desligado ninguém lê o Pelando."}
          </div>
        ) : (
          <div className="faixa alerta">Ainda não chegou nenhuma coleta. Ligue o coletor no PC (veja o README).</div>
        )}
        <AtivarPush />

        {grupos.map((g) => {
          const itens = promos.filter((p) => p.regra?.grupo === g);
          const regrasG = regras.filter((r) => r.grupo === g);
          return (
            <section key={g}>
              <h2>{g}</h2>
              <p className="suave">
                {regrasG.map((r) => `${r.nome}${r.precoMax != null ? ` até ${reais(r.precoMax)}` : ""}`).join(" · ")}
              </p>
              {itens.length ? (
                <div className="grade">
                  {itens.map((p) => (
                    <div className="cartao" key={p.id}>
                      {p.avisadaEm && Date.now() - p.avisadaEm.getTime() < UM_DIA && <span className="novo">novo</span>}
                      <span className="preco">{reais(p.preco)}</span>
                      <span className="titulo">{p.titulo}</span>
                      <span className="suave">
                        {p.loja} · {p.regra?.nome} · postada {quando(p.postadaEm)} · {Math.round(p.temperatura)}°
                      </span>
                      {p.cupom && (
                        <span className="suave">
                          Cupom <span className="cupom">{p.cupom}</span>
                        </span>
                      )}
                      <a className="botao" href={p.link} target="_blank" rel="noreferrer">
                        Ver no Pelando
                      </a>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="vazio">Nada ativo dentro do alvo agora.</p>
              )}
            </section>
          );
        })}
        {semGrupo.length > 0 && <p className="suave">{semGrupo.length} promoção(ões) de regras apagadas.</p>}
      </main>
    </>
  );
}
