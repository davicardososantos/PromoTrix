import webpush from "web-push";
import { prisma } from "@/lib/db";

/**
 * Notificação no celular (Web Push / VAPID), no mesmo padrão do Fintrix.
 * Chaves em env: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT.
 */
let configurado = false;
function configurar(): boolean {
  if (configurado) return true;
  const publica = process.env.VAPID_PUBLIC_KEY;
  const privada = process.env.VAPID_PRIVATE_KEY;
  if (!publica || !privada) return false;
  webpush.setVapidDetails(process.env.VAPID_SUBJECT || "mailto:promotrix@example.com", publica, privada);
  configurado = true;
  return true;
}

export type Aviso = { title: string; body: string; url?: string; tag?: string };

/** Manda para todos os aparelhos inscritos (ou só os de um usuário). Remove inscrição expirada. */
export async function avisarCelulares(aviso: Aviso, userId?: string): Promise<number> {
  if (!configurar()) return 0;
  const inscricoes = await prisma.pushSubscription.findMany({ where: userId ? { userId } : {} });
  let entregues = 0;
  for (const s of inscricoes) {
    try {
      await webpush.sendNotification(
        { endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } },
        JSON.stringify(aviso),
      );
      entregues++;
    } catch (err) {
      const status = (err as { statusCode?: number }).statusCode;
      if (status === 404 || status === 410) {
        await prisma.pushSubscription.delete({ where: { id: s.id } }).catch(() => {});
      }
    }
  }
  return entregues;
}
