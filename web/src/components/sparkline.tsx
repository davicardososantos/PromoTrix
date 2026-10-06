import type { Preco } from "@prisma/client";
import { quando, reais } from "@/lib/formato";

/**
 * A série de preços de uma oferta, do jeito "stat tile": o preço grande já está no cartão, aqui vem
 * só a forma da curva e quanto mudou. Uma leitura só não vira gráfico (devolve null).
 *
 * A linha fica na cor apagada e só o ponto de agora é escuro, porque o que importa é onde o preço
 * está hoje em relação ao caminho que fez. Queda é boa notícia num preço, então o sinal verde é o
 * negativo — o contrário do que seria num gráfico de vendas.
 */
export function Sparkline({ precos, largura = 168, altura = 40 }: { precos: Preco[]; largura?: number; altura?: number }) {
  if (precos.length < 2) return null;

  const valores = precos.map((p) => p.valor);
  const menor = Math.min(...valores);
  const maior = Math.max(...valores);
  const faixa = maior - menor || 1;
  const folga = 6; // o ponto de agora tem raio 4: sem folga ele encosta na borda do SVG
  const x = (i: number) => folga + (i / (valores.length - 1)) * (largura - 2 * folga);
  const y = (v: number) => altura - folga - ((v - menor) / faixa) * (altura - 2 * folga);
  const linha = valores.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");

  const primeiro = valores[0];
  const atual = valores[valores.length - 1];
  const variacao = atual - primeiro;
  const desde = quando(precos[0].em);

  return (
    <div className="serie">
      <svg
        className="spark"
        viewBox={`0 0 ${largura} ${altura}`}
        width={largura}
        height={altura}
        role="img"
        aria-label={`Preço de ${reais(primeiro)} em ${desde} para ${reais(atual)} agora. Menor: ${reais(menor)}.`}
      >
        <path d={linha} fill="none" stroke="var(--faint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={x(valores.length - 1)} cy={y(atual)} r="4" fill="var(--text)" />
      </svg>
      <span className="serie-nota">
        {variacao === 0 ? (
          <>no mesmo preço desde {desde}</>
        ) : (
          <>
            <b className={variacao < 0 ? "caiu" : "subiu"}>
              {variacao < 0 ? "↓" : "↑"} {reais(Math.abs(variacao))}
            </b>{" "}
            desde {desde}
          </>
        )}
        {menor < atual ? <> · menor visto {reais(menor)}</> : null}
      </span>
    </div>
  );
}
