"""Janela de alerta do PromoTrix: grande, no meio da tela, sempre por cima e com alarme.

O promotrix.py abre esta janela num processo separado, então a tarefa agendada termina e a janela
continua. Ela só fecha quando a pessoa clicar em Fechar.
O alarme toca em repetição, alto o bastante para ouvir longe do PC, até clicar em "Parar alarme" ou
Fechar, ou até passar TEMPO_ALARME_S (para não tocar a tarde toda com a casa vazia).
Cupom de loja tem outro aviso, discreto (mostrar_cupons): cartão escuro no canto, com um som curto.
Uso: pythonw alerta.py <alerta-*.json> [--teste]   (o JSON é apagado depois de lido)
"""
import json
import sys
import tkinter as tk
import webbrowser
import winsound
from pathlib import Path

AMARELO, ESCURO, VERDE, VERDE_ESCURO = "#FFE600", "#111827", "#047857", "#065F46"
BRANCO, CINZA, CINZA_CLARO = "#FFFFFF", "#4B5563", "#E5E7EB"
CARTAO_ESCURO, CINZA_ESCURO, VERDE_CLARO = "#1F2937", "#9CA3AF", "#34D399"  # aviso de cupom
FONTE = "Segoe UI"
ALARME = Path(r"C:\Windows\Media\Alarm01.wav")  # o despertador do Windows
TEMPO_ALARME_S = 180


def mostrar(promos, painel, teste):
    root = tk.Tk()
    root.title("PromoTrix: promoção encontrada" + (" (teste)" if teste else ""))
    root.configure(bg=BRANCO)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    topo = tk.Frame(root, bg=AMARELO)
    topo.pack(fill="x")
    faixa = tk.Label(topo, text=("TESTE · " if teste else "") + "PROMOÇÃO ENCONTRADA!",
                     font=(FONTE, 24, "bold"), bg=AMARELO, fg=ESCURO, padx=40, pady=16)
    faixa.pack()

    for p in promos[:4]:
        caixa = tk.Frame(root, bg=BRANCO, padx=32, pady=12)
        caixa.pack(fill="x")
        tk.Label(caixa, text=p["regra"], font=(FONTE, 15, "bold"), bg=BRANCO, fg=CINZA, anchor="w").pack(fill="x")
        tk.Label(caixa, text=p["preco_txt"], font=(FONTE, 44, "bold"), bg=BRANCO, fg=VERDE, anchor="w").pack(fill="x")
        extras = [x for x in (p.get("desconto_txt"), f"{p['temperatura']:.0f}° no Pelando" if p.get("temperatura") else None) if x]
        if extras:
            tk.Label(caixa, text="  ·  ".join(extras), font=(FONTE, 13, "bold"), bg=BRANCO, fg=VERDE_ESCURO,
                     anchor="w").pack(fill="x")
        tk.Label(caixa, text=f"{p['loja']} · {p['titulo']}", font=(FONTE, 12), bg=BRANCO, fg=ESCURO,
                 anchor="w", justify="left", wraplength=600).pack(fill="x")
        botoes = tk.Frame(caixa, bg=BRANCO, pady=12)
        botoes.pack(fill="x")
        tk.Button(botoes, text=p.get("botao", "Abrir promoção"), font=(FONTE, 13, "bold"), bg=VERDE, fg=BRANCO,
                  activebackground=VERDE_ESCURO, activeforeground=BRANCO, relief="flat", padx=18, pady=8,
                  cursor="hand2", command=lambda link=p["link"]: webbrowser.open(link)).pack(side="left")
        if p.get("cupom"):
            botao = tk.Button(botoes, text=f"Copiar cupom {p['cupom']}", font=(FONTE, 13, "bold"),
                              bg=ESCURO, fg=AMARELO, activebackground=CINZA, activeforeground=AMARELO,
                              relief="flat", padx=18, pady=8, cursor="hand2")
            botao.config(command=lambda c=p["cupom"], b=botao: (root.clipboard_clear(), root.clipboard_append(c),
                                                                b.config(text=f"Cupom {c} copiado ✓")))
            botao.pack(side="left", padx=12)
    if len(promos) > 4:
        tk.Label(root, text=f"+ {len(promos) - 4} no painel", font=(FONTE, 12), bg=BRANCO, fg=CINZA).pack()

    def parar_alarme():
        winsound.PlaySound(None, 0)
        botao_alarme.pack_forget()

    def fechar():
        winsound.PlaySound(None, 0)
        root.destroy()

    rodape = tk.Frame(root, bg=BRANCO, pady=4)
    rodape.pack(pady=(4, 20))
    botao_alarme = tk.Button(rodape, text="Parar alarme", font=(FONTE, 12, "bold"), bg=ESCURO, fg=AMARELO,
                             activebackground=CINZA, activeforeground=AMARELO, relief="flat", padx=18, pady=6,
                             cursor="hand2", command=parar_alarme)
    botao_alarme.pack(side="left", padx=6)
    if painel:
        tk.Button(rodape, text="Ver todas as promoções", font=(FONTE, 12), bg=CINZA_CLARO, relief="flat",
                  padx=18, pady=6, cursor="hand2", command=lambda: webbrowser.open(painel)).pack(side="left", padx=6)
    tk.Button(rodape, text="Fechar", font=(FONTE, 12), bg=CINZA_CLARO, relief="flat", padx=24, pady=6,
              cursor="hand2", command=fechar).pack(side="left", padx=6)
    root.protocol("WM_DELETE_WINDOW", fechar)  # o X da janela também cala o alarme

    # No meio da tela (um pouco acima do centro) e na frente de tudo.
    root.update_idletasks()
    largura, altura = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{(root.winfo_screenwidth() - largura) // 2}+{max(20, (root.winfo_screenheight() - altura) // 3)}")
    root.lift()
    root.focus_force()

    def tocar():
        if ALARME.exists():
            winsound.PlaySound(str(ALARME), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            root.after(TEMPO_ALARME_S * 1000, parar_alarme)
        else:  # Windows sem o som de alarme: volta aos bipes de antes
            for i in range(3):
                root.after(i * 800, winsound.MessageBeep, winsound.MB_ICONEXCLAMATION)
            botao_alarme.pack_forget()

    def piscar(vezes=10):  # a faixa amarela pisca uns segundos para chamar atenção
        if vezes:
            escuro = vezes % 2 == 0
            cor_fundo, cor_texto = (ESCURO, AMARELO) if escuro else (AMARELO, ESCURO)
            topo.config(bg=cor_fundo)
            faixa.config(bg=cor_fundo, fg=cor_texto)
            root.after(450, piscar, vezes - 1)

    tocar()
    piscar()
    root.mainloop()


def mostrar_cupons(cupons, painel, teste):
    """Aviso de cupom: um cartão pequeno e escuro no canto da tela, com um som curto, sem piscar e sem
    tomar o foco. Discreto de propósito, para não se confundir com a janela amarela das promoções."""
    root = tk.Tk()
    root.title("PromoTrix: cupom" + (" (teste)" if teste else ""))
    root.configure(bg=ESCURO)
    root.attributes("-topmost", True)
    root.attributes("-toolwindow", True)  # barra de título fininha, só com o X
    root.resizable(False, False)

    titulo = "CUPOM QUE PODE SERVIR" if len(cupons) == 1 else f"{len(cupons)} CUPONS QUE PODEM SERVIR"
    tk.Label(root, text=("TESTE · " if teste else "") + titulo, font=(FONTE, 10, "bold"), bg=ESCURO,
             fg=AMARELO, anchor="w").pack(fill="x", padx=16, pady=(12, 4))

    for c in cupons[:3]:
        caixa = tk.Frame(root, bg=CARTAO_ESCURO, padx=14, pady=10)
        caixa.pack(fill="x", padx=12, pady=4)
        linha = tk.Frame(caixa, bg=CARTAO_ESCURO)
        linha.pack(fill="x")
        tk.Label(linha, text=c["preco_txt"], font=(FONTE, 17, "bold"), bg=CARTAO_ESCURO, fg=BRANCO).pack(side="left")
        tk.Label(linha, text=c["loja"], font=(FONTE, 10), bg=CARTAO_ESCURO, fg=CINZA_ESCURO).pack(side="left", padx=8, pady=(5, 0))
        for texto, cor in ((c.get("desconto_txt"), CINZA_ESCURO), (c["regra"], VERDE_CLARO)):
            if texto:
                tk.Label(caixa, text=texto, font=(FONTE, 9), bg=CARTAO_ESCURO, fg=cor, anchor="w", justify="left",
                         wraplength=380).pack(fill="x", pady=(2, 0))
        botoes = tk.Frame(caixa, bg=CARTAO_ESCURO)
        botoes.pack(fill="x", pady=(8, 0))
        if c.get("cupom"):
            botao = tk.Button(botoes, text=f"Copiar {c['cupom']}", font=(FONTE, 9, "bold"), bg=AMARELO, fg=ESCURO,
                              activebackground=AMARELO, relief="flat", padx=10, pady=2, cursor="hand2")
            botao.config(command=lambda cod=c["cupom"], b=botao: (root.clipboard_clear(), root.clipboard_append(cod),
                                                                  b.config(text=f"{cod} copiado ✓")))
            botao.pack(side="left")
        tk.Button(botoes, text="Abrir", font=(FONTE, 9), bg=CINZA, fg=BRANCO, activebackground=CINZA,
                  activeforeground=BRANCO, relief="flat", padx=10, pady=2, cursor="hand2",
                  command=lambda link=c["link"]: webbrowser.open(link)).pack(side="left", padx=6)
    if len(cupons) > 3:
        tk.Label(root, text=f"+ {len(cupons) - 3} no painel", font=(FONTE, 9), bg=ESCURO, fg=CINZA_ESCURO).pack()

    rodape = tk.Frame(root, bg=ESCURO)
    rodape.pack(fill="x", padx=12, pady=(4, 12))
    tk.Button(rodape, text="Fechar", font=(FONTE, 9), bg=ESCURO, fg=CINZA_ESCURO, activebackground=CINZA,
              relief="flat", cursor="hand2", command=root.destroy).pack(side="right")
    if painel:
        tk.Button(rodape, text="Ver todos os cupons", font=(FONTE, 9), bg=ESCURO, fg=CINZA_ESCURO,
                  activebackground=CINZA, relief="flat", cursor="hand2",
                  command=lambda: webbrowser.open(painel)).pack(side="right", padx=6)

    # No canto de baixo, à direita, acima da barra de tarefas. Sem focus_force: não rouba o teclado.
    root.update_idletasks()
    largura, altura = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{root.winfo_screenwidth() - largura - 16}+{root.winfo_screenheight() - altura - 64}")
    winsound.MessageBeep(winsound.MB_OK)
    root.mainloop()


if __name__ == "__main__":
    arquivo = Path(next(a for a in sys.argv[1:] if not a.startswith("--")))
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    arquivo.unlink(missing_ok=True)
    if isinstance(dados, list):  # formato antigo: só a lista de promoções
        dados = {"promos": dados, "painel": None}
    if dados.get("modo") == "cupom":
        mostrar_cupons(dados["promos"], dados.get("painel"), "--teste" in sys.argv)
    else:
        mostrar(dados["promos"], dados.get("painel"), "--teste" in sys.argv)
