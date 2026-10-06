import type { Regra } from "@prisma/client";
import { prisma } from "@/lib/db";
import { Topo } from "@/components/topo";
import { lista, reais, voo } from "@/lib/formato";
import { alternarBusca, alternarRegra, apagarBusca, apagarRegra, salvarBusca, salvarRegra } from "./actions";

export const dynamic = "force-dynamic";

const dataBr = (iso: string) => iso.split("-").reverse().join("/");

function resumo(r: Regra) {
  const partes = [r.precoMax != null ? `até ${reais(r.precoMax)}` : "qualquer preço"];
  const trecho = voo(r.voo);
  if (trecho) {
    partes.unshift(
      `${trecho.origens.join("+")} → ${trecho.destinos.join(", ")} em ${trecho.datas.map(dataBr).join(" ou ")}`,
    );
  }
  if (r.precoReferencia != null) partes.push(`normal ${reais(r.precoReferencia)}`);
  if (r.descontoMin != null) partes.push(`${r.descontoMin}%+ de desconto`);
  if (r.temperaturaMin != null) partes.push(`${r.temperaturaMin}°+ no Pelando`);
  if (r.ate) partes.push(`vale até ${dataBr(r.ate)}`);
  if (!r.ativa) partes.push("desligada");
  return partes.join(" · ");
}

/**
 * Preenchido, a regra para de olhar o Pelando: o PC passa a ler o preço deste trecho no Google
 * Flights e guarda o voo mais barato de cada destino em cada data. Os campos de termo e de votos
 * acima não valem para passagem; o preço máximo e o preço normal valem.
 */
function FormVoo({ r }: { r?: Regra }) {
  const v = r ? voo(r.voo) : null;
  return (
    <fieldset className="voo">
      <legend>Passagem aérea (opcional)</legend>
      <p className="resumo-alvo">
        Com os três primeiros campos preenchidos, esta regra acompanha o preço do trecho no Google
        Flights em vez de procurar no Pelando. Vários aeroportos de saída custam uma consulta só.
      </p>
      <div className="campos">
        <label>
          Aeroportos de saída
          <input name="vooOrigens" defaultValue={v?.origens.join(", ") ?? ""} placeholder="GRU, CGH, VCP" />
        </label>
        <label>
          Aeroportos de chegada
          <input name="vooDestinos" defaultValue={v?.destinos.join(", ") ?? ""} placeholder="SSA, VDC" />
        </label>
        <label>
          Datas de ida (AAAA-MM-DD)
          <input name="vooDatas" defaultValue={v?.datas.join(", ") ?? ""} placeholder="2026-12-24, 2026-12-25" />
        </label>
        <label>
          Máximo de paradas
          <input name="vooMaxParadas" inputMode="numeric" defaultValue={v?.max_paradas ?? ""} placeholder="1" />
        </label>
        <label>
          Reler a cada (horas)
          <input name="vooIntervaloH" inputMode="numeric" defaultValue={v?.intervalo_h ?? ""} placeholder="4" />
        </label>
      </div>
    </fieldset>
  );
}

function FormRegra({ r }: { r?: Regra }) {
  return (
    <form action={salvarRegra} className="campos">
      {r && <input type="hidden" name="id" value={r.id} />}
      <label>
        Grupo
        <input name="grupo" defaultValue={r?.grupo} placeholder="Cozinha" required />
      </label>
      <label>
        Nome
        <input name="nome" defaultValue={r?.nome} placeholder="Cooktop Electrolux a gás" required />
      </label>
      <label>
        Prioridade
        <select name="prioridade" defaultValue={r?.prioridade ?? "normal"}>
          <option value="alta">Alta: janela no PC + celular</option>
          <option value="normal">Normal: só no painel</option>
        </select>
      </label>
      <label>
        Precisa ter todos (vírgula)
        <input name="precisa" defaultValue={r ? lista(r.precisa).join(", ") : ""} placeholder="cooktop, electrolux, gas" />
      </label>
      <label>
        Precisa ter pelo menos um
        <input name="qualquer" defaultValue={r ? lista(r.qualquer).join(", ") : ""} />
      </label>
      <label>
        Não pode ter
        <input name="naoPode" defaultValue={r ? lista(r.naoPode).join(", ") : ""} placeholder="capa, pelicula" />
      </label>
      <label>
        Preço mínimo (R$)
        <input name="precoMin" inputMode="decimal" defaultValue={r?.precoMin ?? ""} />
      </label>
      <label>
        Preço máximo (R$)
        <input name="precoMax" inputMode="decimal" defaultValue={r?.precoMax ?? ""} />
      </label>
      <label>
        Preço normal (R$) · calcula o % OFF
        <input name="precoReferencia" inputMode="decimal" defaultValue={r?.precoReferencia ?? ""} />
      </label>
      <label>
        Desconto mínimo (%)
        <input name="descontoMin" inputMode="numeric" defaultValue={r?.descontoMin ?? ""} />
      </label>
      <label>
        Votos mínimos no Pelando (°)
        <input name="temperaturaMin" inputMode="numeric" defaultValue={r?.temperaturaMin ?? ""} />
      </label>
      <label>
        Vale até
        <input name="ate" type="date" defaultValue={r?.ate ?? ""} />
      </label>
      <FormVoo r={r} />
      <button className="btn btn-primario" type="submit">
        {r ? "Salvar" : "Criar regra"}
      </button>
    </form>
  );
}

export default async function Regras() {
  const [regras, buscas] = await Promise.all([
    prisma.regra.findMany({ orderBy: { ordem: "asc" } }),
    prisma.busca.findMany({ orderBy: { ordem: "asc" } }),
  ]);
  const grupos = [...new Set(regras.map((r) => r.grupo))];

  return (
    <>
      <Topo />
      <main className="pagina">
        <div className="cabeca">
          <div>
            <h1>Regras</h1>
            <p>O que o PC caça. Ele lê estas regras a cada coleta; a primeira que bater vence.</p>
          </div>
        </div>

        {grupos.map((g) => (
          <section key={g} className="secao">
            <div className="secao-cabeca">
              <h2>{g}</h2>
              <span className="contagem">{regras.filter((r) => r.grupo === g).length}</span>
            </div>
            {regras
              .filter((r) => r.grupo === g)
              .map((r) => (
                <details key={r.id} className={`regra${r.ativa ? "" : " desligada"}`}>
                  <summary>
                    <span className="nome">{r.nome}</span>
                    <span className={`etiqueta ${r.prioridade}`}>{r.prioridade}</span>
                    <span className="resumo-alvo">{resumo(r)}</span>
                  </summary>
                  <div className="dentro">
                    <FormRegra r={r} />
                    <div className="acoes">
                      <form action={alternarRegra}>
                        <input type="hidden" name="id" value={r.id} />
                        <button className="btn btn-secundario" type="submit">
                          {r.ativa ? "Desligar" : "Ligar"}
                        </button>
                      </form>
                      <form action={apagarRegra}>
                        <input type="hidden" name="id" value={r.id} />
                        <button className="btn btn-perigo" type="submit">
                          Apagar
                        </button>
                      </form>
                    </div>
                  </div>
                </details>
              ))}
          </section>
        ))}

        <section className="secao">
          <div className="secao-cabeca">
            <h2>Nova regra</h2>
          </div>
          <details className="regra" open={regras.length === 0}>
            <summary>
              <span className="nome">Criar regra</span>
            </summary>
            <div className="dentro">
              <FormRegra />
            </div>
          </details>
        </section>

        <section className="secao">
          <div className="secao-cabeca">
            <h2>Buscas no Pelando</h2>
            <span className="contagem">{buscas.length}</span>
          </div>
          <p className="resumo-alvo" style={{ marginTop: 0 }}>
            Os termos que o PC pesquisa. As regras só enxergam o que aparece nestas buscas.
          </p>
          <div className="buscas">
            {buscas.map((b) => (
              <span key={b.id} className={`busca${b.ativa ? "" : " desligada"}`}>
                {b.termo}
                {b.ate && <small> · até {dataBr(b.ate)}</small>}
                <form action={alternarBusca}>
                  <input type="hidden" name="id" value={b.id} />
                  <button type="submit" title={b.ativa ? "Desligar" : "Ligar"}>
                    {b.ativa ? "pausar" : "ligar"}
                  </button>
                </form>
                <form action={apagarBusca}>
                  <input type="hidden" name="id" value={b.id} />
                  <button type="submit" title="Apagar">
                    ×
                  </button>
                </form>
              </span>
            ))}
          </div>
          <form action={salvarBusca} className="campos">
            <label>
              Novo termo
              <input name="termo" placeholder="lava loucas electrolux" required />
            </label>
            <label>
              Vale até (opcional)
              <input name="ate" type="date" />
            </label>
            <button className="btn btn-primario" type="submit">
              Adicionar busca
            </button>
          </form>
        </section>
      </main>
    </>
  );
}
