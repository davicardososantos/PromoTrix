import Link from "next/link";
import { signOut } from "@/lib/auth";

export function Topo() {
  return (
    <header className="topo">
      <strong>PromoTrix</strong>
      <nav>
        <Link href="/">Painel</Link>
        <Link href="/regras">Regras</Link>
        <Link href="/historico">Histórico</Link>
        <form
          action={async () => {
            "use server";
            await signOut({ redirectTo: "/login" });
          }}
        >
          <button type="submit">Sair</button>
        </form>
      </nav>
    </header>
  );
}
