"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import { auth } from "@/lib/auth";

async function exigirLogin() {
  const sessao = await auth();
  if (!sessao?.user?.id) throw new Error("não autorizado");
}

/** "a57, 256" → ["a57","256"] (o coletor ignora maiúsculas e acentos na comparação). */
const termos = (v: FormDataEntryValue | null) =>
  JSON.stringify(
    String(v ?? "")
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
  );
const numero = (v: FormDataEntryValue | null) => {
  const t = String(v ?? "").trim().replace(",", ".");
  return t === "" ? null : Number(t);
};
const texto = (v: FormDataEntryValue | null) => String(v ?? "").trim() || null;
const partes = (v: FormDataEntryValue | null) =>
  String(v ?? "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

/** Trecho de passagem aérea (ver coletor/voos.py). Sem os três primeiros campos, não é regra de voo. */
function voo(dados: FormData) {
  const origens = partes(dados.get("vooOrigens")).map((s) => s.toUpperCase());
  const destinos = partes(dados.get("vooDestinos")).map((s) => s.toUpperCase());
  const datas = partes(dados.get("vooDatas"));
  if (!origens.length || !destinos.length || !datas.length) return null;
  const maxParadas = numero(dados.get("vooMaxParadas"));
  const intervalo = numero(dados.get("vooIntervaloH"));
  return JSON.stringify({
    origens,
    destinos,
    datas,
    ...(maxParadas != null ? { max_paradas: maxParadas } : {}),
    ...(intervalo != null ? { intervalo_h: intervalo } : {}),
  });
}

export async function salvarRegra(dados: FormData) {
  await exigirLogin();
  const id = texto(dados.get("id"));
  const campos = {
    grupo: String(dados.get("grupo")).trim(),
    nome: String(dados.get("nome")).trim(),
    prioridade: dados.get("prioridade") === "alta" ? "alta" : "normal",
    precisa: termos(dados.get("precisa")),
    qualquer: termos(dados.get("qualquer")),
    naoPode: termos(dados.get("naoPode")),
    precoMin: numero(dados.get("precoMin")),
    precoMax: numero(dados.get("precoMax")),
    temperaturaMin: numero(dados.get("temperaturaMin")),
    precoReferencia: numero(dados.get("precoReferencia")),
    descontoMin: numero(dados.get("descontoMin")),
    voo: voo(dados),
    ate: texto(dados.get("ate")),
  };
  if (!campos.grupo || !campos.nome) return;
  if (id) {
    await prisma.regra.update({ where: { id }, data: campos });
  } else {
    const ultima = await prisma.regra.findFirst({ orderBy: { ordem: "desc" } });
    await prisma.regra.create({ data: { ...campos, ordem: (ultima?.ordem ?? 0) + 1 } });
  }
  revalidatePath("/regras");
  revalidatePath("/");
}

export async function alternarRegra(dados: FormData) {
  await exigirLogin();
  const id = String(dados.get("id"));
  const regra = await prisma.regra.findUnique({ where: { id } });
  if (regra) await prisma.regra.update({ where: { id }, data: { ativa: !regra.ativa } });
  revalidatePath("/regras");
  revalidatePath("/");
}

export async function apagarRegra(dados: FormData) {
  await exigirLogin();
  await prisma.regra.delete({ where: { id: String(dados.get("id")) } }).catch(() => {});
  revalidatePath("/regras");
  revalidatePath("/");
}

export async function salvarBusca(dados: FormData) {
  await exigirLogin();
  const termo = String(dados.get("termo") ?? "").trim();
  if (!termo) return;
  const ultima = await prisma.busca.findFirst({ orderBy: { ordem: "desc" } });
  await prisma.busca.create({ data: { termo, ate: texto(dados.get("ate")), ordem: (ultima?.ordem ?? 0) + 1 } });
  revalidatePath("/regras");
}

export async function alternarBusca(dados: FormData) {
  await exigirLogin();
  const id = String(dados.get("id"));
  const busca = await prisma.busca.findUnique({ where: { id } });
  if (busca) await prisma.busca.update({ where: { id }, data: { ativa: !busca.ativa } });
  revalidatePath("/regras");
}

export async function apagarBusca(dados: FormData) {
  await exigirLogin();
  await prisma.busca.delete({ where: { id: String(dados.get("id")) } }).catch(() => {});
  revalidatePath("/regras");
}
