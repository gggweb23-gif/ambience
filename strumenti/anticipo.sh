#!/usr/bin/env bash
# Video in anticipo, uno dopo l'altro sulla stessa "corsia": ogni voce e' "launcher|canale|giorni|etichetta run del motore".
# Lancia il video, aspetta che il motore finisca, poi passa al successivo.
set -u
for voce in "$@"; do
  IFS='|' read -r launcher canale giorni etichetta <<< "$voce"
  [ -z "$launcher" ] && continue
  if [ "$launcher" = "avvio_canali.yml" ]; then   # i video Pexels (Storia, Agora/KAO) vanno uno alla volta: si aspetta che finisca quello in corso
    while [ "$(gh api "repos/$R/actions/runs?status=in_progress&per_page=50" --jq '[.workflow_runs[] | select(.path | test("video_storia.yml|video_produzione.yml"))] | length')" != "0" ]; do sleep 60; done
  fi
  inizio=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "== $(date +%H:%M) $canale: video in anticipo di $giorni giorni ($launcher)"
  gh api "repos/$R/actions/workflows/$launcher/dispatches" -f ref=main -f "inputs[canale]=$canale" -f "inputs[anticipo]=$giorni" || { echo "  lancio non riuscito"; continue; }
  id=""
  for i in $(seq 1 40); do   # il motore parte entro qualche minuto
    sleep 30
    id=$(gh api "repos/$R/actions/runs?per_page=50&created=>=$inizio" --jq ".workflow_runs[] | select(.display_title == \"$etichetta $canale\") | .id" | head -1)
    [ -n "$id" ] && break
  done
  if [ -z "$id" ]; then echo "  motore non partito (vedi il log dell'avvio)"; continue; fi
  echo "  motore partito: run $id"
  while [ "$(gh api "repos/$R/actions/runs/$id" --jq .status)" != "completed" ]; do sleep 60; done
  echo "  $(date +%H:%M) finito: $(gh api "repos/$R/actions/runs/$id" --jq .conclusion)"
done
