"use client";

import { useEffect, useState } from "react";

/** Converte a chave pública VAPID (base64url) em bytes para o pushManager. */
function chaveEmBytes(base64: string): Uint8Array {
  const preenchimento = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + preenchimento).replace(/-/g, "+").replace(/_/g, "/");
  const bruto = atob(b64);
  return Uint8Array.from(bruto, (c) => c.charCodeAt(0));
}

type Estado = "carregando" | "desligado" | "ligado" | "bloqueado" | "sem-suporte" | "erro" | "ativando";

/** Botão para receber no celular as promoções de prioridade alta (Web Push). */
export function AtivarPush() {
  const [estado, setEstado] = useState<Estado>("carregando");
  const [teste, setTeste] = useState<string>("");

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
    setTeste(r?.entregues ? "Enviado! Veja a notificação." : "Não chegou em nenhum aparelho.");
  }

  if (estado === "carregando") return null;
  if (estado === "sem-suporte")
    return (
      <p className="suave">
        Este aparelho não recebe notificação do navegador. No iPhone, instale o app pela opção &quot;Adicionar à Tela
        de Início&quot; do Safari e abra por lá.
      </p>
    );
  if (estado === "ligado")
    return (
      <p className="suave">
        Notificações ligadas neste aparelho.{" "}
        <button className="botao secundario" onClick={testar}>
          Mandar teste
        </button>{" "}
        {teste}
      </p>
    );
  return (
    <div className="faixa">
      <button className="botao" onClick={ativar} disabled={estado === "ativando"}>
        {estado === "ativando" ? "Ativando..." : "Receber as promoções importantes neste celular"}
      </button>
      {estado === "bloqueado" && <p className="erro">Notificações bloqueadas. Libere nas configurações do navegador.</p>}
      {estado === "erro" && <p className="erro">Não deu para ativar agora. Tente de novo.</p>}
    </div>
  );
}
