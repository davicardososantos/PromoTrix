import type { Cupom } from "@prisma/client";
import { CopiarCupom } from "@/components/copiar-cupom";
import { Chama, Seta } from "@/components/icones";
import { fonte, haQuanto, lista, reais, servidos } from "@/lib/formato";

const MAX_ITENS = 4;

/** Cartão de um cupom de loja: valor, compra mínima e limite, condições e os itens em que pode servir. */
export function CartaoCupom({ c, novo }: { c: Cupom; novo: boolean }) {
  const itens = servidos(c.servem);
  const condicoes = lista(c.condicoes);
  return (
    <article className={`cupom${itens.length ? " serve" : ""}`}>
      <div className="cupom-topo">
        <span className="cupom-loja">{c.loja}</span>
        {novo && <span className="selo selo-novo">Novo</span>}
        {c.temperatura >= 1 && (
          <span className="cupom-calor" title="Votos da comunidade no Pelando">
            <Chama tamanho={12} />
            {Math.round(c.temperatura)}°
          </span>
        )}
      </div>
      <span className="cupom-valor">{c.valorTxt}</span>
      {c.regrasTxt && <span className="cupom-regras">{c.regrasTxt}</span>}
      {condicoes.length > 0 && (
        <div className="cupom-condicoes">
          {condicoes.map((x) => (
            <span key={x} className="etiqueta">
              {x}
            </span>
          ))}
        </div>
      )}
      <h3 className="cupom-titulo" title={c.titulo}>
        {c.titulo}
      </h3>
      {itens.length > 0 && (
        <div className="cupom-itens">
          <span className="cupom-rotulo">Pode servir em</span>
          <ul>
            {itens.slice(0, MAX_ITENS).map((s) => (
              <li key={s.regra_nome} title={`Desconto calculado no ${s.base_tipo} do item: ${reais(s.base)}`}>
                <span>{s.regra_nome}</span>
                <b>-{reais(s.valor)}</b>
              </li>
            ))}
            {itens.length > MAX_ITENS && <li className="mais">e mais {itens.length - MAX_ITENS}</li>}
          </ul>
        </div>
      )}
      <span className="promo-meta">
        Via {fonte(c.link)}
        {c.postadoEm ? ` · postado ${haQuanto(c.postadoEm)}` : ""}
      </span>
      <div className="promo-acoes">
        {c.codigo && <CopiarCupom codigo={c.codigo} />}
        <a className="btn btn-primario" href={c.link} target="_blank" rel="noreferrer">
          Ver cupom <Seta tamanho={15} />
        </a>
      </div>
    </article>
  );
}
