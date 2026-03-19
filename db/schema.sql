-- SkillProbe evaluation storage for web service and batch runs
-- SQLite 3

-- Skills from a source repo (e.g. OpenClaw-Medical-Skills)
CREATE TABLE IF NOT EXISTS skills (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  repo_source TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  description TEXT,
  profile_json TEXT,
  is_directly_testable INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(repo_source, repo_path)
);

CREATE INDEX IF NOT EXISTS idx_skills_repo ON skills(repo_source, repo_path);
CREATE INDEX IF NOT EXISTS idx_skills_slug ON skills(slug);

-- One evaluation run per skill (latest overwrites or append by design)
CREATE TABLE IF NOT EXISTS evaluations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_id TEXT NOT NULL REFERENCES skills(id),
  status TEXT NOT NULL DEFAULT 'pending',  -- pending | running | completed | failed
  baseline_total REAL,
  with_skill_total REAL,
  net_gain REAL,
  recommendation_label TEXT,
  recommendation_detail TEXT,
  report_summary TEXT,
  details_json TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(skill_id)
);

CREATE INDEX IF NOT EXISTS idx_evaluations_skill ON evaluations(skill_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_status ON evaluations(status);
CREATE INDEX IF NOT EXISTS idx_evaluations_net_gain ON evaluations(net_gain);

-- Per-task results within an evaluation
CREATE TABLE IF NOT EXISTS evaluation_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
  task_index INTEGER NOT NULL,
  prompt TEXT NOT NULL,
  baseline_output TEXT,
  with_skill_output TEXT,
  baseline_scores_json TEXT,
  with_skill_scores_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(evaluation_id, task_index)
);

CREATE INDEX IF NOT EXISTS idx_evaluation_tasks_eval ON evaluation_tasks(evaluation_id);
