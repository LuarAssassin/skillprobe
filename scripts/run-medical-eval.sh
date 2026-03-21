#!/usr/bin/env bash
# 对 OpenClaw-Medical-Skills 中的 adhd-daily-planner 与 ai-analyzer 做真实 A/B 评测
# 使用当前运行时已配置的模型提供方；无需强制绑定 OpenAI

set -euo pipefail

SKILLPROBE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MEDICAL_SKILLS_ROOT="${MEDICAL_SKILLS_ROOT:-/tmp/OpenClaw-Medical-Skills}"
OUTPUT_BASE="${SKILLPROBE_ROOT}/outputs/medical-eval"
TASKS="${TASKS:-3}"
MODEL="${MODEL:-${SKILLPROBE_MODEL:-}}"

if [ ! -d "$MEDICAL_SKILLS_ROOT/skills" ]; then
    echo "Cloning OpenClaw-Medical-Skills to $MEDICAL_SKILLS_ROOT ..."
    git clone --depth 1 https://github.com/FreedomIntelligence/OpenClaw-Medical-Skills.git "$MEDICAL_SKILLS_ROOT"
fi

export PYTHONPATH="$SKILLPROBE_ROOT"
cd "$SKILLPROBE_ROOT"

run_one() {
    local name="$1"
    local path="$2"
    echo "=============================================="
    echo "Evaluating: $name"
    echo "=============================================="
    local cmd=(python -m apps.cli.main evaluate "$path" --tasks "$TASKS" --output-dir "${OUTPUT_BASE}/${name}")
    if [ -n "$MODEL" ]; then
        cmd+=(--model "$MODEL")
    fi
    "${cmd[@]}"
    echo ""
}

run_one "adhd-daily-planner" "$MEDICAL_SKILLS_ROOT/skills/adhd-daily-planner"
run_one "ai-analyzer"        "$MEDICAL_SKILLS_ROOT/skills/ai-analyzer"

echo "Done. Reports:"
echo "  $OUTPUT_BASE/adhd-daily-planner/report.md"
echo "  $OUTPUT_BASE/ai-analyzer/report.md"
