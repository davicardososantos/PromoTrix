"""PromoTrix: caçador de promoções que lê o Pelando e avisa na tela.

O Pelando (pelando.com.br) junta promoções de Mercado Livre, Amazon, Shopee, Magalu e outras lojas,
com o cupom, poucos minutos depois de elas aparecerem. O PromoTrix lê as buscas de config.json,
confere cada promoção ATIVA com as regras e:
  - prioridade "alta": abre uma janela grande no meio da tela, com som (alerta.py);
  - prioridade "normal": entra no painel, com uma notificação discreta do Windows;
  - sempre: refaz o painel.html com tudo o que está valendo agora, separado por grupo.
Cada promoção avisa uma vez. Só avisa de novo se o preço dela cair.

Com o painel web (pasta ../web) ligado, crie o servidor.json (veja servidor.example.json). Aí:
  - as buscas e regras vêm do servidor, onde dá pra editar pelo celular. A última cópia fica em
    config-cache.json, e o coletor segue funcionando se o servidor estiver fora;
  - cada execução manda para o servidor o que encontrou. Lá vira histórico e notificação no celular.
Sem servidor.json, tudo funciona só no PC, com o config.json.

Uso:
  python promotrix.py                              checa e avisa (o que a tarefa agendada faz)
  python promotrix.py --listar                     mostra o que bate nas regras agora, sem avisar nem gravar
  python promotrix.py --painel                     refaz o painel e abre no navegador
  python promotrix.py --teste                      abre a janela de alerta com um exemplo
  python promotrix.py --enviar-config [--substituir]  manda o config.json local para o servidor
"""
import base64
import html
import json
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

PASTA = Path(__file__).resolve().parent
CONFIG = PASTA / "config.json"
CONFIG_CACHE = PASTA / "config-cache.json"
SERVIDOR = PASTA / "servidor.json"
ESTADO = PASTA / "estado.json"
LOG = PASTA / "promotrix.log"
PAINEL = PASTA / "painel.html"
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
        achadas[id_] = {
            "id": id_,
            "titulo": titulo.strip(),
            "preco": float(preco) if preco else None,
            "status": campo(t, "status"),
            "criada": campo(t, "createdAt"),
            "loja": loja.group(1) if loja else "?",
            "temperatura": float(temperatura) if temperatura else 0.0,
            "link": "https://www.pelando.com.br/d/" + slug,
        }
    return achadas


def cupom(link):
    try:
        m = re.search(r'data-code="([^"]+)"', baixar(link))
        return m.group(1) if m else None
    except Exception:
        return None


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
    """Servidor → cópia local (config-cache.json) → config.json, nessa ordem."""
    if servidor():
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


def enviar_coleta(lidas, ativas, novos_ids, cupons):
    if not servidor():
        return
    dentro = [{
        "id": p["id"], "titulo": p["titulo"], "preco": p["preco"], "loja": p["loja"],
        "temperatura": p["temperatura"], "criada": p["criada"], "link": p["link"],
        "regra_id": r.get("id"), "regra_nome": r["nome"], "cupom": cupons.get(p["id"]),
    } for r, p in ativas]
    try:
        resposta = api("POST", "/api/coletor/coleta", {"lidas": lidas, "dentro": dentro, "novos": novos_ids})
        log(f"servidor: coleta enviada ({len(dentro)} dentro, {len(novos_ids)} novas, {resposta.get('pushes', 0)} push)")
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
    return p["temperatura"] >= r.get("temperatura_min", float("-inf"))


def descrever_alvo(r):
    partes = []
    if "preco_max" in r:
        partes.append("até " + reais(r["preco_max"]))
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


def abrir_alerta(itens, teste=False):
    """Abre a janela grande (alerta.py) num processo separado, que fica aberto depois que a tarefa termina."""
    arquivo = PASTA / f"alerta-{datetime.now():%Y%m%d%H%M%S%f}.json"
    arquivo.write_text(json.dumps({"promos": itens, "painel": PAINEL.as_uri()}, ensure_ascii=False), encoding="utf-8")
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
a.botao{margin-top:auto;align-self:flex-start;background:var(--preco);color:#fff;text-decoration:none;padding:6px 12px;border-radius:6px;font-weight:600}
.vazio{color:var(--suave);font-style:italic}
"""


def gerar_painel(config, ativas, avisados, regras):
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
            cartoes.append(
                '<div class="cartao">'
                + ('<span class="novo">novo</span>' if novo else "")
                + f'<span class="preco">{esc(reais(p["preco"]))}</span>'
                + f'<span class="titulo">{esc(p["titulo"])}</span>'
                + f'<span class="meta">{esc(p["loja"])} · {esc(r["nome"])}'
                + (f" · postada {quando:%d/%m %H:%M}" if quando else "") + f' · {p["temperatura"]:.0f}°</span>'
                + (f'<span class="meta">Cupom <span class="cupom">{esc(cod)}</span></span>' if cod else "")
                + f'<a class="botao" href="{esc(p["link"])}" target="_blank">Ver no Pelando</a></div>')
        corpo = '<div class="grade">' + "".join(cartoes) + "</div>" if cartoes else '<p class="vazio">Nada ativo dentro do alvo agora.</p>'
        partes.append(f'<section><h2>{esc(g)}</h2><p class="regras">{resumo}</p>{corpo}</section>')
    PAINEL.write_text(
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>PromoTrix</title>'
        f"<style>{CSS}</style></head><body><header><h1>PromoTrix</h1>"
        f"<p>Promoções ativas no Pelando dentro dos seus alvos · atualizado em {momento:%d/%m/%Y %H:%M}</p></header>"
        f'<main>{"".join(partes)}</main></body></html>', encoding="utf-8")


# ---------------------------------------------------------------- principal

def main():
    args = sys.argv[1:]
    if "--teste" in args:
        abrir_alerta([{"regra": "Galaxy A57 256GB", "preco_txt": "R$ 1.889,00", "loja": "Mercado Livre",
                       "titulo": "Celular Samsung Galaxy A57 5G 256GB, 8GB RAM (exemplo)",
                       "cupom": "EXEMPLO10", "link": "https://www.pelando.com.br/"}], teste=True)
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

    todas, falhas = {}, 0
    for i, b in enumerate(buscas):
        if i:
            time.sleep(config.get("pausa_entre_buscas_s", 1.5))  # educação com o Pelando
        try:
            todas.update(promocoes(b["termo"]))
        except Exception as e:
            falhas += 1
            log(f"falha na busca '{b['termo']}': {e}")
    if buscas and falhas == len(buscas):
        log("nenhuma busca funcionou (sem internet?)")
        return
    if not todas:
        log("nenhuma promoção lida: o formato do Pelando pode ter mudado")
        if estado.get("erro_avisado_em") != hoje:
            notificar("PromoTrix parou de ler o Pelando",
                      ["O site mudou e não achei nenhuma promoção.", "Veja o README: 'Se parar de funcionar'."],
                      "https://www.pelando.com.br/")
            estado["erro_avisado_em"] = hoje
            ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        return

    ativas = []
    for p in todas.values():
        if p["status"] != "active":
            continue
        regra = next((r for r in regras if bate(p, r)), None)
        if regra:
            ativas.append((regra, p))

    if "--listar" in args:
        for r, p in sorted(ativas, key=lambda x: (x[0]["grupo"], x[1]["preco"] or 0)):
            ja = "  (já avisada)" if p["id"] in avisados else ""
            print(f"[{r['prioridade']:6}] {r['grupo'][:14]:14} {r['nome'][:26]:26} {reais(p['preco']):>12}  "
                  f"{p['loja'][:13]:13} {p['titulo'][:55]}{ja}")
        print(f"{len(todas)} promoções lidas, {len(ativas)} dentro das regras (regras: {origem})")
        return

    alta, normal, novos_ids = [], [], []
    for r, p in sorted(ativas, key=lambda x: x[1]["preco"] or 0):
        ja = avisados.get(p["id"])
        if ja and (p["preco"] is None or ja.get("preco") is None or p["preco"] >= ja["preco"]):
            continue
        cod = cupom(p["link"])
        avisados[p["id"]] = {"preco": p["preco"], "em": agora().isoformat(timespec="minutes"), "cupom": cod}
        item = {"regra": r["nome"], "preco_txt": reais(p["preco"]), "loja": p["loja"],
                "titulo": p["titulo"], "cupom": cod, "link": p["link"]}
        (alta if r.get("prioridade") == "alta" else normal).append(item)
        novos_ids.append(p["id"])
        log(f"AVISO [{r.get('prioridade', 'normal')}] {r['nome']} {reais(p['preco'])} {p['loja']} "
            f"{p['titulo'][:70]} cupom={cod} {p['link']}")

    gerar_painel(config, ativas, avisados, regras)
    if alta:
        abrir_alerta(alta)
    if alta or normal:
        resumo = f"{len(alta) + len(normal)} promoção(ões) nova(s)" + (f", {len(alta)} importante(s)" if alta else "")
        notificar("PromoTrix: " + resumo,
                  [f"{i['regra']}: {i['preco_txt']}" for i in (alta + normal)[:2]] + ["Clique para abrir o painel"],
                  PAINEL.as_uri(), som=False)

    limite = agora() - timedelta(days=DIAS_GUARDANDO_AVISOS)
    for k in [k for k, v in avisados.items() if datetime.fromisoformat(v["em"]) < limite]:
        del avisados[k]
    estado["ultima_execucao"] = agora().isoformat(timespec="minutes")
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"ok: {len(todas)} promoções lidas, {len(ativas)} dentro das regras, {len(alta)} alta + {len(normal)} normal"
        f" (regras: {origem})")
    enviar_coleta(len(todas), ativas, novos_ids, {k: v.get("cupom") for k, v in avisados.items() if v.get("cupom")})

    if "--painel" in args:
        webbrowser.open(PAINEL.as_uri())


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pythonw não tem console: sem isto, o erro some calado
        import traceback
        log("ERRO " + " | ".join(traceback.format_exc().splitlines()))
        raise
