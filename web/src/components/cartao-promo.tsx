import type { Preco, Promocao, Regra } from "@prisma/client";
import { CopiarCupom } from "@/components/copiar-cupom";
import { Chama, Imagem, Seta } from "@/components/icones";
import { Sparkline } from "@/components/sparkline";
import { haQuanto, reais } from "@/lib/formato";

export type PromoComRegra = Promocao & { regra: Regra | null; precos?: Preco[] };

/** Cartão de uma promoção: foto, selos (desconto, novo, menor preço, votos), preço e ações. */
export function CartaoPromo({ p, novo, menorPreco }: { p: PromoComRegra; novo: boolean; menorPreco: boolean }) {
  const referencia = p.regra?.precoReferencia ?? null;
  const mostraAntigo = referencia != null && p.preco != null && p.preco < referencia && p.descontoOrigem?.startsWith("abaixo");
  const selos = (
    <div className="selos">
      {p.desconto ? (
        <span className="selo selo-off" title={p.descontoOrigem ?? undefined}>
          -{Math.round(p.desconto)}%
        </span>
      ) : null}
      {menorPreco && <span className="selo selo-menor">Menor preço</span>}
      {novo && <span className="selo selo-novo">Novo</span>}
    </div>
  );
  return (
    <article className="promo">
      {/* Passagem aérea não tem foto: sem a moldura da imagem, os selos sobem para o corpo do cartão. */}
      {p.imagem && (
        <div className="promo-foto">
          {/* O ícone fica embaixo da foto: se a foto não carregar, ele aparece no lugar do vazio. */}
          <Imagem tamanho={40} className="sem-foto" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={p.imagem} alt="" loading="lazy" referrerPolicy="no-referrer" />
          {selos}
          {p.temperatura >= 1 && (
            <span className="calor" title="Votos da comunidade no Pelando">
              <Chama tamanho={13} />
              {Math.round(p.temperatura)}°
            </span>
          )}
        </div>
      )}
      <div className="promo-corpo">
        {!p.imagem && selos}
        {p.regra && <span className="promo-regra">{p.regra.nome}</span>}
        <h3 className="promo-titulo" title={p.titulo}>
          {p.titulo}
        </h3>
        <div className="promo-precos">
          <span className="preco">{reais(p.preco)}</span>
          {mostraAntigo && <span className="preco-antigo">{reais(referencia)}</span>}
        </div>
        {/* O preço riscado já explica o desconto pelo preço normal; os outros casos (cupom, título, e
            o que o Google diz do trecho nas passagens) ganham a origem escrita. */}
        {p.descontoOrigem && !mostraAntigo ? <span className="origem">{p.descontoOrigem}</span> : null}
        {p.precos && <Sparkline precos={p.precos} />}
        <span className="promo-meta">
          {p.loja}
          {p.postadaEm ? ` · postada ${haQuanto(p.postadaEm)}` : ""}
        </span>
        <div className="promo-acoes">
          {p.cupom && <CopiarCupom codigo={p.cupom} />}
          <a className="btn btn-primario" href={p.link} target="_blank" rel="noreferrer">
            Ver oferta <Seta tamanho={15} />
          </a>
        </div>
      </div>
    </article>
  );
}
