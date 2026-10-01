"use client";

import { useEffect, useState } from "react";
import { Sino } from "@/components/icones";

/** Converte a chave pública VAPID (base64url) em bytes para o pushManager. */
function chaveEmBytes(base64: string): Uint8Array {
  const preenchimento = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + preenchimento).replace(/-/g, "+").replace(/_/g, "/");
  const bruto = atob(b64);
  return Uint8Array.from(bruto, (c) => c.charCodeAt(0));
}

type Estado = "carregando" | "desligado" | "ligado" | "bloqueado" | "sem-suporte" | "erro" | "ativando";

/** Receber no celular as promoções de prioridade alta (Web Push). */
export function AtivarPush() {
  const [estado, setEstado] = useState<Estado>("carregando");
  const [teste, setTeste] = useState("");

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return setEstado("sem-suporte");
    if (Notification.permission === "denied") return setEstado("bloqueado");
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((s) => setEstado(s ? "ligado" : "desligado"))
      .catch(() => setEstado("desligado"));
  }, []);

  async function ativar() {
    try {
      setEstado("ativando");
      if ((await Notification.requestPermission()) !== "granted") return setEstado("bloqueado");
      const { key } = await fetch("/api/push/public-key").then((r) => r.json());
      if (!key) return setEstado("erro");
      const reg = await navigator.serviceWorker.ready;
      const inscricao = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: chaveEmBytes(key) as BufferSource,
      });
      const r = await fetch("/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(inscricao),
      });
      setEstado(r.ok ? "ligado" : "erro");
    } catch {
      setEstado("erro");
    }
  }

  async function testar() {
    setTeste("Enviando...");
    const r = await fetch("/api/push/teste", { method: "POST" }).then((x) => x.json()).catch(() => null);
    setTeste(r?.entregues ? "Enviado. Veja a notificação." : "Não chegou em nenhum aparelho.");
  }

  if (estado === "carregando") return null;
  if (estado === "sem-suporte")
    return (
      <div className="push">
        <Sino />
        <span>
          Este navegador não recebe notificação. No iPhone, instale pelo Safari em <b>Adicionar à Tela de Início</b> e
          abra por lá.
        </span>
      </div>
    );
  if (estado === "ligado")
    return (
      <div className="push">
        <Sino />
        <span style={{ flex: 1 }}>
          <b>Notificações ligadas</b> neste aparelho para as promoções importantes.
        </span>
        <button className="btn btn-secundario" onClick={testar}>
          Mandar teste
        </button>
        {teste && <span>{teste}</span>}
      </div>
    );
  return (
    <div className="push">
      <Sino />
      <span style={{ flex: 1 }}>
        Receba as <b>promoções importantes</b> neste celular, na hora.
      </span>
      <button className="btn btn-marca" onClick={ativar} disabled={estado === "ativando"}>
        {estado === "ativando" ? "Ativando..." : "Ativar notificações"}
      </button>
      {estado === "bloqueado" && <p className="erro">Bloqueadas. Libere nas configurações do navegador.</p>}
      {estado === "erro" && <p className="erro">Não deu para ativar agora. Tente de novo.</p>}
    </div>
  );
}
