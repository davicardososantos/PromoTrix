import { PrismaClient } from "@prisma/client";

// Uma instância só (o hot reload do `next dev` recriaria a cada mudança).
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
