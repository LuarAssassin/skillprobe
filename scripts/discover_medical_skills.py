#!/usr/bin/env python3
"""
Discover skills from OpenClaw-Medical-Skills and insert into SQLite.
Only skills with parseable SKILL.md are considered directly testable.
"""

import json
import sys
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.store import init_db, insert_skill, insert_evaluation


REPO_SOURCE = "OpenClaw-Medical-Skills"
REPO_URL = "https://github.com/FreedomIntelligence/OpenClaw-Medical-Skills"


def slug_from_name(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")[:128]


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Discover medical skills and populate DB")
    p.add_argument("--repo", default="/tmp/OpenClaw-Medical-Skills", help="Path to OpenClaw-Medical-Skills clone")
    p.add_argument("--db", default=None, help="SQLite path (default: skillprobe/outputs/evaluations.db)")
    p.add_argument("--limit", type=int, default=None, help="Max skills to process (default: all)")
    args = p.parse_args()

    repo = Path(args.repo)
    if not (repo / "skills").is_dir():
        print("Error: repo/skills not found at", repo / "skills", file=sys.stderr)
        sys.exit(1)

    db_path = args.db or str(ROOT / "outputs" / "evaluations.db")
    conn = init_db(db_path)
    skills_dir = repo / "skills"

    try:
        from packages.core.skill_profile.parser import parse_skill_dir
    except ImportError:
        # Fallback: no profile, just name and path
        parse_skill_dir = None

    added = 0
    failed = 0
    for path in sorted(skills_dir.iterdir()):
        if not path.is_dir():
            continue
        if args.limit is not None and added >= args.limit:
            break
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            skill_md = path / "README.md"
        if not skill_md.exists():
            failed += 1
            continue
        repo_path = f"skills/{path.name}"
        slug = slug_from_name(path.name)
        try:
            if parse_skill_dir is not None:
                profile = parse_skill_dir(str(path))
                skill_id = profile.id
                name = profile.name
                description = (profile.description or "")[:2000]
                profile_json = json.dumps(profile.to_dict(), ensure_ascii=False)
            else:
                import hashlib
                skill_id = hashlib.sha256(f"{path.name}:{path}".encode()).hexdigest()[:12]
                name = path.name
                description = ""
                profile_json = None
            insert_skill(
                conn,
                id=skill_id,
                name=name,
                slug=slug,
                repo_source=REPO_SOURCE,
                repo_path=repo_path,
                description=description,
                profile_json=profile_json,
                is_directly_testable=1,
            )
            insert_evaluation(conn, skill_id=skill_id, status="pending")
            added += 1
        except Exception as e:
            failed += 1
            if added < 3:
                print("Skip", path.name, ":", e, file=sys.stderr)

    print(f"Added {added} skills to {db_path}. Skipped/failed: {failed}")


if __name__ == "__main__":
    main()
