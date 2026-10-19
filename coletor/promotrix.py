"""PromoTrix: caçador de promoções que lê o Pelando e avisa na tela.

O Pelando (pelando.com.br) junta promoções de Mercado Livre, Amazon, Shopee, Magalu e outras lojas,
com o cupom, poucos minutos depois de elas aparecerem. O PromoTrix lê as buscas de config.json,
confere cada promoção ATIVA com as regras e:
  - prioridade "alta": abre uma janela grande no meio da tela, com som (alerta.py);
  - prioridade "normal": entra no painel, com uma notificação discreta do Windows;
  - sempre: refaz o painel.html com tudo o que está valendo agora, separado por grupo.
Cada promoção avisa uma vez. Só avisa de novo se o preço dela cair.

Cupom de loja ("R$ 300 OFF em R$ 1999" no Mercado Livre) é um post sem produto. Ele não passa pelas
regras como promoção: avisa quando serve num item monitorado (veja "cupons das lojas", mais abaixo),
com a mesma prioridade do item. As buscas "cupom mercado livre", "cupom shopee"... trazem esses posts.

Regra com um bloco "voo" não olha o Pelando: ela acompanha o preço de uma passagem aérea no Google
Flights (voos.py) e segue pelo mesmo caminho. Como passagem não muda de preço de meia em meia hora,
cada uma dessas regras tem o seu "intervalo_h".

Com o painel web (pasta ../web) ligado, crie o servidor.json (veja servidor.example.json). Aí:
  - as buscas e regras vêm do servidor, onde dá pra editar pelo celular. A última cópia fica em
    config-cache.json, e o coletor segue funcionando se o servidor estiver fora;
  - cada execução manda para o servidor o que encontrou. Lá vira histórico e notificação no celular.
Sem servidor.json, tudo funciona só no PC, com o config.json.

Uso:
  python promotrix.py                              checa e avisa (o que a tarefa agendada faz)
  python promotrix.py --listar                     mostra o que bate nas regras agora, sem avisar nem gravar
  python promotrix.py --painel                     refaz o painel e abre no navegador
  python promotrix.py --voos                       mostra os voos das regras de passagem, sem esperar o intervalo
  python promotrix.py --cupons                     mostra os cupons lidos e em que itens servem, sem avisar nem gravar
  python promotrix.py --teste                      abre a janela de alerta com um exemplo
  python promotrix.py --teste-cupom                abre o aviso discreto de cupom com um exemplo
  python promotrix.py --enviar-config [--substituir]  manda o config.json local para o servidor
"""
import base64
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import voos

PASTA = Path(__file__).resolve().parent
CONFIG = PASTA / "config.json"
CONFIG_CACHE = PASTA / "config-cache.json"
SERVIDOR = PASTA / "servidor.json"
ESTADO = PASTA / "estado.json"
LOG = PASTA / "promotrix.log"
PAINEL = PASTA / "painel.html"
RODANDO = PASTA / "rodando.txt"  # existe enquanto uma busca está em andamento (a bandeja.py lê)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
BRT = timezone(timedelta(hours=-3))
SEM_JANELA = 0x08000000  # CREATE_NO_WINDOW: o PowerShell da notificação não pisca na tela
DIAS_GUARDANDO_AVISOS = 90

# O Pelando serializa cada promoção como "campo":[0,valor]. Cada uma começa no id + slug.
INICIO = re.compile(r'"id":\[0,"[0-9a-f-]{36}"\],"slug":\[0,"')


# ---------------------------------------------------------------- utilidades

def agora():
    return datetime.now(BRT)


def log(msg):
    if LOG.exists() and LOG.stat().st_size > 300_000:
        LOG.write_text(LOG.read_text(encoding="utf-8")[-150_000:], encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{agora():%Y-%m-%d %H:%M} {msg}\n")


def normalizar(texto):
    """Minúsculas e sem acento, para comparar 'Lava-Louças' com 'lava-loucas'."""
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                   if unicodedata.category(c) != "Mn")


def reais(valor):
    if valor is None:
        return "sem preço"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ler_json(caminho, padrao):
    # utf-8-sig: aceita arquivo salvo com BOM (o Out-File do PowerShell 5.1 põe BOM)
    return json.loads(caminho.read_text(encoding="utf-8-sig")) if caminho.exists() else padrao


def vigente(item, hoje):
    """Regras e buscas podem ter "ate": "AAAA-MM-DD" e param sozinhas depois dessa data."""
    return not item.get("ate") or hoje <= item["ate"]


# ---------------------------------------------------------------- Pelando

def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return html.unescape(r.read().decode("utf-8", errors="replace"))


def campo(trecho, nome):
    m = re.search(r'"%s":\[0,("([^"]*)"|[0-9.]+|null)' % nome, trecho)
    if not m:
        return None
    return m.group(2) if m.group(2) is not None else (None if m.group(1) == "null" else m.group(1))


def promocoes(termo):
    pagina = baixar("https://www.pelando.com.br/busca/" + urllib.parse.quote(termo))
    inicios = [m.start() for m in INICIO.finditer(pagina)] + [len(pagina)]
    achadas = {}
    for a, b in zip(inicios, inicios[1:]):
        t = pagina[a:b]
        id_, slug, titulo = campo(t, "id"), campo(t, "slug"), campo(t, "title")
        if not (id_ and slug and titulo) or id_ in achadas:
            continue
        loja = re.search(r'"store":\[0,\{"id":\[0,"\d+"\],"name":\[0,"([^"]+)"', t)
        preco, temperatura = campo(t, "price"), campo(t, "temperature")
        # As imagens do Pelando têm o endereço assinado por tamanho (".../<assinatura>=/0x300/..."): não dá
        # para trocar o tamanho no link. Pega a maior versão que vem pronta no srcset.
        tamanhos = re.findall(r'"url":\[0,"(https://media\.pelando\.com\.br/[^"]+)"\],"width":\[0,(\d+)\]', t)
        imagem = max(tamanhos, key=lambda u: int(u[1]))[0] if tamanhos else campo(t, "imageUrl")
        pct, fixo = campo(t, "discountPercentage"), campo(t, "discountFixed")
        achadas[id_] = {
            "id": id_,
            "titulo": titulo.strip(),
            "preco": float(preco) if preco else None,
            "status": campo(t, "status"),
            "criada": campo(t, "createdAt"),
            "loja": loja.group(1) if loja else "?",
            "temperatura": float(temperatura) if temperatura else 0.0,
            "link": "https://www.pelando.com.br/d/" + slug,
            "imagem": imagem,
            # Só vem preenchido em cupom ("20% OFF em LEGO"); em oferta comum o Pelando não guarda o "de/por".
            "desconto_pelando": float(pct) if pct and float(pct) > 0 else None,
            # Post de cupom de loja, sem produto: "coupon". Nele o valor em reais é o desconto fixo
            # ("R$ 300 OFF") ou o limite do % ("10% limitado a R$ 20"), conforme o título.
            "tipo": campo(t, "kind"),
            "desconto_fixo": float(fixo) if fixo and float(fixo) > 0 else None,
            "fonte": "pelando",
        }
    return achadas


def desconto(p, regra):
    """% de desconto, só a partir de dado real. Devolve (porcentagem, de onde veio) ou (None, None).

    1. o % que o Pelando informa (cupons);
    2. um "X% OFF" escrito no título;
    3. o "preço normal" cadastrado na regra (preco_referencia), tirado de loja de verdade.
    O Pelando não guarda o preço antigo das ofertas, e as lojas bloqueiam leitura automática."""
    opcoes = []
    if p.get("desconto_pelando"):
        opcoes.append((p["desconto_pelando"], "informado no " + ("Promobit" if p.get("fonte") == "promobit" else "Pelando")))
    m = re.search(r"(\d{1,2})\s?%\s?(?:off|de desconto)", normalizar(p["titulo"]))
    if m:
        opcoes.append((float(m.group(1)), "escrito na oferta"))
    ref = regra.get("preco_referencia") if regra else None
    if ref and p["preco"] and p["preco"] < ref:
        opcoes.append((round((ref - p["preco"]) / ref * 100), f"abaixo do preço normal ({reais(ref)})"))
    return max(opcoes) if opcoes else (None, None)


def origem_preco(p, regra):
    """Igual a desconto(), mas a frase também traz o que o Google diz do trecho, nas passagens."""
    pct, origem = desconto(p, regra)
    if p.get("tendencia"):
        origem = " · ".join(x for x in (origem, "Google: " + p["tendencia"]) if x)
    return pct, origem


def cupom(link):
    try:
        m = re.search(r'data-code="([^"]+)"', baixar(link))
        return m.group(1) if m else None
    except Exception:
        return None


# ---------------------------------------------------------------- Promobit

# O Promobit (promobit.com.br) é outra comunidade de promoções. O site carrega a busca de uma API
# pública (api.promobit.com.br), a mesma que o navegador usa, e ela responde da internet de casa.
# Cada busca do config vira uma consulta lá também: "cupom <loja>" traz os cupons da loja, e o resto,
# as ofertas ativas. Tudo sai no formato de promocoes(), com "fonte": "promobit".
# A mesma oferta postada nos dois sites avisa uma vez só (veja sem_repetir_fontes).
PROMOBIT_API = "https://api.promobit.com.br"
# O Promobit demora a encerrar oferta: passado isto desde a postagem, ela não conta mais como ativa.
PROMOBIT_DIAS_OFERTA = 3
PROMOBIT_DIAS_CUPOM = 7
# Nome da loja no Promobit → nome no Pelando, para o painel e para achar a oferta repetida.
LOJAS = {"magazine luiza": "Magalu", "magazine voce": "Magalu", "parceiro magalu": "Magalu"}
# Código que não é código: o desconto entra pelo link ou pelo botão "Coletar" da loja.
SEM_CODIGO = ("link", "colet", "sem cod", "nao precisa", "automatic")


def promobit_json(caminho, **params):
    req = urllib.request.Request(
        PROMOBIT_API + caminho + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": UA, "Accept": "application/json", "Origin": "https://www.promobit.com.br",
                 "Referer": "https://www.promobit.com.br/"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def _data(txt):
    """'2026-10-19T15:16:46-0300' → datetime com fuso (None se não der)."""
    try:
        return datetime.fromisoformat(txt) if txt else None
    except ValueError:
        return None


def _recente(quando, dias):
    return quando is not None and agora() - quando <= timedelta(days=dias)


def _utc(quando):
    """No mesmo formato do Pelando ('...Z'), que o painel e o site já sabem ler."""
    return quando.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z") if quando else None


def loja_padrao(nome):
    return LOJAS.get(normalizar(nome).strip(), nome)


def promobit(termo):
    """Ofertas ativas do Promobit (ou os cupons da loja, numa busca "cupom <loja>"), no formato de promocoes()."""
    achadas = {}
    if normalizar(termo).startswith("cupom "):
        for c in promobit_json("/search/result/coupons", q=termo.split(" ", 1)[1].strip()).get("coupons", []):
            quando, ate = _data(c.get("coupon_published")), _data(c.get("coupon_until"))
            vale = c.get("coupon_status_name") == "APPROVED" and (
                ate >= agora() if ate else _recente(quando, PROMOBIT_DIAS_CUPOM))
            curto = normalizar(c.get("coupon_discount_short") or "")
            pct = re.match(r"(\d+(?:[.,]\d+)?)\s*%", curto)
            fixo = re.match(r"r\$\s*" + _NUM, curto)
            codigo = (c.get("coupon_code") or "").strip()
            id_ = f"promobit-cupom-{c['coupon_id']}"
            achadas[id_] = {
                "id": id_, "titulo": c["coupon_title"].strip(), "preco": None, "status": "active" if vale else "expired",
                "criada": _utc(quando), "loja": loja_padrao(c.get("store_name") or "?"), "temperatura": 0.0,
                "link": "https://www.promobit.com.br/cupons/" + (f"loja/{c['store_slug']}/" if c.get("store_slug") else ""),
                "imagem": None, "desconto_pelando": float(pct.group(1).replace(",", ".")) if pct else None,
                "tipo": "coupon", "desconto_fixo": numero(fixo.group(1)) if fixo else None, "fonte": "promobit",
                "codigo": codigo if codigo and not any(x in normalizar(codigo) for x in SEM_CODIGO) else None,
                # As condições de verdade (mínimo, limite, categoria) costumam estar aqui, não no título.
                "detalhes": html.unescape(c.get("coupon_instructions") or ""),
            }
        return achadas
    for o in promobit_json("/search/result/offers", q=termo, offer_status_name="APPROVED").get("offers", []):
        quando = _data(o.get("offer_published"))
        foto = (o.get("offer_photo") or "").lstrip("/")
        id_ = f"promobit-{o['offer_id']}"
        achadas[id_] = {
            "id": id_, "titulo": o["offer_title"].strip(),
            "preco": float(o["offer_price"]) if o.get("offer_price") else None,
            "status": "active" if o.get("offer_status_name") == "APPROVED" and _recente(quando, PROMOBIT_DIAS_OFERTA)
            else "expired",
            "criada": _utc(quando), "loja": loja_padrao(o.get("store_name") or "?"),
            # Curtida do Promobit não tem a escala dos graus do Pelando: não vira temperatura.
            "temperatura": 0.0, "link": f"https://www.promobit.com.br/oferta/{o['offer_slug']}/",
            "imagem": f"https://i.promobit.com.br/268/{foto}" if foto else None,
            # O "de" do Promobit é o preço riscado da loja, muitas vezes inflado (A57 "de R$ 4.299"):
            # não vira %. O % continua vindo do preço normal da regra.
            "desconto_pelando": None, "tipo": "offer", "desconto_fixo": None, "fonte": "promobit",
            "codigo": (o.get("offer_coupon") or "").strip() or None,
        }
    return achadas


def avisada_em_outra_fonte(p, r, avisados):
    """Oferta do Promobit que o Pelando já avisou nas últimas 24 h (mesma regra, loja e preço)."""
    if p.get("fonte") != "promobit" or not p["preco"]:
        return False
    desde = agora() - timedelta(hours=24)
    return any(k != p["id"] and v.get("regra") == r["nome"] and v.get("loja") == normalizar(p["loja"])
               and v.get("preco") and abs(v["preco"] - p["preco"]) <= max(5, v["preco"] * 0.01)
               and datetime.fromisoformat(v["em"]) >= desde for k, v in avisados.items())


def sem_repetir_fontes(ativas):
    """A mesma oferta nos dois sites (mesma regra, mesma loja, preço a até 1% ou R$ 5) fica uma vez só.
    O Pelando vem antes; a do Promobit só fica se não houver par."""
    ativas = sorted(ativas, key=lambda x: x[1].get("fonte") == "promobit")
    vistas, unicas = [], []
    for r, p in ativas:
        chave = (r["nome"], normalizar(p["loja"]))
        if p.get("fonte") == "promobit" and p["preco"] and any(
                k == chave and abs(v - p["preco"]) <= max(5, v * 0.01) for k, v in vistas):
            continue
        if p["preco"]:
            vistas.append((chave, p["preco"]))
        unicas.append((r, p))
    return unicas


# ---------------------------------------------------------------- cupons das lojas

# Um cupom serve num item monitorado quando:
#   1. o preço do item cabe na compra mínima do cupom. O preço é o normal da regra (preco_referencia)
#      ou, sem ele, o alvo (preco_max). Regra sem nenhum dos dois fica de fora;
#   2. a categoria escrita no cupom ("em Tecnologia", "em itens Electrolux") bate com o item. Cupom
#      sem categoria vale para a loja toda;
#   3. o desconto no item chega a CUPOM_MIN_PCT do preço. "R$ 40 OFF em R$ 199" num celular não conta.
# O PromoTrix não sabe se o anúncio aceita o cupom (muitos são "itens selecionados"): quem confirma é o
# carrinho. Por isso o aviso diz em que itens ele PODE servir, e não inventa o preço final.
CUPOM_MIN_PCT = 10
CUPOM_FORA = ("primeira compra", "1a compra", "novos usuarios", "novo usuario", "novos clientes", "novo cliente",
              "resgatado", "esgotado", "encerrado", "expirado")
CUPOM_REPETIDO_DIAS = 3  # o mesmo cupom (loja, valor, mínimo, limite) postado de novo não avisa outra vez
# Cupom postado há mais tempo que isto não avisa, mesmo que apareça agora pela primeira vez na busca:
# fica só na aba Cupons (muitos já esgotaram o limite de usos).
CUPOM_AVISO_DIAS = 2
# Palavras do "em ..." do título que não restringem nada.
ESCOPO_GERAL = {
    "loja", "lojas", "oficial", "oficiais", "item", "itens", "produto", "produtos", "selecionado", "selecionados",
    "selecionadas", "site", "todo", "toda", "app", "aplicativo", "compra", "compras", "ate", "sem", "juros",
    "off", "cupom", "e", "de", "do", "da", "dos", "das", "o", "a", "os", "as", "no", "na", "nos", "nas",
    "todas", "todos", "categoria", "categorias", "reais", "magalu", "shopee", "amazon", "mercado", "livre",
    "seus", "suas", "pedidos", "pedido", "aplicando", "melhores",
}
_TEC = ("a57", "galaxy", "iphone", "celular", "smartphone", "watch", "notebook", "tablet")
_CELULAR = ("a57", "galaxy", "iphone", "celular", "smartphone")
_ELETRO = ("cooktop", "lava", "forno", "depurador", "coifa", "fryer", "ar condicionado", "geladeira")
# Categoria escrita no cupom → termos das regras que entram nela. Uma marca escrita no cupom
# (Electrolux) não precisa estar aqui: ela casa direto com os termos da regra.
CATEGORIAS = {
    "tecnologia": _TEC, "eletronicos": _TEC, "eletronico": _TEC,
    "celular": _CELULAR, "celulares": _CELULAR, "smartphone": _CELULAR, "smartphones": _CELULAR,
    "telefonia": _CELULAR, "samsung": ("a57", "galaxy"), "apple": ("apple watch", "iphone"),
    "smartwatch": ("watch",), "smartwatches": ("watch",), "relogio": ("watch",), "relogios": ("watch",),
    "wearables": ("watch",),
    "eletrodomesticos": _ELETRO, "eletroportateis": _ELETRO, "eletro": _ELETRO, "cozinha": _ELETRO,
    "climatizacao": ("ar condicionado",), "ventilacao": ("ar condicionado",),
    "moda": ("renner",), "roupas": ("renner",), "vestuario": ("renner",),
}
_NUM = r"(\d[\d.,]*(?:\s*mil\b)?)"  # "1.999", "1.999,90", "1,6mil"
_MINIMO = re.compile(r"(?:acima de|a partir de|minim[oa] de|minim[oa]|compras de)\s*(?:r\$)?\s*" + _NUM
                     + r"|\bem r\$\s*" + _NUM)
_LIMITE = re.compile(r"(?:limitad[oa] a|limite de|limite|maximo de|maximo|\bmax\b)\s*(?:r\$)?\s*" + _NUM
                     + r"|\bate r\$\s*" + _NUM)
_FIXO = re.compile(r"r\$\s*" + _NUM + r"\s*(?:de )?(?:off|de desconto)")


def numero(txt):
    """'1.999' → 1999, '1.999,90' → 1999.9, '500' → 500, '1,6mil' → 1600."""
    mil = 1000 if txt.endswith("mil") else 1
    txt = txt.removesuffix("mil").strip().strip(".,")
    if mil > 1:
        return (numero(txt) or 0) * mil or None
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", txt):
        txt = txt.replace(".", "")
    try:
        return float(txt)
    except ValueError:
        return None


def _primeiro(regex, texto):
    m = regex.search(texto)
    return numero(next(g for g in m.groups() if g)) if m else None


def ler_cupom(p):
    """Valor, compra mínima, limite, categoria e condições de um post de cupom. None se não der para usar.

    No Pelando tudo vem no título. No Promobit o título costuma ser genérico ("Economize R$ 50 aplicando
    cupom Shopee") e as condições vêm nas instruções ("Compra mínima de R$ 450. Válido em: TECNOLOGIA.")."""
    t = normalizar(p["titulo"])
    instrucoes = normalizar(p.get("detalhes") or "")
    texto = t + " | " + instrucoes  # onde procurar mínimo, limite e o que exclui o cupom
    if any(x in texto for x in CUPOM_FORA):
        return None
    pct, fixo = p.get("desconto_pelando"), p.get("desconto_fixo")
    limite = _primeiro(_LIMITE, texto)
    if pct and pct > 100:  # "25000% OFF (até R$ 250)" no Promobit: erro de digitação, o valor é o limite
        pct, fixo, limite = None, fixo or limite, None
    if pct and "%" not in t and (fixo or _FIXO.search(t)):
        pct = None  # "R$ 15 OFF acima de R$ 180" às vezes vem do Pelando com 15%: o título manda
    if pct:
        limite = limite or fixo  # junto com um %, o valor em reais do Pelando é o limite
        fixo = None
    else:
        fixo = fixo or _primeiro(_FIXO, t)
        limite = None  # "R$ 50 OFF (até R$ 50)": em cupom de valor fixo, limite não muda nada
        if not fixo:
            return None  # frete grátis, "até 70% OFF" sem número...: nada para calcular
    minimo = 0.0 if re.search(r"sem (?:pedido |compra )?minim[oa]", texto) else _primeiro(_MINIMO, texto)
    trechos = [m.group(1) for m in re.finditer(r"\bem\s+(?!r\$|\d|compras)([a-z][^\[\]]*)", t)]
    trechos += re.findall(r"valido em:?\s*([^.|]+)", instrucoes)  # "Válido em: TECNOLOGIA." (Promobit)
    # "Produtos Garnier com 25% OFF", "itens Samsung": a marca restringe o cupom.
    trechos += re.findall(r"\b(?:produtos|itens|linha)\s+(?:da |de |do )?([a-z][a-z0-9-]+)", t)
    escopo = []
    for trecho in trechos:
        trecho = re.split(r"\s(?:na|no|com|para|pelo|pela|via)\s|[,;()|]", trecho)[0]
        escopo += [w for w in re.findall(r"[a-z][a-z0-9-]+", trecho) if w not in ESCOPO_GERAL and w not in escopo]
    condicoes = [c.strip() for c in re.findall(r"\[([^\]]+)\]", p["titulo"])]
    if "cashback" in t:
        condicoes.append("cashback")
    valor_txt = f"{reais(fixo).replace(',00', '')} OFF" if fixo else f"{pct:.0f}% OFF"
    regras_txt = " · ".join(x for x in (
        f"acima de {reais(minimo).replace(',00', '')}" if minimo and minimo > 1
        else "sem mínimo" if minimo is not None else "mínimo não informado",
        f"até {reais(limite).replace(',00', '')}" if limite else "",
        f"só em {' '.join(escopo)}" if escopo else "",
    ) if x)
    # O mesmo cupom costuma ser postado várias vezes no dia, por pessoas diferentes.
    chave = "|".join(str(x) for x in (normalizar(p["loja"]), pct, fixo, minimo, limite, " ".join(escopo)))
    # Sem mínimo, sem limite e sem categoria conhecidos ("Economize 10% aplicando cupom Amazon"), dizer que
    # serve num celular de R$ 2.299 seria chute: o cupom vai para a aba Cupons, mas não conta como "serve".
    vago = minimo is None and limite is None and not escopo
    return {**p, "pct": pct, "fixo": fixo, "minimo": minimo, "limite": limite, "escopo": escopo,
            "condicoes": condicoes, "valor_txt": valor_txt, "regras_txt": regras_txt, "chave": chave, "vago": vago}


def onde_serve(c, regras):
    """Itens em que o cupom serve e o desconto que ele daria no preço normal (ou no alvo) de cada um."""
    servidos = []
    if c["vago"]:
        return servidos
    for r in regras:
        if r.get("voo"):
            continue
        base, base_tipo = ((r["preco_referencia"], "preço normal") if r.get("preco_referencia")
                           else (r.get("preco_max"), "alvo"))
        if not base or base < (c["minimo"] or 0):
            continue
        texto = normalizar(" ".join([r["grupo"], r["nome"], *r.get("precisa", []), *r.get("qualquer", [])]))
        if c["escopo"] and not any(
                re.search(rf"\b{re.escape(w)}\b", texto) or any(x in texto for x in CATEGORIAS.get(w, ()))
                for w in c["escopo"]):
            continue
        valor = c["fixo"] or base * c["pct"] / 100
        if c["limite"]:
            valor = min(valor, c["limite"])
        if valor < base * CUPOM_MIN_PCT / 100:
            continue
        servidos.append({"regra": r, "valor": round(valor, 2), "base": base, "base_tipo": base_tipo})
    return servidos


def cupons_ativos(todas, ativas, regras):
    """[(cupom, itens em que serve)] de todos os posts de cupom ativos: os que servem primeiro (maior
    desconto no item), depois os mais votados. Os que não servem em nada vão só para a aba Cupons do site.
    Post de cupom que já bateu numa regra comum (como "Renner: cupons e promoções") já avisa como
    promoção: entra na lista, mas sem itens, para não avisar duas vezes."""
    ja = {p["id"] for _, p in ativas}
    achados = []
    for p in todas.values():
        if p.get("tipo") != "coupon" or p["status"] != "active":
            continue
        c = ler_cupom(p)
        if c:
            achados.append((c, [] if p["id"] in ja else onde_serve(c, regras)))
    achados.sort(key=lambda x: (-max((s["valor"] for s in x[1]), default=0), -x[0]["temperatura"]))
    vistos, unicos = set(), []
    for c, s in achados:  # do mesmo cupom postado várias vezes, fica o post mais votado
        if c["chave"] not in vistos:
            vistos.add(c["chave"])
            unicos.append((c, s))
    return unicos


def codigos_dos_cupons(cupons, guardados, maximo=10):
    """Guarda no estado.json cada cupom visto (para o aviso sair uma vez só) e o código dele. O código só
    aparece na página do post: cada cupom é aberto uma vez, no máximo `maximo` páginas por rodada (os que
    servem vêm primeiro na lista); o resto fica para a próxima."""
    abertos = 0
    for c, _ in cupons:
        g = guardados.setdefault(c["id"], {"em": agora().isoformat(timespec="minutes"), "chave": c["chave"]})
        if c.get("fonte") == "promobit":  # o Promobit já manda o código junto
            g["cupom"] = c.get("codigo")
            continue
        if "cupom" in g or abertos >= maximo:
            continue
        if abertos:
            time.sleep(1)  # educação com o Pelando
        g["cupom"] = cupom(c["link"])
        abertos += 1
    return {k: v.get("cupom") for k, v in guardados.items()}


def servidos_txt(servidos, limite=3):
    nomes = [f"{s['regra']['nome']} (-{reais(s['valor']).replace(',00', '')})" for s in servidos[:limite]]
    return ", ".join(nomes) + (f" e mais {len(servidos) - limite}" if len(servidos) > limite else "")


# ---------------------------------------------------------------- passagens aéreas

def passagens(regras, estado, forcar=False):
    """Preço das regras com bloco "voo", lido no Google Flights (voos.py).

    Passagem não muda de preço de meia em meia hora, e cada trecho é uma página de alguns MB: cada
    regra só é relida depois do seu "intervalo_h". No meio disso o último preço fica guardado no
    estado.json e continua valendo, para a passagem não sumir do painel entre duas leituras.
    """
    guardados = estado.setdefault("voos", {})
    achadas = []
    for r in regras:
        chave = r.get("id") or r["nome"]
        guardado = guardados.get(chave)
        horas = r["voo"].get("intervalo_h", 4)
        novo = forcar or not guardado or agora() - datetime.fromisoformat(guardado["em"]) >= timedelta(hours=horas)
        if novo:
            lidas = voos.ofertas(r, log)
            if lidas:  # se todos os trechos falharem, segue com o preço anterior e tenta de novo depois
                guardado = {"em": agora().isoformat(timespec="minutes"), "ofertas": lidas}
                guardados[chave] = guardado
        if guardado:
            achadas += [(r, o) for o in guardado["ofertas"]]
    return achadas


# ---------------------------------------------------------------- servidor (painel web)

def servidor():
    s = ler_json(SERVIDOR, None)
    return s if s and s.get("url") and s.get("token") else None


def api(metodo, caminho, corpo=None):
    s = servidor()
    req = urllib.request.Request(
        s["url"].rstrip("/") + caminho,
        method=metodo,
        data=json.dumps(corpo).encode("utf-8") if corpo is not None else None,
        headers={"Authorization": "Bearer " + s["token"], "Content-Type": "application/json", "User-Agent": "PromoTrix-coletor"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def obter_config():
    """Servidor → cópia local (config-cache.json) → config.json, nessa ordem. Com --local, só o config.json."""
    if servidor() and "--local" not in sys.argv:
        try:
            config = api("GET", "/api/coletor/config")
            CONFIG_CACHE.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
            return config, "servidor"
        except Exception as e:
            log(f"servidor fora ao buscar regras ({e}); usando a última cópia")
            if CONFIG_CACHE.exists():
                return ler_json(CONFIG_CACHE, {}), "cópia local"
    if not CONFIG.exists():
        sys.exit("Falta o config.json. Copie o config.example.json para config.json e ajuste as regras.")
    return ler_json(CONFIG, {}), "config.json"


def cupom_para_servidor(c, servidos, codigo):
    return {
        "id": c["id"], "titulo": c["titulo"], "loja": c["loja"], "link": c["link"], "criada": c["criada"],
        "temperatura": c["temperatura"], "codigo": codigo, "porcentagem": c["pct"], "valor_fixo": c["fixo"],
        "minimo": c["minimo"], "limite": c["limite"], "condicoes": c["condicoes"], "escopo": c["escopo"],
        "valor_txt": c["valor_txt"], "regras_txt": c["regras_txt"],
        "servem": [{"regra_id": s["regra"].get("id"), "regra_nome": s["regra"]["nome"],
                    "prioridade": s["regra"].get("prioridade", "normal"), "valor": s["valor"],
                    "base": s["base"], "base_tipo": s["base_tipo"]} for s in servidos],
    }


def enviar_coleta(lidas, ativas, novos_ids, cupons, lista_cupons=(), codigos=None, cupons_novos=()):
    if not servidor():
        return
    dentro = []
    for r, p in ativas:
        pct, origem = origem_preco(p, r)
        dentro.append({
            "id": p["id"], "titulo": p["titulo"], "preco": p["preco"], "loja": p["loja"],
            "temperatura": p["temperatura"], "criada": p["criada"], "link": p["link"],
            "regra_id": r.get("id"), "regra_nome": r["nome"], "cupom": cupons.get(p["id"]),
            "imagem": p.get("imagem"), "desconto": pct, "desconto_origem": origem,
        })
    try:
        resposta = api("POST", "/api/coletor/coleta", {
            "lidas": lidas, "dentro": dentro, "novos": novos_ids,
            "cupons": [cupom_para_servidor(c, s, (codigos or {}).get(c["id"])) for c, s in lista_cupons],
            "cupons_novos": list(cupons_novos),
        })
        log(f"servidor: coleta enviada ({len(dentro)} dentro, {len(novos_ids)} novas, {len(lista_cupons)} cupons, "
            f"{resposta.get('pushes', 0)} push)")
    except Exception as e:
        log(f"servidor fora ao enviar a coleta: {e}")


# ---------------------------------------------------------------- regras

def bate(p, r):
    """precisa/qualquer olham título + loja; nao_pode olha só o título."""
    alvo = normalizar(p["titulo"] + " " + p["loja"])
    titulo = normalizar(p["titulo"])
    if not all(normalizar(t) in alvo for t in r.get("precisa", [])):
        return False
    if r.get("qualquer") and not any(normalizar(t) in alvo for t in r["qualquer"]):
        return False
    if any(normalizar(t) in titulo for t in r.get("nao_pode", [])):
        return False
    preco = p["preco"]
    if "preco_max" in r and (preco is None or preco > r["preco_max"]):
        return False
    if "preco_min" in r and (preco is None or preco < r["preco_min"]):
        return False
    if "desconto_min" in r and (desconto(p, r)[0] or 0) < r["desconto_min"]:
        return False
    return p["temperatura"] >= r.get("temperatura_min", float("-inf"))


def descrever_alvo(r):
    partes = []
    if r.get("voo"):
        v = r["voo"]
        partes.append("+".join(v["origens"]) + " → " + ", ".join(v["destinos"]))
        partes.append(" ou ".join(f"{d[8:10]}/{d[5:7]}" for d in v["datas"]))
        if v.get("max_paradas") is not None:
            partes.append("direto" if not v["max_paradas"] else f"até {v['max_paradas']} parada(s)")
    if "preco_max" in r:
        partes.append("até " + reais(r["preco_max"]))
    if "desconto_min" in r:
        partes.append(f"com {r['desconto_min']:.0f}% ou mais de desconto")
    if "temperatura_min" in r:
        partes.append(f"a partir de {r['temperatura_min']:.0f}° no Pelando")
    if r.get("ate"):
        partes.append(f"até {r['ate'][8:10]}/{r['ate'][5:7]}")
    return " · ".join(partes) or "qualquer preço"


# ---------------------------------------------------------------- avisos

def notificar(titulo, linhas, link, som=True):
    esc = lambda s: html.escape(s, quote=True)
    audio = '<audio src="ms-winsoundevent:Notification.Reminder"/>' if som else '<audio silent="true"/>'
    xml = (f'<toast activationType="protocol" launch="{esc(link)}" duration="long">'
           f'<visual><binding template="ToastGeneric"><text>{esc(titulo)}</text>'
           + "".join(f"<text>{esc(l)}</text>" for l in linhas)
           + f"</binding></visual>{audio}</toast>")
    b64 = base64.b64encode(xml.encode("utf-8")).decode()
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$x.LoadXml([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')));"
        "$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show("
        "(New-Object Windows.UI.Notifications.ToastNotification $x))"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                   creationflags=SEM_JANELA, timeout=30, check=False)


def abrir_alerta(itens, teste=False, modo="promo"):
    """Abre o aviso (alerta.py) num processo separado, que fica aberto depois que a tarefa termina.
    modo "promo": a janela grande com alarme. modo "cupom": o cartão discreto no canto da tela."""
    arquivo = PASTA / f"alerta-{datetime.now():%Y%m%d%H%M%S%f}.json"
    arquivo.write_text(json.dumps({"promos": itens, "painel": PAINEL.as_uri(), "modo": modo},
                                  ensure_ascii=False), encoding="utf-8")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    cmd = [str(pythonw if pythonw.exists() else sys.executable), str(PASTA / "alerta.py"), str(arquivo)]
    if teste:
        cmd.append("--teste")
    soltos = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:  # sai do "job" do Agendador para a janela não morrer junto com a tarefa
        subprocess.Popen(cmd, creationflags=soltos | 0x01000000, close_fds=True)
    except OSError:
        subprocess.Popen(cmd, creationflags=soltos, close_fds=True)


# ---------------------------------------------------------------- painel

CSS = """
:root{--fundo:#f4f5f7;--cartao:#fff;--texto:#111827;--suave:#6b7280;--borda:#e5e7eb;--preco:#047857;--destaque:#ffe600;--novo:#dc2626}
@media (prefers-color-scheme:dark){:root{--fundo:#0f1115;--cartao:#1a1d24;--texto:#f3f4f6;--suave:#9ca3af;--borda:#2a2f3a;--preco:#34d399;--novo:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--texto);font:15px/1.45 "Segoe UI",system-ui,sans-serif}
header{background:var(--destaque);color:#111827;padding:18px 24px}header h1{margin:0;font-size:26px}header p{margin:4px 0 0}
main{max-width:1100px;margin:0 auto;padding:16px}
section{margin:22px 0}h2{font-size:20px;margin:0 0 8px}
.regras{color:var(--suave);font-size:13px;margin:0 0 10px}.regras b{color:var(--texto);font-weight:600}
.grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.cartao{background:var(--cartao);border:1px solid var(--borda);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:6px}
.preco{font-size:26px;font-weight:700;color:var(--preco)}.titulo{font-weight:600}
.meta{color:var(--suave);font-size:13px}.cupom{font-family:Consolas,monospace;background:var(--destaque);color:#111827;padding:1px 6px;border-radius:4px}
.novo{color:var(--novo);font-weight:700;font-size:12px;text-transform:uppercase}
.foto{position:relative;background:#fff;border-radius:8px;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;overflow:hidden}
.foto img{max-width:100%;max-height:100%;object-fit:contain}
.off{position:absolute;top:8px;left:8px;background:var(--preco);color:#fff;font-weight:700;font-size:13px;padding:2px 8px;border-radius:999px}
a.botao{margin-top:auto;align-self:flex-start;background:var(--preco);color:#fff;text-decoration:none;padding:6px 12px;border-radius:6px;font-weight:600}
.vazio{color:var(--suave);font-style:italic}
.outros{margin:0;padding-left:18px;color:var(--suave);font-size:14px}.outros a{color:var(--texto)}
"""


def fonte_txt(p):
    return "Promobit" if p.get("fonte") == "promobit" else "Pelando"


def painel_cupons(cupons, codigos):
    """Seção do topo do painel: cupons que servem nos itens (cartões) e os outros mais votados (lista)."""
    esc = html.escape
    servem = [(c, s) for c, s in cupons if s]
    outros = sorted([c for c, s in cupons if not s], key=lambda c: -c["temperatura"])[:12]
    if not servem and not outros:
        return ""
    cartoes = []
    for c, s in servem:
        cod = codigos.get(c["id"])
        cartoes.append(
            '<div class="cartao">'
            f'<span class="preco">{esc(c["valor_txt"])}</span>'
            f'<span class="titulo">{esc(c["titulo"])}</span>'
            f'<span class="meta">{esc(c["loja"])} · {esc(c["regras_txt"])}'
            + (f' · {esc(", ".join(c["condicoes"]))}' if c["condicoes"] else "") + "</span>"
            + f'<span class="meta">Pode servir em: {esc(servidos_txt(s, 6))}</span>'
            + (f'<span class="meta">Cupom <span class="cupom">{esc(cod)}</span></span>' if cod else "")
            + f'<a class="botao" href="{esc(c["link"])}" target="_blank">Ver no {fonte_txt(c)}</a></div>')
    corpo = ('<div class="grade">' + "".join(cartoes) + "</div>" if cartoes
             else '<p class="vazio">Nenhum cupom ativo serve nos seus itens agora.</p>')
    if outros:
        corpo += ('<p class="regras">Outros cupons ativos, os mais votados:</p><ul class="outros">'
                  + "".join(f'<li><a href="{esc(c["link"])}" target="_blank">{esc(c["valor_txt"])}</a> · '
                            f'{esc(c["loja"])} · {esc(c["regras_txt"])}' + (f' · <span class="cupom">{esc(codigos[c["id"]])}</span>'
                            if codigos.get(c["id"]) else "") + "</li>" for c in outros) + "</ul>")
    return ('<section><h2>Cupons que servem nos seus itens</h2><p class="regras">O desconto é calculado no '
            'preço normal do item (ou no alvo). Confira no carrinho: muitos cupons valem só para itens '
            f'selecionados.</p>{corpo}</section>')


def gerar_painel(config, ativas, avisados, regras, cupons=(), codigos=None):
    esc = html.escape
    momento = agora()
    grupos = []
    for r in regras:
        if r["grupo"] not in grupos:
            grupos.append(r["grupo"])
    partes = []
    for g in grupos:
        regras_g = [r for r in regras if r["grupo"] == g]
        itens = sorted([(r, p) for r, p in ativas if r["grupo"] == g], key=lambda x: x[1]["preco"] or 0)
        resumo = " · ".join(f"<b>{esc(r['nome'])}</b> {esc(descrever_alvo(r))}" for r in regras_g)
        cartoes = []
        for r, p in itens:
            aviso = avisados.get(p["id"], {})
            em = aviso.get("em")
            novo = em and momento - datetime.fromisoformat(em) < timedelta(hours=24)
            cod = aviso.get("cupom")
            quando = datetime.fromisoformat(p["criada"].replace("Z", "+00:00")).astimezone(BRT) if p["criada"] else None
            pct, origem = origem_preco(p, r)
            # Com foto, o -% vira selo em cima dela. Passagem não tem foto: aí o -% e a explicação
            # (inclusive o que o Google diz do trecho) viram uma linha de texto.
            foto = ""
            if p.get("imagem"):
                selo = f'<span class="off" title="{esc(origem)}">-{pct:.0f}%</span>' if pct else ""
                foto = f'<div class="foto">{selo}<img src="{esc(p["imagem"])}" alt="" loading="lazy"></div>'
                linha = ""
            else:
                linha = " · ".join(x for x in (f"-{pct:.0f}%" if pct else "", origem) if x)
            cartoes.append(
                '<div class="cartao">' + foto
                + ('<span class="novo">novo</span>' if novo else "")
                + f'<span class="preco">{esc(reais(p["preco"]))}</span>'
                + f'<span class="titulo">{esc(p["titulo"])}</span>'
                + f'<span class="meta">{esc(p["loja"])} · {esc(r["nome"])}'
                + (f" · postada {quando:%d/%m %H:%M}" if quando else "")
                + (f' · {p["temperatura"]:.0f}°' if p["temperatura"] else "") + "</span>"
                + (f'<span class="meta">{esc(linha)}</span>' if linha else "")
                + (f'<span class="meta">Cupom <span class="cupom">{esc(cod)}</span></span>' if cod else "")
                + f'<a class="botao" href="{esc(p["link"])}" target="_blank">'
                + ("Ver no Google Flights" if r.get("voo") else f"Ver no {fonte_txt(p)}") + "</a></div>")
        corpo = '<div class="grade">' + "".join(cartoes) + "</div>" if cartoes else '<p class="vazio">Nada ativo dentro do alvo agora.</p>'
        partes.append(f'<section><h2>{esc(g)}</h2><p class="regras">{resumo}</p>{corpo}</section>')
    PAINEL.write_text(
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>PromoTrix</title>'
        f"<style>{CSS}</style></head><body><header><h1>PromoTrix</h1>"
        f"<p>Promoções ativas no Pelando dentro dos seus alvos · atualizado em {momento:%d/%m/%Y %H:%M}</p></header>"
        f'<main>{painel_cupons(cupons, codigos or {})}{"".join(partes)}</main></body></html>', encoding="utf-8")


# ---------------------------------------------------------------- principal

def main():
    args = sys.argv[1:]
    if "--teste" in args:
        abrir_alerta([{"regra": "Galaxy A57 256GB", "preco_txt": "R$ 1.889,00", "loja": "Mercado Livre",
                       "titulo": "Celular Samsung Galaxy A57 5G 256GB, 8GB RAM (exemplo)",
                       "cupom": "EXEMPLO10", "link": "https://www.pelando.com.br/"}], teste=True)
        return
    if "--teste-cupom" in args:
        abrir_alerta([{"regra": "Pode servir em: Galaxy A57 256GB (-R$ 300)", "preco_txt": "R$ 300 OFF",
                       "loja": "Mercado Livre", "titulo": "Cupom Mercado Livre oferece R$ 300 OFF em R$ 1999 (exemplo)",
                       "cupom": "EXEMPLO300", "link": "https://www.pelando.com.br/", "eh_cupom": True,
                       "desconto_txt": "acima de R$ 1.999 · confira no carrinho se o item aceita"}],
                     teste=True, modo="cupom")
        return
    if "--voos" in args:  # inspeção: lê todos os trechos agora, sem o intervalo e sem gravar nada
        config, _ = obter_config()
        hoje = agora().strftime("%Y-%m-%d")
        for r in [r for r in config["regras"] if r.get("voo") and vigente(r, hoje)]:
            v = r["voo"]
            print(f"\n{r['grupo']} · {r['nome']} · {descrever_alvo(r)}")
            print(f"  {'+'.join(v['origens'])} → {', '.join(v['destinos'])} em {', '.join(v['datas'])}")
            for o in voos.ofertas(r, log=lambda m: print("  !", m)):
                pct = desconto(o, r)[0]
                print(f"  {reais(o['preco']):>12} {(f'-{pct:.0f}%' if pct else ''):>5} {o['loja'][:12]:12} "
                      f"{o['titulo']:58} {o['opcoes']:2} voos · {o['tendencia'] or '?'}"
                      + ("" if bate(o, r) else "  — fora do alvo"))
        return
    if "--enviar-config" in args:
        if not servidor():
            sys.exit("Falta o servidor.json (veja servidor.example.json).")
        sufixo = "?substituir=1" if "--substituir" in args else ""
        try:
            print(api("PUT", "/api/coletor/config" + sufixo, ler_json(CONFIG, {})))
        except urllib.error.HTTPError as e:
            sys.exit(f"O servidor recusou ({e.code}): {e.read().decode('utf-8', 'replace')}")
        return

    config, origem = obter_config()
    estado = ler_json(ESTADO, {})
    avisados = estado.setdefault("avisados", {})
    for k, v in list(avisados.items()):  # formato antigo do monitor: {id: preço}
        if not isinstance(v, dict):
            avisados[k] = {"preco": v, "em": agora().isoformat(timespec="minutes"), "cupom": None}

    hoje = agora().strftime("%Y-%m-%d")
    buscas = [b for b in config["buscas"] if vigente(b, hoje)]
    regras = [r for r in config["regras"] if vigente(r, hoje)]
    # Regra de passagem não tem termo nenhum, então casaria com qualquer promoção do Pelando dentro do
    # preço: ela fica fora do casamento do Pelando e é lida só pelo voos.py.
    regras_voo = [r for r in regras if r.get("voo")]
    regras_pelando = [r for r in regras if not r.get("voo")]

    todas, falhas, falhas_promobit = {}, 0, []
    for i, b in enumerate(buscas):
        if i:
            time.sleep(config.get("pausa_entre_buscas_s", 1.5))  # educação com o Pelando e o Promobit
        try:
            todas.update(promocoes(b["termo"]))
        except Exception as e:
            falhas += 1
            log(f"falha na busca '{b['termo']}': {e}")
        try:
            todas.update(promobit(b["termo"]))
        except Exception as e:
            falhas_promobit.append(f"{b['termo']}: {e}")
    if falhas_promobit:  # uma linha só: com o Promobit fora, seriam 16 linhas por rodada
        log(f"promobit: {len(falhas_promobit)} de {len(buscas)} buscas falharam ({falhas_promobit[0]})")
    if buscas and falhas == len(buscas) and len(falhas_promobit) == len(buscas):
        log("nenhuma busca funcionou (sem internet?)")
        return
    lidas = {f: sum(1 for p in todas.values() if p.get("fonte") == f) for f in ("pelando", "promobit")}
    if not lidas["pelando"] and falhas < len(buscas):
        log("nenhuma promoção lida no Pelando: o formato do site pode ter mudado")
        if estado.get("erro_avisado_em") != hoje:
            notificar("PromoTrix parou de ler o Pelando",
                      ["O site mudou e não achei nenhuma promoção.", "Veja o README: 'Se parar de funcionar'."],
                      "https://www.pelando.com.br/")
            estado["erro_avisado_em"] = hoje
            ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    if not todas:
        return

    ativas = []
    for p in todas.values():
        if p["status"] != "active":
            continue
        regra = next((r for r in regras_pelando if bate(p, r)), None)
        if regra:
            ativas.append((regra, p))
    ativas = sem_repetir_fontes(ativas)
    # Passagem entra no painel mesmo cara, para o site acompanhar o preço subir e descer. O alvo da
    # regra decide só o aviso, mais abaixo.
    ativas += passagens(regras_voo, estado)
    lista_cupons = cupons_ativos(todas, ativas, regras_pelando)

    if "--cupons" in args:
        for c, s in lista_cupons:
            print(f"{c['valor_txt']:>12}  {c['loja'][:14]:14} {c['temperatura']:5.0f}°  {c['regras_txt'][:44]:44} "
                  f"{c['titulo'][:70]}")
            if s:
                print(f"{'':14}serve em: {servidos_txt(s, 10)}")
        print(f"{len(lista_cupons)} cupons ativos, {sum(1 for _, s in lista_cupons if s)} servem nos itens "
              f"(regras: {origem})")
        return

    if "--listar" in args:
        for r, p in sorted(ativas, key=lambda x: (x[0]["grupo"], x[1]["preco"] or 0)):
            ja = "  (já avisada)" if p["id"] in avisados else ""
            pct_ = desconto(p, r)[0]
            print(f"[{r['prioridade']:6}] {r['grupo'][:14]:14} {r['nome'][:26]:26} {reais(p['preco']):>12} "
                  f"{(f'-{pct_:.0f}%' if pct_ else ''):>5} {p['temperatura']:5.0f}°  {p["loja"][:13]:13} {fonte_txt(p)[:8]:8} {p["titulo"][:50]}{ja}")
        print(f"{len(todas)} promoções lidas, {len(ativas)} dentro das regras (regras: {origem})")
        return

    # Fonte nova (o Promobit, na primeira rodada dele): o que já está ativo lá só é guardado, sem aviso,
    # para não tocar alarme por oferta de dias atrás.
    fontes = estado.setdefault("fontes", {})
    silenciar = {"promobit"} - set(fontes)

    alta, normal, novos_ids = [], [], []
    for r, p in sorted(ativas, key=lambda x: x[1]["preco"] or 0):
        if r.get("voo") and not bate(p, r):
            continue  # passagem acima do alvo: fica no painel e no histórico, mas não avisa
        ja = avisados.get(p["id"])
        if ja and (p["preco"] is None or ja.get("preco") is None or p["preco"] >= ja["preco"]):
            continue
        if p.get("fonte") == "promobit":
            cod = p.get("codigo")  # o Promobit já manda o cupom junto
        else:
            cod = cupom(p["link"]) if not r.get("voo") else None  # passagem não tem cupom no Pelando
        avisados[p["id"]] = {"preco": p["preco"], "em": agora().isoformat(timespec="minutes"), "cupom": cod,
                             "regra": r["nome"], "loja": normalizar(p["loja"])}
        if p.get("fonte") in silenciar or avisada_em_outra_fonte(p, r, avisados):
            continue
        pct_, de_onde = origem_preco(p, r)
        item = {"regra": r["nome"], "preco_txt": reais(p["preco"]), "loja": p["loja"],
                "titulo": p["titulo"], "cupom": cod, "link": p["link"],
                "desconto_txt": f"-{pct_:.0f}% · {de_onde}" if pct_ else de_onde,
                "temperatura": p["temperatura"]}
        (alta if r.get("prioridade") == "alta" else normal).append(item)
        novos_ids.append(p["id"])
        log(f"AVISO [{r.get('prioridade', 'normal')}] {r['nome']} {reais(p['preco'])} {p['loja']} "
            f"{p['titulo'][:70]} cupom={cod} {p['link']}")

    # Cupom que serve num item avisa uma vez, com a prioridade mais alta entre os itens, e não avisa de
    # novo se o mesmo cupom for repostado. Na primeira rodada com cupons (estado.json sem "cupons"), o
    # que já está ativo só é guardado, sem aviso, para não tocar alarme por cupom de dias atrás.
    primeira_vez = "cupons" not in estado
    guardados = estado.setdefault("cupons", {})
    codigos = codigos_dos_cupons(lista_cupons, guardados)
    cupons_novos = []
    for c, s in lista_cupons:
        g = guardados[c["id"]]
        if not s or g.get("avisado"):
            continue
        g["avisado"] = True
        repetido = any(o is not g and o.get("avisado") and o.get("chave") == c["chave"]
                       and agora() - datetime.fromisoformat(o["em"]) < timedelta(days=CUPOM_REPETIDO_DIAS)
                       for o in guardados.values())
        antigo = not _recente(_data(c.get("criada")), CUPOM_AVISO_DIAS)
        if primeira_vez or repetido or antigo or c.get("fonte") in silenciar:
            continue
        importante = any(x["regra"].get("prioridade") == "alta" for x in s)
        item = {"regra": "Pode servir em: " + servidos_txt(s), "preco_txt": c["valor_txt"],
                "loja": c["loja"], "titulo": c["titulo"], "cupom": g.get("cupom"), "link": c["link"],
                "desconto_txt": " · ".join([c["regras_txt"], *c["condicoes"], "confira no carrinho se o item aceita"]),
                "temperatura": c["temperatura"], "eh_cupom": True, "botao": "Abrir cupom"}
        (alta if importante else normal).append(item)
        cupons_novos.append(c["id"])
        log(f"AVISO CUPOM [{'alta' if importante else 'normal'}] {c['valor_txt']} {c['loja']} {c['regras_txt']} "
            f"serve em {servidos_txt(s, 10)} cupom={g.get('cupom')} {c['link']}")

    gerar_painel(config, ativas, avisados, regras, lista_cupons, codigos)
    # Promoção importante: janela grande com alarme. Cupom importante: cartão discreto no canto, para
    # não se confundir com produto.
    if [i for i in alta if not i.get("eh_cupom")]:
        abrir_alerta([i for i in alta if not i.get("eh_cupom")])
    if [i for i in alta if i.get("eh_cupom")]:
        abrir_alerta([i for i in alta if i.get("eh_cupom")], modo="cupom")
    if alta or normal:
        n_cupons = sum(1 for i in alta + normal if i.get("eh_cupom"))
        n_promos = len(alta) + len(normal) - n_cupons
        resumo = " e ".join(x for x in (f"{n_promos} promoção(ões) nova(s)" if n_promos else "",
                                        f"{n_cupons} cupom(ns) novo(s)" if n_cupons else "") if x)
        resumo += f", {len(alta)} importante(s)" if alta else ""
        notificar("PromoTrix: " + resumo,
                  [f"{i['regra']}: {i['preco_txt']}" for i in (alta + normal)[:2]] + ["Clique para abrir o painel"],
                  PAINEL.as_uri(), som=False)

    limite = agora() - timedelta(days=DIAS_GUARDANDO_AVISOS)
    for guardado in (avisados, guardados):
        for k in [k for k, v in guardado.items() if datetime.fromisoformat(v["em"]) < limite]:
            del guardado[k]
    for f in silenciar:  # só conta como vista a fonte que respondeu nesta rodada
        if lidas[f]:
            fontes[f] = agora().isoformat(timespec="minutes")
            log(f"{f}: primeira leitura, {lidas[f]} itens guardados sem aviso")
    estado["ultima_execucao"] = agora().isoformat(timespec="minutes")
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"ok: {len(todas)} promoções lidas ({lidas['pelando']} Pelando + {lidas['promobit']} Promobit),"
        f" {len(ativas)} dentro das regras, {len(alta)} alta + {len(normal)} normal,"
        f" {len(lista_cupons)} cupons ({sum(1 for _, s in lista_cupons if s)} servem) (regras: {origem})")
    enviar_coleta(len(todas), ativas, novos_ids, {k: v.get("cupom") for k, v in avisados.items() if v.get("cupom")},
                  lista_cupons, codigos, cupons_novos)

    if "--painel" in args:
        webbrowser.open(PAINEL.as_uri())


if __name__ == "__main__":
    if sys.stdout:  # console do Windows em cp1252: uma seta "→" num título derrubava o --listar
        sys.stdout.reconfigure(errors="replace")
    RODANDO.write_text(str(os.getpid()), encoding="utf-8")
    try:
        main()
    except Exception:  # pythonw não tem console: sem isto, o erro some calado
        import traceback
        log("ERRO " + " | ".join(traceback.format_exc().splitlines()))
        raise
    finally:
        RODANDO.unlink(missing_ok=True)
