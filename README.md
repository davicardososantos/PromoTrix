# PromoTrix

Caçador de promoções. Um **coletor no PC (Windows)** lê o [Pelando](https://www.pelando.com.br) de tempos
em tempos e **avisa na tela** quando aparece uma promoção ativa dentro do preço que você definiu. Um
**painel web** (Next.js) guarda o histórico de preços, deixa editar os produtos e alvos pelo celular e
manda **notificação push** das promoções importantes.

Além das lojas, ele acompanha **preço de passagem aérea** no Google Flights: uma regra com trecho e
datas vira um alerta igual ao das promoções, com histórico de preço do voo. E lê os **cupons de loja**
(Mercado Livre, Shopee, Amazon, Magalu): avisa quando um cupom pode servir num item que você monitora.

```
            PC (Windows) — coletor/                         Servidor — web/
  ┌──────────────────────────────────────────┐        ┌───────────────────────────────┐
  │ a cada 15 min (Agendador de Tarefas)     │  GET   │ /api/coletor/config            │
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
| `coletor/` | Python 3.10+, só a biblioteca padrão. `promotrix.py` (coleta e regras), `voos.py` (passagem aérea no Google Flights), `alerta.py` (janela com tkinter), `instalar-tarefa.ps1` (Agendador de Tarefas), `bandeja.py` (ícone perto do relógio, opcional, precisa do `pystray`) |
| `web/` | Next.js 15 + Prisma (SQLite) + Auth.js + Web Push. Docker e deploy por GitHub Actions + SSH |
| `.github/workflows/deploy.yml` | Deploy do `web/` numa VPS por SSH a cada push na `main` |

## Coletor (Windows)

```powershell
cd coletor
copy config.example.json config.json      # buscas e regras (modo sozinho)
python promotrix.py --listar              # o que bate nas regras agora
python promotrix.py --voos                # lê os trechos de passagem na hora, sem esperar o intervalo
python promotrix.py --cupons              # cupons de loja ativos e em que itens servem
python promotrix.py --teste               # mostra a janela de alerta
powershell -ExecutionPolicy Bypass -File instalar-tarefa.ps1   # 2 min após o logon e a cada 15 min
```

### Ícone na bandeja (opcional)

A tarefa roda escondida. Para ver de relance se o PromoTrix está vivo, o `bandeja.py` põe um ícone
amarelo com "P" perto do relógio. A bolinha mostra o estado: **verde** (a última busca deu certo),
**azul** (buscando agora), **laranja** (funcionou, mas com aviso), **vermelha** (erro, ou nenhuma busca
terminou na última hora e pouco) e **cinza** (pausado). Passar o mouse mostra a última busca e a próxima.
O clique abre o painel e o botão direito tem "Buscar agora", "Ver log", "Pausar buscas" e "Iniciar com o Windows".

```powershell
pip install pystray
python bandeja.py --instalar     # abre junto com o Windows (pasta Inicializar) e já abre agora
python bandeja.py --remover      # tira da inicialização
```

No Windows 11 o ícone novo fica escondido na setinha `^`. Para deixá-lo sempre à vista, arraste-o
para a barra, ou ligue em Configurações > Personalização > Barra de tarefas > Outros ícones da bandeja.

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

### Cupons de loja

Cupom de loja ("R$ 300 OFF em R$ 1999" no Mercado Livre) é um post do Pelando **sem produto**. Ele
chega pelas buscas `cupom mercado livre`, `cupom shopee`, `cupom amazon` e `cupom magalu` (outra loja:
é só criar a busca `cupom <loja>`) e não passa pelas regras como promoção. O coletor lê o valor (% ou
reais), a compra mínima e o limite do desconto, e confere cada regra:

1. o preço do item cabe na compra mínima. O preço é o `preco_referencia` ou, sem ele, o `preco_max`;
   regra sem nenhum dos dois fica de fora;
2. a categoria escrita no cupom ("em Tecnologia", "em itens Electrolux") bate com o item. A marca casa
   direto com os termos da regra; as categorias ficam em `CATEGORIAS`, no `promotrix.py`. Cupom sem
   categoria vale para a loja toda; categoria desconhecida ("em Ferramentas") não serve;
3. o desconto no item chega a 10% do preço (`CUPOM_MIN_PCT`): "R$ 40 OFF em R$ 199" não conta num celular.

O cupom que serve avisa **uma vez**, com a prioridade mais alta entre os itens. O aviso é mais
discreto que o de promoção, para não confundir cupom com produto: na prioridade alta, um cartão escuro
no canto da tela com um som curto (sem alarme, sem piscar, sem tomar o foco) e push **silencioso** no
celular; na normal, só a notificação do Windows. `python promotrix.py --teste-cupom` mostra o cartão.
O mesmo cupom repostado por outra pessoa não avisa de novo por 3 dias. Ficam de
fora os de primeira compra, os de frete grátis (sem valor para calcular) e os marcados como resgatados.
O código do cupom só aparece na página do post: cada um é aberto **uma vez** (no máximo 10 por rodada)
e o código fica no `estado.json`.

O PromoTrix **não sabe se o anúncio aceita o cupom** (muitos valem só para "itens selecionados"): o
aviso diz em que itens ele **pode** servir e quanto daria no preço normal, sem inventar preço final.
Quem confirma é o carrinho. Todos os cupons ativos, sirvam ou não, vão para a aba **Cupons** do site.

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
histórico do painel vira a série de preços daquele dia.

Passagem é acompanhada **sempre**, por qualquer preço: ela aparece no painel e no histórico desde a
primeira leitura, para dar para ver o preço subir e descer. O `preco_max` aqui é só o **alvo do
aviso** — a janela no PC e o push só saem quando o trecho chega nele, e aí vale a mesma regra das
promoções: avisa uma vez, e só de novo se o preço cair. Os campos de termo e de votos não valem para
passagem; `preco_referencia` vale igual.

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

Telas: **Painel** (grandes oportunidades e os cupons que servem nos seus itens no topo e, abaixo, o
que a última coleta achou, por grupo, com foto, % de desconto e votos), **Cupons** (todos os cupons de
loja ativos, por loja: primeiro os que servem nos itens, depois os mais votados), **Regras** (editar
produtos, alvos e buscas), **Histórico** (tudo o que já bateu em cada regra e o menor preço visto).

Oferta que já mudou de preço ganha, nas duas telas, a **curva do preço** com quanto subiu ou desceu
desde a primeira leitura e o menor valor visto. É o que deixa acompanhar uma passagem pelo site. Os
pontos ficam na tabela `Preco`, gravados só quando o valor muda. No celular, o painel
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
- Ele lê uma página pública: mantenha 15 minutos ou mais de intervalo, poucas buscas e a pausa entre
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
