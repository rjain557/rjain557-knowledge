---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-28T03:02:17.091238-07:00
---

# Add idempotent schema migration runner to replace manual SQL execution

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

The commit history shows repeated ad-hoc DB fixes (fix(db): decode NVARCHAR as UTF-16LE, fix(db): make record_link idempotent, fix(db): match real schema) and the sql/ directory exists but there is no migration runner visible in scripts/ or pyproject.toml entry points. This means schema changes are applied manually and inconsistently across environments. The system already uses pyodbc and SQL Server; adding a minimal migration runner (numbered SQL files, a migrations_applied table) would make the dead-letter queue addition above and all future schema changes safe to deploy without manual steps.

## Cited evidence

- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - sql/ (list and read ALL .sql files — note their naming convention)
  - src/cortex/db.py (or the main DB module — find with `grep -r 'pyodbc' src/ -l`)
  - .env.example (confirm DB connection env var names)
  - pyproject.toml (check existing scripts/entry points)

Task: Build a minimal idempotent SQL migration runner.

1. Create `scripts/migrate.py`:
```python
"""
Runs all sql/NNN_*.sql files in numeric order.
Skips files already recorded in cortex.schema_migrations.
Safe to run multiple times (idempotent).
"""
import os, re, pathlib, structlog
from cortex.db import get_connection  # use existing connection helper

log = structlog.get_logger()

BOOTSTRAP_SQL = """
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'cortex' AND TABLE_NAME = 'schema_migrations'
)
CREATE TABLE cortex.schema_migrations (
    filename     NVARCHAR(256) PRIMARY KEY,
    applied_at   DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
"""

def run_migrations(sql_dir: str = "sql") -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(BOOTSTRAP_SQL)
    conn.commit()

    files = sorted(
        p for p in pathlib.Path(sql_dir).glob("*.sql")
        if re.match(r'^\d+_', p.name)
    )
    for f in files:
        cur.execute("SELECT 1 FROM cortex.schema_migrations WHERE filename = ?", f.name)
        if cur.fetchone():
            log.info("migration_skipped", file=f.name)
            continue
        log.info("migration_applying", file=f.name)
        sql = f.read_text(encoding="utf-8")
        # Split on GO statements (SQL Server batch separator)
        for batch in re.split(r'^\s*GO\s*$', sql, flags=re.MULTILINE | re.IGNORECASE):
            if batch.strip():
                cur.execute(batch)
        cur.execute("INSERT INTO cortex.schema_migrations (filename) VALUES (?)", f.name)
        conn.commit()
        log.info("migration_applied", file=f.name)

if __name__ == "__main__":
    run_migrations()
```

2. Rename existing sql/ files to follow the `NNN_description.sql` convention if they don't already (e.g., `001_initial_schema.sql`, `002_record_link_upsert.sql`). Use git mv so history is preserved.

3. Add to `pyproject.toml` under `[project.scripts]`:
```toml
[project.scripts]
cortex-migrate = "cortex.migrate:run_migrations"
```
(Or add as a direct scripts/ entry if the project doesn't use entry points.)

4. Add a one-liner to `CLAUDE.md` (or the ingestion skill card if already refactored): 'Before running any DB-dependent script in a new environment, run `python scripts/migrate.py` first.'

Edge cases:
  - SQL Server does not support `IF NOT EXISTS` on all DDL — use the INFORMATION_SCHEMA check pattern shown above.
  - Files without the `NNN_` prefix (e.g., ad-hoc query files) must be ignored by the runner.
  - If a migration fails mid-batch, the transaction is rolled back and the filename is NOT inserted into schema_migrations, so re-running is safe.
  - Test with a dry-run flag: add `--dry-run` argparse option that prints file names without executing.

Verification:
  - Run `python scripts/migrate.py` twice on the dev DB; second run should log only 'migration_skipped' lines.
  - Confirm `SELECT * FROM cortex.schema_migrations` shows one row per sql/ file.
  - Introduce a syntax error in a new test .sql file, run migrate.py, confirm it raises and does NOT insert the filename.
```
