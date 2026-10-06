-- CreateTable
CREATE TABLE "Preco" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "promocaoId" TEXT NOT NULL,
    "valor" REAL NOT NULL,
    "em" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Preco_promocaoId_fkey" FOREIGN KEY ("promocaoId") REFERENCES "Promocao" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE INDEX "Preco_promocaoId_em_idx" ON "Preco"("promocaoId", "em");
