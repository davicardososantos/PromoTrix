import Link from "next/link";
import { signOut } from "@/lib/auth";
import { Etiqueta } from "@/components/icones";
import { NavLinks } from "@/components/nav-links";

export function Topo() {
  return (
    <header className="topo">
      <div className="topo-dentro">
        <Link href="/" className="marca">
          <span className="marca-icone">
            <Etiqueta tamanho={18} />
          </span>
          <span className="marca-nome">PromoTrix</span>
        </Link>
        <nav className="nav">
          <NavLinks />
          <form
            action={async () => {
              "use server";
              await signOut({ redirectTo: "/login" });
            }}
          >
            <button type="submit">Sair</button>
          </form>
        </nav>
      </div>
    </header>
  );
}
