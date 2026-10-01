#!/usr/bin/env sh
# Deploy do PromoTrix na VPS. Chamado pelo workflow (.github/workflows/deploy.yml) via ssh.
# Copiado do Fintrix (pós-incidente do 502): NUNCA derruba o app no ar antes de saber que o novo
# sobe. Ordem: build → migrations (app antigo ainda servindo) → recria → healthcheck de verdade.
# Só mexe no projeto `promotrix` (containers promotrix_*): os outros stacks do servidor não são tocados.
set -eu

if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
DC="$DC -p promotrix"
PORTA="$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '"' || true)"
PORTA="${PORTA:-3200}"
echo ">> Usando: $DC (porta $PORTA)"

echo ">> [1/4] Build da imagem nova (app antigo continua no ar)..."
$DC build

echo ">> [2/4] Migrations + primeiro usuário (app antigo AINDA no ar). Log abaixo:"
echo "----------------------------------------------------------------"
if ! $DC run --rm migrate; then
  echo "----------------------------------------------------------------"
  echo ">> FALHA nas migrations. O app ANTIGO continua servindo."
  $DC run --rm migrate npx prisma migrate status || true
  exit 1
fi
echo "----------------------------------------------------------------"

echo ">> [3/4] Recriando os containers do PromoTrix com a imagem nova..."
$DC down --remove-orphans
$DC up -d

echo ">> [4/4] Healthcheck: o app precisa RESPONDER na porta $PORTA..."
ok=0
for i in $(seq 1 20); do
  if curl -fsS -o /dev/null "http://localhost:$PORTA/login"; then
    echo ">> App OK na $PORTA."
    ok=1
    break
  fi
  echo ">> Aguardando o app subir ($i/20)..."
  sleep 3
done
if [ "$ok" -ne 1 ]; then
  echo ">> ERRO: o app não respondeu na $PORTA. Últimos logs:"
  docker logs promotrix_app --tail 80 || true
  exit 1
fi

docker image prune -f
echo ">> Deploy concluído."
