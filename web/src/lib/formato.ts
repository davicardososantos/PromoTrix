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
