const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const dataHora = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "America/Sao_Paulo",
});

export const reais = (v: number | null | undefined) => (v == null ? "sem preço" : moeda.format(v));
export const quando = (d: Date | null | undefined) => (d ? dataHora.format(d) : "—");

/** "há 5 min", "há 3 h", "há 2 dias". */
export function haQuanto(d: Date): string {
  const min = Math.round((Date.now() - d.getTime()) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `há ${h} h`;
  return `há ${Math.round(h / 24)} dias`;
}

export const lista = (json: string): string[] => {
  try {
    const v = JSON.parse(json);
    return Array.isArray(v) ? v.map(String) : [];
  } catch {
    return [];
  }
};

/** Trecho de passagem aérea guardado como JSON em Regra.voo (ver coletor/voos.py). */
export type Voo = {
  origens: string[];
  destinos: string[];
  datas: string[];
  max_paradas?: number;
  intervalo_h?: number;
};

export function voo(json: string | null): Voo | null {
  if (!json) return null;
  try {
    const v = JSON.parse(json) as Voo;
    return v?.origens?.length && v?.destinos?.length && v?.datas?.length ? v : null;
  } catch {
    return null;
  }
}

/** Item em que um cupom pode servir (Cupom.servem, montado pelo coletor). `valor` é o desconto no
 *  preço normal do item (base_tipo "preço normal") ou no alvo da regra (base_tipo "alvo"). */
export type Servido = {
  regra_id?: string | null;
  regra_nome: string;
  prioridade: string;
  valor: number;
  base: number;
  base_tipo: string;
};

export function servidos(json: string): Servido[] {
  try {
    const v = JSON.parse(json);
    return Array.isArray(v) ? (v as Servido[]) : [];
  } catch {
    return [];
  }
}

/** De que site veio a oferta ou o cupom (o coletor lê o Pelando e o Promobit). */
export const fonte = (link: string) => (link.includes("promobit.com.br") ? "Promobit" : "Pelando");

/** Maior desconto que o cupom dá num item monitorado (0 se não serve em nenhum). */
export const maiorDesconto = (json: string) => Math.max(0, ...servidos(json).map((s) => s.valor));
