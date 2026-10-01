// Cria o primeiro usuário a partir de ADMIN_EMAIL / ADMIN_NOME / ADMIN_PASSWORD, só se ainda não
// existir nenhum. Roda depois das migrations (docker-compose, serviço `migrate`) e pode rodar sempre:
// se já tem usuário, não faz nada. Uso local: npm run admin
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();
try {
  if ((await prisma.user.count()) > 0) {
    console.log("Já existe usuário; nada a fazer.");
  } else {
    const email = (process.env.ADMIN_EMAIL || "").trim().toLowerCase();
    const senha = process.env.ADMIN_PASSWORD || "";
    if (!email || senha.length < 8) {
      console.error("Defina ADMIN_EMAIL e ADMIN_PASSWORD (8+ caracteres) para criar o primeiro usuário.");
      process.exit(1);
    }
    await prisma.user.create({
      data: { email, nome: process.env.ADMIN_NOME || email, passwordHash: await bcrypt.hash(senha, 10) },
    });
    console.log(`Usuário ${email} criado.`);
  }
} finally {
  await prisma.$disconnect();
}
