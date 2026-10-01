import type { Regra } from "@prisma/client";
import { prisma } from "@/lib/db";
import { Topo } from "@/components/topo";
import { lista, reais } from "@/lib/formato";
import { alternarBusca, alternarRegra, apagarBusca, apagarRegra, salvarBusca, salvarRegra } from "./actions";

export const dynamic = "force-dynamic";

const dataBr = (iso: string) => iso.split("-").reverse().join("/");

function resumo(r: Regra) {
  const partes = [r.precoMax != null ? `até ${reais(r.precoMax)}` : "qualquer preço"];
  if (r.precoReferencia != null) partes.push(`normal ${reais(r.precoReferencia)}`);
  if (r.descontoMin != null) partes.push(`${r.descontoMin}%+ de desconto`);
  if (r.temperaturaMin != null) partes.push(`${r.temperaturaMin}°+ no Pelando`);
  if (r.ate) partes.push(`vale até ${dataBr(r.ate)}`);
  if (!r.ativa) partes.push("desligada");
  return partes.join(" · ");
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
