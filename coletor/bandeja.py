"""Ícone do PromoTrix na bandeja do Windows (perto do relógio), para ver de relance se ele está vivo.

A tarefa agendada roda escondida, então sem isto não dá para saber se o PromoTrix está buscando, se
parou ou se deu erro. O ícone amarelo com "P" ganha uma bolinha:
  - verde: a última busca deu certo;
  - azul: buscando agora;
  - laranja: a última busca funcionou, mas com algum problema (servidor fora, um trecho de voo falhou...);
  - vermelha: erro, ou faz tempo demais que nenhuma busca termina;
  - cinza: buscas pausadas (tarefa desligada no Agendador).
Passar o mouse mostra a última busca e a próxima. Clicar abre o painel; o botão direito tem
"Buscar agora", "Ver log", "Pausar" e "Iniciar com o Windows".

Ele só lê o promotrix.log, o rodando.txt e a tarefa "PromoTrix". Quem busca continua sendo a tarefa.
Precisa do pystray (pip install pystray); o resto do coletor segue só com a biblioteca padrão.

Uso:
  pythonw bandeja.py              abre o ícone (uma cópia só; uma segunda fecha sozinha)
  python bandeja.py --instalar    põe na pasta Inicializar do Windows e abre
  python bandeja.py --remover     tira da pasta Inicializar
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

PASTA = Path(__file__).resolve().parent
LOG = PASTA / "promotrix.log"
RODANDO = PASTA / "rodando.txt"
PAINEL = PASTA / "painel.html"
SERVIDOR = PASTA / "servidor.json"
TAREFA = "PromoTrix"
ATALHO = Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup\PromoTrix (bandeja).lnk"
SEM_JANELA = 0x08000000

INTERVALO = timedelta(minutes=15)          # o mesmo da instalar-tarefa.ps1
ATRASADO = INTERVALO * 2 + timedelta(minutes=15)  # duas buscas perdidas seguidas = algo errado
BUSCA_TRAVADA = timedelta(minutes=6)       # a tarefa morre com 5 min; rodando.txt mais velho que isso sobrou

AMARELO, ESCURO = "#FFE600", "#111827"
CORES = {"ok": "#16A34A", "buscando": "#2563EB", "atencao": "#F59E0B", "erro": "#DC2626", "pausado": "#9CA3AF"}
NOMES = {"ok": "funcionando", "buscando": "buscando agora...", "atencao": "funcionando, com aviso",
         "erro": "com problema", "pausado": "pausado"}

# Linhas do log que querem dizer que a busca não funcionou. As outras que não são "ok"/"AVISO" são avisos menores.
ERRO_GRAVE = re.compile(r"^(ERRO |nenhuma busca funcionou|nenhuma promoção lida)")
LINHA = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) (.*)$")
INICIO = datetime.now()


# ---------------------------------------------------------------- o que está acontecendo

def ps(comando):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", comando],
                       capture_output=True, text=True, creationflags=SEM_JANELA, timeout=30)
    return r.stdout.strip()


def ler_tarefa():
    """Estado da tarefa no Agendador: Ready, Running ou Disabled, e quando roda de novo."""
    try:
        saida = ps(f"$t=Get-ScheduledTask '{TAREFA}' -ErrorAction Stop; $i=$t|Get-ScheduledTaskInfo;"
                   "@{estado=[string]$t.State; proxima=if($i.NextRunTime){$i.NextRunTime.ToString('s')}else{''}}"
                   "|ConvertTo-Json -Compress")
        d = json.loads(saida)
        return {"estado": d["estado"], "proxima": datetime.fromisoformat(d["proxima"]) if d["proxima"] else None}
    except Exception:
        return {"estado": "Ausente", "proxima": None}


def ler_log():
    """Última busca que terminou, os problemas dela e os avisos de hoje, lidos do fim do promotrix.log."""
    linhas = []
    if LOG.exists():
        with LOG.open("rb") as f:
            f.seek(max(0, LOG.stat().st_size - 60_000))
            texto = f.read().decode("utf-8", errors="replace")
        for l in texto.splitlines():
            m = LINHA.match(l)
            if m:
                linhas.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M"), m.group(2)))
    oks = [i for i, (_, t) in enumerate(linhas) if t.startswith("ok: ")]
    ultima, resumo = (linhas[oks[-1]][0], linhas[oks[-1]][1][4:]) if oks else (None, "")
    # A última busca é tudo depois do penúltimo "ok" (o que veio antes do último "ok" e o que veio depois).
    bloco = linhas[(oks[-2] + 1 if len(oks) > 1 else 0):]
    depois = linhas[(oks[-1] + 1 if oks else 0):]
    graves = [t for _, t in depois if ERRO_GRAVE.match(t)]
    avisos = [t for _, t in bloco if not (t.startswith(("ok: ", "AVISO ", "servidor: coleta enviada")) or ERRO_GRAVE.match(t))]
    hoje = datetime.now().date()
    promos = [t[6:] for q, t in linhas if q.date() == hoje and t.startswith("AVISO ")]
    m = re.match(r"(\d+) promoções lidas, (\d+) dentro das regras, (\d+) alta \+ (\d+) normal", resumo)
    return {"ultima": ultima, "lidas": m and int(m[1]), "no_alvo": m and int(m[2]),
            "novas": m and int(m[3]) + int(m[4]), "graves": graves, "avisos": avisos, "promos_hoje": promos,
            "mexido": LOG.stat().st_mtime if LOG.exists() else 0}


def buscando():
    return RODANDO.exists() and datetime.now() - datetime.fromtimestamp(RODANDO.stat().st_mtime) < BUSCA_TRAVADA


def situacao(tarefa, log):
    if buscando() or tarefa["estado"] == "Running":
        return "buscando"
    if tarefa["estado"] in ("Disabled", "Ausente"):
        return "pausado"
    if log["graves"]:
        return "erro"
    acordado_ha_pouco = datetime.now() - INICIO < timedelta(minutes=10)  # o PC acabou de ligar: espera a 1ª busca
    if not acordado_ha_pouco and (not log["ultima"] or datetime.now() - log["ultima"] > ATRASADO):
        return "erro"
    return "atencao" if log["avisos"] else "ok"


def ha_quanto(quando):
    if not quando:
        return "nunca"
    minutos = int((datetime.now() - quando).total_seconds() // 60)
    if minutos < 1:
        return "agora há pouco"
    if minutos < 60:
        return f"há {minutos} min"
    if quando.date() == datetime.now().date():
        return f"às {quando:%H:%M}"
    return f"em {quando:%d/%m %H:%M}"


# ---------------------------------------------------------------- desenho do ícone

def desenhar(nivel):
    t = 64
    img = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, t - 1, t - 1), radius=14, fill=AMARELO)
    try:
        fonte = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 42)
    except OSError:
        fonte = ImageFont.load_default()
    d.text((21, 26), "P", font=fonte, fill=ESCURO, anchor="mm")
    # Bolinha grande no canto: no tamanho real (16 px) é ela que se enxerga.
    d.ellipse((24, 24, t - 1, t - 1), fill="#FFFFFF")
    d.ellipse((29, 29, t - 6, t - 6), fill=CORES[nivel])
    return img


# ---------------------------------------------------------------- a bandeja

class Bandeja:
    def __init__(self):
        self.tarefa = ler_tarefa()
        self.log = ler_log()
        self.nivel = situacao(self.tarefa, self.log)
        self.pedida_em = None  # quando o Davi clicou em "Buscar agora" (para avisar quando terminar)
        self.icone = pystray.Icon("PromoTrix", desenhar(self.nivel), self.dica(), self.menu())

    # textos ------------------------------------------------------------
    def dica(self):
        l = self.log
        linhas = [f"PromoTrix · {NOMES[self.nivel]}"]
        if self.nivel != "buscando":
            linhas.append(f"Última busca {ha_quanto(l['ultima'])}"
                          + (f" · {l['no_alvo']} no alvo" if l["no_alvo"] is not None else ""))
        if self.tarefa["proxima"] and self.nivel != "pausado":
            linhas.append(f"Próxima às {self.tarefa['proxima']:%H:%M}")
        return "\n".join(linhas)[:127]  # o Windows corta a dica em 127 letras

    def linha_situacao(self, _):
        return f"Situação: {NOMES[self.nivel]}"

    def linha_ultima(self, _):
        l = self.log
        if l["lidas"] is None:
            return f"Última busca: {ha_quanto(l['ultima'])}"
        return f"Última busca {ha_quanto(l['ultima'])}: {l['lidas']} lidas, {l['no_alvo']} no alvo"

    def linha_proxima(self, _):
        if self.nivel == "pausado":
            return "Próxima busca: pausado"
        p = self.tarefa["proxima"]
        return f"Próxima busca às {p:%H:%M}" if p else "Próxima busca: ?"

    def linha_hoje(self, _):
        n = len(self.log["promos_hoje"])
        return "Nenhum aviso de promoção hoje" if not n else f"Avisos de promoção hoje: {n}"

    def linha_problema(self, _):
        p = (self.log["graves"] or self.log["avisos"] or [""])[-1]
        return ("Problema: " + p)[:90]

    def menu(self):
        Item, sep = pystray.MenuItem, pystray.Menu.SEPARATOR
        return pystray.Menu(
            Item(self.linha_situacao, None, enabled=False),
            Item(self.linha_ultima, None, enabled=False),
            Item(self.linha_proxima, None, enabled=False),
            Item(self.linha_hoje, None, enabled=False),
            Item(self.linha_problema, None, enabled=False,
                 visible=lambda _: self.nivel in ("erro", "atencao")),
            sep,
            Item("Abrir painel", self.abrir_painel, default=True),
            Item("Buscar agora", self.buscar_agora, enabled=lambda _: self.nivel != "buscando"),
            Item("Ver promoções avisadas hoje", self.ver_hoje, visible=lambda _: bool(self.log["promos_hoje"])),
            Item("Ver log", lambda: os.startfile(LOG)),
            Item("Painel do PC (offline)", lambda: webbrowser.open(PAINEL.as_uri())),
            sep,
            Item(lambda _: "Retomar buscas" if self.tarefa["estado"] == "Disabled" else "Pausar buscas",
                 self.pausar_retomar, enabled=lambda _: self.tarefa["estado"] != "Ausente"),
            Item("Iniciar com o Windows", self.alternar_atalho, checked=lambda _: ATALHO.exists()),
            Item("Fechar este ícone", self.sair),
        )

    # ações -------------------------------------------------------------
    def abrir_painel(self):
        try:
            url = json.loads(SERVIDOR.read_text(encoding="utf-8-sig"))["url"]
        except Exception:
            url = PAINEL.as_uri()
        webbrowser.open(url)

    def buscar_agora(self):
        self.pedida_em = time.time()
        if self.tarefa["estado"] == "Ready":  # pela tarefa: ela mesma impede duas buscas ao mesmo tempo
            subprocess.run(["schtasks", "/run", "/tn", TAREFA], capture_output=True, creationflags=SEM_JANELA)
        else:  # pausado: busca uma vez, sem religar a tarefa
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable), str(PASTA / "promotrix.py")],
                             cwd=PASTA, creationflags=SEM_JANELA)
        self.nivel = "buscando"
        self.atualizar_icone()

    def ver_hoje(self):
        arquivo = PASTA / "avisos-de-hoje.txt"
        arquivo.write_text("Promoções avisadas hoje pelo PromoTrix\n\n" + "\n\n".join(self.log["promos_hoje"]),
                           encoding="utf-8")
        os.startfile(arquivo)

    def pausar_retomar(self):
        acao = "/enable" if self.tarefa["estado"] == "Disabled" else "/disable"
        subprocess.run(["schtasks", "/change", "/tn", TAREFA, acao], capture_output=True, creationflags=SEM_JANELA)
        self.tarefa = ler_tarefa()
        self.recalcular()

    def alternar_atalho(self):
        if ATALHO.exists():
            ATALHO.unlink()
        else:
            criar_atalho()
        self.icone.update_menu()

    def sair(self):
        self.parar = True
        self.icone.stop()

    # laço --------------------------------------------------------------
    def atualizar_icone(self):
        self.icone.icon = desenhar(self.nivel)
        self.icone.title = self.dica()
        self.icone.update_menu()

    def recalcular(self):
        antes = self.nivel
        self.log = ler_log()
        self.nivel = situacao(self.tarefa, self.log)
        if self.nivel != antes:
            self.icone.icon = desenhar(self.nivel)
            if self.nivel == "erro":
                self.icone.notify(self.linha_problema(None) if self.log["graves"] else
                                  "Nenhuma busca terminou na última hora. Veja o log pelo ícone.", "PromoTrix com problema")
        if self.pedida_em and self.nivel != "buscando" and self.log["mexido"] > self.pedida_em:
            self.pedida_em = None
            l = self.log
            if self.nivel == "erro":
                pass  # o aviso de erro já saiu acima
            elif l["novas"]:
                self.icone.notify(f"{l['novas']} promoção(ões) nova(s). {l['no_alvo']} no alvo.", "Busca feita")
            else:
                self.icone.notify(f"{l['lidas']} promoções lidas, {l['no_alvo']} no alvo, nenhuma nova.", "Busca feita")
        self.icone.title = self.dica()
        self.icone.update_menu()

    def vigiar(self, icone):
        icone.visible = True
        self.parar = False
        ultima_tarefa = time.time()
        while not self.parar:
            time.sleep(2)
            # O Agendador é lento de consultar (abre um PowerShell): de minuto em minuto basta, e
            # o rodando.txt já mostra a busca na hora.
            if time.time() - ultima_tarefa > 60:
                self.tarefa = ler_tarefa()
                ultima_tarefa = time.time()
            try:
                self.recalcular()
            except Exception:
                pass  # log sendo reescrito no meio da leitura: tenta de novo daqui a 2 s

    def rodar(self):
        self.icone.run(setup=self.vigiar)


def criar_atalho():
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    alvo = pythonw if pythonw.exists() else Path(sys.executable)
    ps(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{ATALHO}');"
       f"$s.TargetPath='{alvo}';$s.Arguments='\"{PASTA / 'bandeja.py'}\"';"
       f"$s.WorkingDirectory='{PASTA}';$s.Description='PromoTrix na bandeja';$s.Save()")


def uma_copia_so():
    ctypes.windll.kernel32.CreateMutexW(None, False, "PromoTrixBandeja")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if "--remover" in sys.argv:
        ATALHO.unlink(missing_ok=True)
        print("Tirado da inicialização do Windows.")
        sys.exit()
    if "--instalar" in sys.argv:
        criar_atalho()
        print(f"Atalho criado em {ATALHO}")
        os.startfile(ATALHO)  # abre já, sem esperar o próximo logon
        sys.exit()
    if uma_copia_so():
        Bandeja().rodar()
