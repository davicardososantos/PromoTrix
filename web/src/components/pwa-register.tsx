"use client";

import { useEffect, useState } from "react";

type EventoInstalar = Event & { prompt: () => Promise<void>; userChoice: Promise<unknown> };

/**
 * Registra o service worker e oferece instalar o app (Android/desktop). No iPhone não existe esse
 * convite: a instalação é pelo "Adicionar à Tela de Início" do Safari. Mesmo padrão do Fintrix.
 */
export function PwaRegister() {
  const [convite, setConvite] = useState<EventoInstalar | null>(null);
  const [dispensado, setDispensado] = useState(false);

  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
    const aoConvidar = (e: Event) => {
      e.preventDefault();
      setConvite(e as EventoInstalar);
    };
    window.addEventListener("beforeinstallprompt", aoConvidar);
    return () => window.removeEventListener("beforeinstallprompt", aoConvidar);
  }, []);

  if (!convite || dispensado) return null;
  return (
    <div className="convite">
      <span style={{ flex: 1, fontSize: 14 }}>Instalar o PromoTrix como app na tela inicial?</span>
      <button
        className="btn btn-marca"
        onClick={async () => {
          await convite.prompt();
          await convite.userChoice;
          setConvite(null);
        }}
      >
        Instalar
      </button>
      <button className="btn btn-secundario" onClick={() => setDispensado(true)}>
        Agora não
      </button>
    </div>
  );
}
