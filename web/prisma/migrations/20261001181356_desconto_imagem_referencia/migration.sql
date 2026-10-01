-- AlterTable
ALTER TABLE "Promocao" ADD COLUMN "desconto" REAL;
ALTER TABLE "Promocao" ADD COLUMN "descontoOrigem" TEXT;
ALTER TABLE "Promocao" ADD COLUMN "imagem" TEXT;

-- AlterTable
ALTER TABLE "Regra" ADD COLUMN "descontoMin" REAL;
ALTER TABLE "Regra" ADD COLUMN "precoReferencia" REAL;
