"""Preço de passagem aérea no Google Flights, sem navegador.

O Google Flights não tem API pública, mas a página de resultados vem pronta no HTML: dá para ler o
preço mais barato de um trecho num dia direto da resposta, sem Playwright e sem login. Isso cabe no
servidor ou no PC; aqui ele roda junto com o coletor do Pelando.

A busca vai num só parâmetro, o `tfs`: um protobuf (o formato binário do Google) em base64. Não é
documentado, então o pouco que o PromoTrix usa está montado à mão em `tfs()`, com os números de campo
que o site usa. Vários aeroportos de origem cabem na mesma consulta (o campo 13 se repete), então
monitorar GRU + CGH + VCP custa **uma** requisição, não três.

Cada oferta sai no mesmo formato das promoções do Pelando (`promotrix.promocoes`), para seguir pelo
mesmo caminho: regras, janela de alerta, painel, histórico e push.
"""
import base64
import gzip
import html
import re
import urllib.request
from datetime import date

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
BUSCA = "https://www.google.com/travel/flights/search"
# Cada voo da lista é um <li class="pIav2d">, e o aria-label mais longo dele resume a oferta inteira:
# "A partir de 815 Reais brasileiros. Voo da LATAM com 1 parada. ... às 17:40 ... às 23:05 ...
#  Duração total: 5 h 25 min." Voo sem escala vem como "Voo direto da Gol."
VOO = re.compile(r'<li class="pIav2d"')
ROTULO = re.compile(r'aria-label="([^"]+)"')
PRECO = re.compile(r"A partir de ([\d.]+) Reais brasileiros")
CIA = re.compile(r"Voo (?:direto )?d[ao] (.+?)(?:\.| com \d+ parada)")
PARADAS = re.compile(r"com (\d+) parada")
HORA = re.compile(r"às (\d{1,2}:\d{2}) do dia")
DURACAO = re.compile(r"Duração total: (.+?)\.")
CODIGO = re.compile(r">([A-Z]{3})</div>")
# O Google diz se o preço do trecho está bom pelo ícone, não por texto: ic_price_low/typical/high.
TENDENCIA = re.compile(r"ic_price_(low|typical|high)_")
TENDENCIAS = {"low": "preços baixos", "typical": "preços normais", "high": "preços altos"}
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


# ---------------------------------------------------------------- o parâmetro tfs

def _varint(n):
    saida = b""
    while True:
        byte, n = n & 0x7F, n >> 7
        saida += bytes([byte | (0x80 if n else 0)])
        if not n:
            return saida


def _num(campo, valor):
    return _varint(campo << 3) + _varint(valor)


def _bytes(campo, corpo):
    return _varint((campo << 3) | 2) + _varint(len(corpo)) + corpo


def _texto(campo, valor):
    return _bytes(campo, valor.encode("utf-8"))


def _aeroporto(codigo):
    return _num(1, 1) + _texto(2, codigo)  # 1 = aeroporto (sigla IATA), não cidade


def tfs(origens, destino, data):
    """O parâmetro de busca: um trecho só de ida, em classe econômica, para um adulto."""
    trecho = _texto(2, data) + b"".join(_bytes(13, _aeroporto(o)) for o in origens) \
        + _bytes(14, _aeroporto(destino))
    info = _num(1, 28) + _num(2, 2) + _bytes(3, trecho) + _num(8, 1) + _num(9, 1) + _num(19, 2)
    return base64.urlsafe_b64encode(info).rstrip(b"=").decode()


def link(origens, destino, data):
    return f"{BUSCA}?tfs={tfs(origens, destino, data)}&hl=pt-BR&gl=BR&curr=BRL"


# ---------------------------------------------------------------- leitura

def _baixar(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=45) as r:
        dados = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        dados = gzip.decompress(dados)
    return dados.decode("utf-8", errors="replace")


def buscar(origens, destino, data):
    """Lê o trecho e devolve (voos, tendência). Cada voo: preço, cia, horários, paradas, duração."""
    pagina = _baixar(link(origens, destino, data))
    inicios = [m.start() for m in VOO.finditer(pagina)] + [len(pagina)]
    achados = {}
    for a, b in zip(inicios, inicios[1:]):
        trecho = pagina[a:b]
        rotulos = ROTULO.findall(trecho)
        if not rotulos:
            continue
        resumo = html.unescape(max(rotulos, key=len))
        preco = PRECO.search(resumo)
        if not preco:
            continue
        horas = HORA.findall(resumo)
        paradas = PARADAS.search(resumo)
        cia = CIA.search(resumo)
        duracao = DURACAO.search(resumo)
        codigos = CODIGO.findall(trecho)
        voo = {
            "preco": float(preco.group(1).replace(".", "")),
            "cia": cia.group(1).strip() if cia else "?",
            "partida": horas[0] if horas else None,
            "chegada": horas[1] if len(horas) > 1 else None,
            "paradas": int(paradas.group(1)) if paradas else 0,
            "duracao": duracao.group(1).strip() if duracao else None,
            "origem": next((c for c in codigos if c in origens), origens[0]),
            "destino": destino,
            "data": data,
        }
        # A mesma oferta aparece mais de uma vez na página (melhores voos, lista completa, resumo).
        achados[(voo["cia"], voo["origem"], voo["partida"], voo["chegada"], voo["paradas"])] = voo
    tendencia = TENDENCIA.search(pagina)
    return list(achados.values()), TENDENCIAS.get(tendencia.group(1)) if tendencia else None


# ---------------------------------------------------------------- ofertas para as regras

def _titulo(voo):
    a, m, d = (int(x) for x in voo["data"].split("-"))
    dia = DIAS[date(a, m, d).weekday()]
    partes = [f'{voo["origem"]} → {voo["destino"]}', f"{dia} {d:02d}/{m:02d}"]
    if voo["partida"] and voo["chegada"]:
        partes.append(f'{voo["partida"]}–{voo["chegada"]}')
    partes.append("direto" if not voo["paradas"] else f'{voo["paradas"]} parada'
                  + ("s" if voo["paradas"] > 1 else ""))
    if voo["duracao"]:
        partes.append(voo["duracao"])
    return " · ".join(partes)


def ofertas(regra, log=print):
    """Uma oferta por destino e data: o voo mais barato que respeita o limite de paradas da regra.

    Guardar só o mais barato de cada dia é o que faz o histórico do painel virar uma série de preços
    do trecho, e o alerta disparar quando aquele dia fica mais barato (o `id` não muda).
    """
    voo_cfg = regra["voo"]
    origens = voo_cfg["origens"]
    max_paradas = voo_cfg.get("max_paradas")
    achadas = []
    for destino in voo_cfg["destinos"]:
        for data in voo_cfg["datas"]:
            try:
                voos, tendencia = buscar(origens, destino, data)
            except Exception as e:
                log(f"falha no trecho {'+'.join(origens)}→{destino} em {data}: {e}")
                continue
            if max_paradas is not None:
                voos = [v for v in voos if v["paradas"] <= max_paradas]
            if not voos:
                log(f"nenhum voo lido em {'+'.join(origens)}→{destino} {data}"
                    f"{f' com até {max_paradas} parada(s)' if max_paradas is not None else ''}")
                continue
            voo = min(voos, key=lambda v: v["preco"])
            achadas.append({
                "id": f"voo:{'+'.join(origens)}>{destino}:{data}",
                "titulo": _titulo(voo),
                "preco": voo["preco"],
                "status": "active",
                "criada": None,
                "loja": voo["cia"],
                "temperatura": 0.0,
                "link": link(origens, destino, data),
                "imagem": None,
                "desconto_pelando": None,
                "tendencia": tendencia,
                "opcoes": len(voos),
            })
    return achadas
