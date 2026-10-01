"use client";

import { useState } from "react";
import { Certo, Copiar } from "@/components/icones";

export function CopiarCupom({ codigo }: { codigo: string }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <button
      type="button"
      className="btn btn-cupom"
      title="Copiar o cupom"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(codigo);
          setCopiado(true);
          setTimeout(() => setCopiado(false), 1800);
        } catch {
          /* sem permissão de área de transferência: o código continua visível no botão */
        }
      }}
    >
      {copiado ? <Certo tamanho={15} /> : <Copiar tamanho={15} />}
      {copiado ? "Copiado" : codigo}
    </button>
  );
}
