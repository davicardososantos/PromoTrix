-- CreateTable
CREATE TABLE "Cupom" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "titulo" TEXT NOT NULL,
    "loja" TEXT NOT NULL,
    "link" TEXT NOT NULL,
    "codigo" TEXT,
    "porcentagem" REAL,
    "valorFixo" REAL,
    "minimo" REAL,
    "limite" REAL,
    "valorTxt" TEXT NOT NULL,
    "regrasTxt" TEXT NOT NULL DEFAULT '',
    "condicoes" TEXT NOT NULL DEFAULT '[]',
    "servem" TEXT NOT NULL DEFAULT '[]',
    "temperatura" REAL NOT NULL DEFAULT 0,
    "postadoEm" DATETIME,
    "primeiraVez" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ultimaVez" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ultimaColetaId" TEXT,
    "avisadoEm" DATETIME
);

-- CreateIndex
CREATE INDEX "Cupom_ultimaColetaId_idx" ON "Cupom"("ultimaColetaId");
