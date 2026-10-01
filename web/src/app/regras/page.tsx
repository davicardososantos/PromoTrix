import type { Regra } from "@prisma/client";
import { prisma } from "@/lib/db";
import { Topo } from "@/components/topo";
import { lista, reais } from "@/lib/formato";
import { alternarBusca, alternarRegra, apagarBusca, apagarRegra, salvarBusca, salvarRegra } from "./actions";

export const dynamic = "force-dynamic";

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
          <option value="alta">Alta (janela grande + celular)</option>
          <option value="normal">Normal (só painel)</option>
        </select>
      </label>
      <label>
        Precisa ter todos (separe por vírgula)
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
        Votos mínimos no Pelando (°)
        <input name="temperaturaMin" inputMode="numeric" defaultValue={r?.temperaturaMin ?? ""} />
      </label>
      <label>
        Vale até (data)
        <input name="ate" type="date" defaultValue={r?.ate ?? ""} />
      </label>
      <button className="botao" type="submit">
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
      <main>
        <h1>Regras</h1>
        <p className="suave">
          O PC lê estas regras a cada coleta. A primeira que bater vence. Maiúsculas e acentos não importam.
        </p>

        {grupos.map((g) => (
          <section key={g}>
            <h2>{g}</h2>
            {regras
              .filter((r) => r.grupo === g)
              .map((r) => (
                <details key={r.id} className={r.ativa ? "" : "desligada"}>
                  <summary>
                    <span className="nome">{r.nome}</span>
                    <span className={`etiqueta ${r.prioridade}`}>{r.prioridade}</span>
                    <span className="suave">
                      {r.precoMax != null ? `até ${reais(r.precoMax)}` : "qualquer preço"}
                      {r.ate ? ` · até ${r.ate.split("-").reverse().join("/")}` : ""}
                      {r.ativa ? "" : " · desligada"}
                    </span>
                  </summary>
                  <FormRegra r={r} />
                  <div className="acoes">
                    <form action={alternarRegra}>
                      <input type="hidden" name="id" value={r.id} />
                      <button className="botao secundario" type="submit">
                        {r.ativa ? "Desligar" : "Ligar"}
                      </button>
                    </form>
                    <form action={apagarRegra}>
                      <input type="hidden" name="id" value={r.id} />
                      <button className="botao perigo" type="submit">
                        Apagar
                      </button>
                    </form>
                  </div>
                </details>
              ))}
          </section>
        ))}

        <h2>Nova regra</h2>
        <details open={regras.length === 0}>
          <summary>
            <span className="nome">Criar regra</span>
          </summary>
          <FormRegra />
        </details>

        <h2>Buscas no Pelando</h2>
        <p className="suave">Termos que o PC pesquisa. As regras só enxergam o que aparece nestas buscas.</p>
        <table>
          <tbody>
            {buscas.map((b) => (
              <tr key={b.id} className={b.ativa ? "" : "desligada"}>
                <td>{b.termo}</td>
                <td className="suave">{b.ate ? `até ${b.ate.split("-").reverse().join("/")}` : ""}</td>
                <td>
                  <div className="acoes" style={{ marginTop: 0 }}>
                    <form action={alternarBusca}>
                      <input type="hidden" name="id" value={b.id} />
                      <button className="botao secundario" type="submit">
                        {b.ativa ? "Desligar" : "Ligar"}
                      </button>
                    </form>
                    <form action={apagarBusca}>
                      <input type="hidden" name="id" value={b.id} />
                      <button className="botao perigo" type="submit">
                        Apagar
                      </button>
                    </form>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <form action={salvarBusca} className="campos" style={{ marginTop: 12 }}>
          <label>
            Novo termo
            <input name="termo" placeholder="lava loucas electrolux" required />
          </label>
          <label>
            Vale até (data, opcional)
            <input name="ate" type="date" />
          </label>
          <button className="botao" type="submit">
            Adicionar busca
          </button>
        </form>
      </main>
    </>
  );
}
