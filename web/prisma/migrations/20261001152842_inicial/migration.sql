-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "email" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "criadoEm" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Busca" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "termo" TEXT NOT NULL,
    "ate" TEXT,
    "ativa" BOOLEAN NOT NULL DEFAULT true,
    "ordem" INTEGER NOT NULL DEFAULT 0
);

-- CreateTable
CREATE TABLE "Regra" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "grupo" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "prioridade" TEXT NOT NULL DEFAULT 'normal',
    "precisa" TEXT NOT NULL DEFAULT '[]',
    "qualquer" TEXT NOT NULL DEFAULT '[]',
    "naoPode" TEXT NOT NULL DEFAULT '[]',
    "precoMin" REAL,
    "precoMax" REAL,
    "temperaturaMin" REAL,
    "ate" TEXT,
    "ativa" BOOLEAN NOT NULL DEFAULT true,
    "ordem" INTEGER NOT NULL DEFAULT 0
);

-- CreateTable
CREATE TABLE "Coleta" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "em" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lidas" INTEGER NOT NULL,
    "dentro" INTEGER NOT NULL,
    "novos" INTEGER NOT NULL
);

-- CreateTable
CREATE TABLE "Promocao" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "titulo" TEXT NOT NULL,
    "preco" REAL,
    "loja" TEXT NOT NULL,
    "temperatura" REAL NOT NULL DEFAULT 0,
    "postadaEm" DATETIME,
    "link" TEXT NOT NULL,
    "cupom" TEXT,
    "regraId" TEXT,
    "primeiraVez" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ultimaVez" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ultimaColetaId" TEXT,
    "avisadaEm" DATETIME,
    CONSTRAINT "Promocao_regraId_fkey" FOREIGN KEY ("regraId") REFERENCES "Regra" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PushSubscription" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "userId" TEXT NOT NULL,
    "endpoint" TEXT NOT NULL,
    "p256dh" TEXT NOT NULL,
    "auth" TEXT NOT NULL,
    "criadoEm" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PushSubscription_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "Promocao_regraId_idx" ON "Promocao"("regraId");

-- CreateIndex
CREATE INDEX "Promocao_ultimaColetaId_idx" ON "Promocao"("ultimaColetaId");

-- CreateIndex
CREATE UNIQUE INDEX "PushSubscription_endpoint_key" ON "PushSubscription"("endpoint");

-- CreateIndex
CREATE INDEX "PushSubscription_userId_idx" ON "PushSubscription"("userId");
