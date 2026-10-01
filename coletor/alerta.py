"""Janela de alerta do PromoTrix: grande, no meio da tela, sempre por cima e com som.

O promotrix.py abre esta janela num processo separado, então a tarefa agendada termina e a janela
continua. Ela só fecha quando a pessoa clicar em Fechar.
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
        tk.Button(botoes, text="Abrir promoção", font=(FONTE, 13, "bold"), bg=VERDE, fg=BRANCO,
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

    rodape = tk.Frame(root, bg=BRANCO, pady=4)
    rodape.pack(pady=(4, 20))
    if painel:
        tk.Button(rodape, text="Ver todas as promoções", font=(FONTE, 12), bg=CINZA_CLARO, relief="flat",
                  padx=18, pady=6, cursor="hand2", command=lambda: webbrowser.open(painel)).pack(side="left", padx=6)
    tk.Button(rodape, text="Fechar", font=(FONTE, 12), bg=CINZA_CLARO, relief="flat", padx=24, pady=6,
              cursor="hand2", command=root.destroy).pack(side="left", padx=6)

    # No meio da tela (um pouco acima do centro) e na frente de tudo.
    root.update_idletasks()
    largura, altura = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{(root.winfo_screenwidth() - largura) // 2}+{max(20, (root.winfo_screenheight() - altura) // 3)}")
    root.lift()
    root.focus_force()

    def tocar(vezes=3):
        if vezes:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            root.after(800, tocar, vezes - 1)

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
    mostrar(dados["promos"], dados.get("painel"), "--teste" in sys.argv)
