"""Janela de alerta do PromoTrix: grande, no meio da tela, sempre por cima e com alarme.

O promotrix.py abre esta janela num processo separado, então a tarefa agendada termina e a janela
continua. Ela só fecha quando a pessoa clicar em Fechar.
O alarme toca em repetição, alto o bastante para ouvir longe do PC, até clicar em "Parar alarme" ou
Fechar, ou até passar TEMPO_ALARME_S (para não tocar a tarde toda com a casa vazia).
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
FONTE = "Segoe UI"
ALARME = Path(r"C:\Windows\Media\Alarm01.wav")  # o despertador do Windows
TEMPO_ALARME_S = 180


def mostrar(promos, painel, teste, texto_faixa="PROMOÇÃO ENCONTRADA!"):
    root = tk.Tk()
    root.title("PromoTrix: " + texto_faixa.rstrip("!").lower() + (" (teste)" if teste else ""))
    root.configure(bg=BRANCO)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    topo = tk.Frame(root, bg=AMARELO)
    topo.pack(fill="x")
    faixa = tk.Label(topo, text=("TESTE · " if teste else "") + texto_faixa,
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


if __name__ == "__main__":
    arquivo = Path(next(a for a in sys.argv[1:] if not a.startswith("--")))
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    arquivo.unlink(missing_ok=True)
    if isinstance(dados, list):  # formato antigo: só a lista de promoções
        dados = {"promos": dados, "painel": None}
    mostrar(dados["promos"], dados.get("painel"), "--teste" in sys.argv, dados.get("faixa", "PROMOÇÃO ENCONTRADA!"))
