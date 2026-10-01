"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITENS = [
  { href: "/", nome: "Painel" },
  { href: "/regras", nome: "Regras" },
  { href: "/historico", nome: "Histórico" },
];

export function NavLinks() {
  const caminho = usePathname();
  return (
    <>
      {ITENS.map((i) => (
        <Link key={i.href} href={i.href} className={caminho === i.href ? "ativo" : undefined}>
          {i.nome}
        </Link>
      ))}
    </>
  );
}
