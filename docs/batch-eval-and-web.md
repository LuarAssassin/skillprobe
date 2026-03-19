# 批量评测与 Web 服务数据流

## 数据存储（SQLite）

- **DB 路径**：`skillprobe/outputs/evaluations.db`
- **表**：
  - `skills`：技能元数据（id, name, slug, repo_source, repo_path, description, profile_json, is_directly_testable）
  - `evaluations`：每条技能的评测结果（skill_id, status, baseline_total, with_skill_total, net_gain, recommendation_label, report_summary, details_json, error_message）
  - `evaluation_tasks`：单次评测下的逐任务结果（evaluation_id, task_index, prompt, baseline_output, with_skill_output, baseline_scores_json, with_skill_scores_json）

## 流程概览

1. **发现技能**（写入 `skills` + `evaluations` 待评测）
   ```bash
   PYTHONPATH=. python scripts/discover_medical_skills.py --repo /path/to/OpenClaw-Medical-Skills [--limit 200]
   ```

2. **列出待评测**（供子 agent 拉取）
   ```bash
   PYTHONPATH=. python scripts/run_medical_batch_eval.py --list-pending --limit 20
   ```
   输出 JSON 数组，每项含 `skill_id`, `name`, `slug`, `skill_path`, `description`。

3. **子 agent 并发评测**
   - 将待评测列表按批拆分（如每批 10 条），每批交给一个子 agent。
   - 子 agent 按 `scripts/SUBAGENT_EVAL_INSTRUCTIONS.md` 对每条技能做 in-agent 评测，返回一个 JSON 数组（每项含 skill_id, status, baseline_total, with_skill_total, net_gain, recommendation_label, tasks 等）。

4. **结果写入 DB**
   - 单文件（数组）：
     ```bash
     PYTHONPATH=. python scripts/run_medical_batch_eval.py --record-dir outputs/batch_skills/batch_1/eval_results.json
     ```
   - 或目录下多个 JSON 文件（每文件一条结果）：
     ```bash
     PYTHONPATH=. python scripts/run_medical_batch_eval.py --record-dir outputs/results/
     ```

5. **汇总与导出**
   ```bash
   PYTHONPATH=. python scripts/run_medical_batch_eval.py --summary
   PYTHONPATH=. python scripts/run_medical_batch_eval.py --export outputs/evaluations_export.json
   ```

## 供 Web 服务使用

- **只读查询**：直接连 `outputs/evaluations.db`，查 `evaluations` + `skills`（JOIN skill_id）即可做列表、筛选、排序。
- **导出 JSON**：`--export` 得到的 JSON 可被静态站点或后端 API 定期生成/缓存。
- **扩展**：如需 REST API，可加一层（如 FastAPI）读同一 SQLite，或定时从 DB 导出到 JSON/其他存储。

## 单条结果录入（CLI）

若子 agent 只返回单条结果，可写入一个 JSON 文件后：
```bash
PYTHONPATH=. python scripts/record_eval_result.py path/to/result.json [--db outputs/evaluations.db]
```
