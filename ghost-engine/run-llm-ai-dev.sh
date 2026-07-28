#!/system/bin/sh

cd "/storage/emulated/0/ghost-engine" || exit 1

if [ ! -f ".env.local" ]; then
  echo "Missing .env.local"
  echo "Create it with OPENAI_API_KEY first."
  exit 1
fi

. ./.env.local

GHOST_REAL_LLM=1 \
GHOST_LLM_OPPONENT=1 \
GHOST_LLM_OPPONENT_DEBUG=1 \
GHOST_LLM_DEBUG=1 \
GHOST_LLM_STRATEGY_MODEL="gpt-5.6-sol" \
GHOST_LLM_STRATEGY_REASONING="medium" \
GHOST_LLM_NARRATION_MODEL="gpt-5.6-terra" \
GHOST_LLM_NARRATION_REASONING="none" \
GHOST_LLM_AMBIENT_MODEL="gpt-5.6-luna" \
GHOST_LLM_AMBIENT_REASONING="none" \
OPENAI_API_KEY="$OPENAI_API_KEY" \
python -m ghost.examples.ghost_revolution.dev_shortcuts
