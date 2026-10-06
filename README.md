# PromoTrix

Caçador de promoções. Um **coletor no PC (Windows)** lê o [Pelando](https://www.pelando.com.br) de tempos
em tempos e **avisa na tela** quando aparece uma promoção ativa dentro do preço que você definiu. Um
**painel web** (Next.js) guarda o histórico de preços, deixa editar os produtos e alvos pelo celular e
manda **notificação push** das promoções importantes.

Além das lojas, ele acompanha **preço de passagem aérea** no Google Flights: uma regra com trecho e
datas vira um alerta igual ao das promoções, com histórico de preço do voo.

```
            PC (Windows) — coletor/                         Servidor — web/
  ┌──────────────────────────────────────────┐        ┌───────────────────────────────┐
  │ a cada 30 min (Agendador de Tarefas)     │  GET   │ /api/coletor/config            │
  │ 1. busca as regras ──────────────────────┼───────▶│   buscas e regras (SQLite)     │
  │ 2. lê o Pelando (internet de casa)       │        │                               │
  │ 3. confere as regras                     │  POST  │ /api/coletor/coleta            │
  │ 4. janela grande na tela (alta)          ├───────▶│   histórico + push no celular  │
  │ 5. envia o que encontrou                 │        │ painel · regras · histórico    │
  └──────────────────────────────────────────┘        └───────────────────────────────┘
```

**Por que a leitura acontece no PC, e não no servidor:** o Pelando fica atrás da Cloudflare, que mostra
a tela "Just a moment…" (erro 403) para IPs de data center. Da internet de casa, a página pública
responde normalmente. O Mercado Livre e a Amazon bloqueiam leitura automática até de casa (login e
captcha), e o Pelando já traz as promoções deles, com o cupom, poucos minutos depois de aparecerem.

O coletor também funciona **sozinho**, sem o painel web: aí as regras ficam no `coletor/config.json`
e o painel vira um `painel.html` local.

## Estrutura

| Pasta | O que é |
|---|---|
| `coletor/` | Python 3.10+, só a biblioteca padrão. `promotrix.py` (coleta e regras), `voos.py` (passagem aérea no Google Flights), `alerta.py` (janela com tkinter), `instalar-tarefa.ps1` (Agendador de Tarefas) |
| `web/` | Next.js 15 + Prisma (SQLite) + Auth.js + Web Push. Docker e deploy por GitHub Actions + SSH |
| `.github/workflows/deploy.yml` | Deploy do `web/` numa VPS por SSH a cada push na `main` |

## Coletor (Windows)

```powershell
cd coletor
copy config.example.json config.json      # buscas e regras (modo sozinho)
python promotrix.py --listar              # o que bate nas regras agora
python promotrix.py --voos                # lê os trechos de passagem na hora, sem esperar o intervalo
python promotrix.py --teste               # mostra a janela de alerta
powershell -ExecutionPolicy Bypass -File instalar-tarefa.ps1   # 2 min após o logon e a cada 30 min
```

Para ligar ao painel web, copie `servidor.example.json` para `servidor.json`, com a URL e o
`COLETOR_TOKEN` do servidor. Depois mande as suas regras uma vez:

```powershell
python promotrix.py --enviar-config            # só funciona com o banco vazio
python promotrix.py --enviar-config --substituir
```

Com `--substituir`, regras e buscas casam pelo nome/termo: as que continuam são atualizadas no lugar
(o histórico de preços e o liga/desliga ficam), as novas são criadas e só as que saíram do arquivo são
apagadas.

A partir daí, as regras vêm do servidor. A última cópia fica em `config-cache.json`, e se o servidor
cair o coletor continua usando ela.

### Regras

| Campo | O que faz |
|---|---|
| `voo` | Passagem aérea: a regra deixa de olhar o Pelando (veja abaixo) |
| `grupo`, `nome` | Seção do painel e nome do alerta |
| `prioridade` | `alta`: janela grande na tela + push no celular. `normal`: só painel e uma notificação discreta |
| `precisa` | **Todos** estes termos têm de aparecer no título ou no nome da loja |
| `qualquer` | Pelo menos **um** destes termos tem de aparecer |
| `nao_pode` | Nenhum destes pode aparecer no título (acessórios, capas, voltagem errada...) |
| `preco_min` / `preco_max` | Faixa de preço em reais, já com desconto |
| `temperatura_min` | Mínimo de votos (°) no Pelando, um filtro de "promoção boa de verdade" |
| `preco_referencia` | Preço normal do produto na loja (para regra de **um produto só**). Serve para calcular o % de desconto e liga o selo "Menor preço" |
| `desconto_min` | Só bate se o desconto conhecido for pelo menos este % |
| `ate` | `AAAA-MM-DD`: a regra (ou busca) para sozinha depois dessa data |

A comparação ignora maiúsculas e acentos. A primeira regra que bater vence. Cada promoção avisa uma
vez, e só avisa de novo se o preço cair.

### De onde vem o % de desconto

O Pelando não guarda o preço "de" (antes do desconto), e as lojas bloqueiam leitura automática. Por
isso o PromoTrix **não inventa** porcentagem: ele usa a maior entre estas fontes, quando existem, e
mostra a origem no selo.

1. O desconto que o Pelando informa (vem preenchido em ofertas de cupom).
2. Um "X% OFF" ou "X% de desconto" escrito no título da oferta.
3. O `preco_referencia` da regra: `(normal - preço) / normal`.

Sem nenhuma delas, a oferta aparece sem %. A faixa **Grandes oportunidades** do painel junta o que tem
15% ou mais de desconto, 300° ou mais no Pelando, ou o menor preço já visto (com pelo menos 3 ofertas
no histórico de uma regra de produto único).

### Passagem aérea (Google Flights)

Uma regra com o bloco `voo` para de procurar no Pelando e passa a acompanhar o preço de um trecho:

```json
{
  "grupo": "Passagens",
  "nome": "Natal na Bahia (24 ou 25/12)",
  "prioridade": "alta",
  "preco_max": 900,
  "ate": "2026-12-25",
  "voo": {
    "origens": ["GRU", "CGH", "VCP"],
    "destinos": ["SSA", "VDC"],
    "datas": ["2026-12-24", "2026-12-25"],
    "max_paradas": 1,
    "intervalo_h": 4
  }
}
```

Para cada destino em cada data, ele guarda **o voo mais barato** dentro do limite de paradas. Assim o
histórico do painel vira a série de preços daquele dia, e o alerta dispara quando o dia fica mais
barato — a mesma regra das promoções: avisa uma vez, e só de novo se o preço cair. `preco_max` e
`preco_referencia` valem igual; os campos de termo e de votos não valem para passagem.

A busca não é uma API: ela vai num parâmetro `tfs`, um protobuf em base64 que o `coletor/voos.py`
monta à mão, e a página de resultados já vem pronta no HTML — não precisa de navegador nem de login.
Como não é documentado pelo Google, pode mudar sem aviso; `python promotrix.py --voos` lê todos os
trechos na hora e mostra o que encontrou, que é o jeito de conferir se ainda funciona.

Cada trecho é uma página de alguns MB, e passagem não muda de preço de meia em meia hora: por isso o
`intervalo_h` (4 por padrão), e por isso vários aeroportos de saída entram na **mesma** consulta.
Entre duas leituras, o último preço continua valendo no painel. O Google também diz se o trecho está
com preço baixo, normal ou alto, e isso aparece no cartão.

## Painel web (`web/`)

Rodar localmente:

```bash
cd web
cp .env.example .env          # preencha AUTH_SECRET, COLETOR_TOKEN, ADMIN_*, VAPID (npm run vapid)
npm install
npx prisma migrate dev        # cria o banco SQLite
npm run admin                 # cria o primeiro usuário
npm run dev                   # http://localhost:3000
```

Telas: **Painel** (grandes oportunidades no topo e, abaixo, o que a última coleta achou, por grupo,
com foto, % de desconto e votos), **Regras** (editar produtos, alvos e
buscas), **Histórico** (tudo o que já bateu em cada regra e o menor preço visto). No celular, o painel
pode ser instalado como app (PWA). O botão "Receber as promoções importantes neste celular" liga o
push. No iPhone, isso só funciona com o app adicionado à tela de início.

### Deploy (VPS com Docker)

O `docker-compose.yml` sobe o projeto isolado:
- containers `promotrix_*`, com rede e volume próprios;
- banco SQLite no volume;
- porta `APP_PORT`, que por padrão é 3200.

O `scripts/deploy.sh` segue esta ordem: build, migrations com o app antigo ainda no ar, recriação dos
containers e healthcheck. Se a migration falhar, o app antigo continua servindo.

1. No servidor, crie `DEPLOY_PATH/.env` a partir do `.env.example`, com chaves novas.
2. No GitHub, em *Settings → Secrets → Actions*, cadastre `HOSTINGER_IP`, `SSH_USER`, `SSH_PORT`,
   `SSH_PRIVATE_KEY` e `DEPLOY_PATH`.
3. Faça push na `main`, ou rode o workflow à mão em *Actions*.
4. Publique a porta: por um proxy reverso, ou por um Cloudflare Tunnel apontando o domínio para
   `http://<host>:APP_PORT`.

## Limites e boas maneiras

- O coletor só funciona com o **PC ligado e o usuário logado**. Promoção que aparece e acaba com o PC
  desligado é perdida. O painel avisa quando a última coleta passou de 2 horas.
- Ele lê uma página pública: mantenha 30 minutos ou mais de intervalo, poucas buscas e a pausa entre
  elas (`pausa_entre_buscas_s`). É uma ferramenta de uso pessoal.
- **Não tente rodar o coletor no servidor contornando a proteção da Cloudflare.**

## Se parar de funcionar

Se o Google Flights mudar a página, as passagens somem do painel e o `promotrix.log` registra
"nenhum voo lido" em cada trecho. `python promotrix.py --voos` mostra o mesmo na hora. O que o
`coletor/voos.py` lê é o `aria-label` de cada `<li class="pIav2d">` e o ícone `ic_price_low/typical/high`.

Se o Pelando mudar a página, o coletor avisa uma vez por dia ("parou de ler o Pelando"). Ele procura
cada promoção pelo trecho `"id":[0,"<uuid>"],"slug":` e lê os campos no formato `"campo":[0,valor]`.
Isso fica em `INICIO` e `campo()`, no `coletor/promotrix.py`. O cupom vem da página da promoção
(`/d/<slug>`), no atributo `data-code`. Os erros vão para o `coletor/promotrix.log`.
