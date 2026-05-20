"""
Create the n8n workflow that triggers Cortex's webhook every hour.

Reads the n8n API key from the vault (or from N8N_API_KEY env var) and
POSTs a workflow definition to https://n8n.ai.technijian.com/api/v1/workflows.

The workflow:
  Schedule (every 1h)  ->  HTTP Request POST /poll  ->  IF status != 'ok'  ->  noop
  (Cortex itself emails rjain@technijian.com on failure; n8n is just the
   scheduler. To add an n8n-side email alert too, configure the Send Email
   node in the UI after import.)

Usage:
    uv run python scripts/setup_n8n_workflow.py             # create or update
    uv run python scripts/setup_n8n_workflow.py --dry-run   # print JSON only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

N8N_BASE = "https://10.100.254.225/api/v1"   # use IP to dodge internal DNS;
                                              # cert won't match -> verify=False
WORKFLOW_NAME = "Cortex - Hourly Mail Poll"
WORKFLOW_NAME_GITHUB = "Cortex - Hourly GitHub Scan"
WORKFLOW_NAME_REPO_REVIEW = "Cortex - Daily Repo Review"
WORKFLOW_NAME_LINT = "Cortex - Daily Wiki Lint"

VAULT_KEY = (
    Path.home()
    / "OneDrive - Technijian, Inc"
    / "Documents" / "VSCODE" / "keys" / "te-dc-ai-n8n.md"
)


def _api_key() -> str:
    if "N8N_API_KEY" in os.environ:
        return os.environ["N8N_API_KEY"]
    txt = VAULT_KEY.read_text(encoding="utf-8")
    m = re.search(r"\*\*API Key \(JWT\):\*\*\s*`([^`]+)`", txt)
    if not m:
        raise SystemExit(f"Could not find API key in {VAULT_KEY}")
    return m.group(1)


def _headers(api_key: str) -> dict:
    return {"X-N8N-API-KEY": api_key, "Accept": "application/json",
            "Content-Type": "application/json"}


def build_workflow(webhook_url: str, webhook_secret: str) -> dict:
    """Return the n8n workflow JSON (v1 schema)."""
    return {
        "name": WORKFLOW_NAME,
        "nodes": [
            {
                "parameters": {
                    "rule": {
                        "interval": [
                            {"field": "hours", "hoursInterval": 1}
                        ]
                    }
                },
                "id": "trigger-1",
                "name": "Every hour",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [240, 300],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": webhook_url,
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "X-Webhook-Secret", "value": webhook_secret},
                            {"name": "Content-Type",   "value": "application/json"}
                        ]
                    },
                    "options": {
                        "timeout": 3000000,
                        "response": {"response": {"neverError": True}}
                    }
                },
                "id": "http-1",
                "name": "Poll Cortex",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [560, 300],
            },
            {
                "parameters": {
                    "conditions": {
                        "options": {"caseSensitive": True, "typeValidation": "loose"},
                        "conditions": [
                            {
                                "id": "cond-1",
                                "leftValue": "={{ $json.status }}",
                                "rightValue": "ok",
                                "operator": {"type": "string", "operation": "notEquals"}
                            }
                        ],
                        "combinator": "and"
                    }
                },
                "id": "if-1",
                "name": "Failed?",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2.2,
                "position": [880, 300],
            },
            {
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "alert_subject",
                             "value": "=Cortex poll FAILED ({{$json.exit_code}}) — {{$json.finished_at}}"},
                            {"name": "alert_body",
                             "value": "=Exit code: {{$json.exit_code}}\nDuration: {{$json.duration_seconds}}s\nLog tail:\n{{$json.notes_log_tail}}"}
                        ]
                    },
                    "options": {}
                },
                "id": "set-1",
                "name": "Format alert",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [1200, 220],
            }
        ],
        "connections": {
            "Every hour":    {"main": [[{"node": "Poll Cortex",  "type": "main", "index": 0}]]},
            "Poll Cortex":   {"main": [[{"node": "Failed?",      "type": "main", "index": 0}]]},
            "Failed?":       {"main": [[{"node": "Format alert", "type": "main", "index": 0}], []]},
        },
        "settings": {
            "executionOrder": "v1",
            "saveExecutionProgress": True,
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
    }


def build_repo_review_workflow(webhook_url: str, webhook_secret: str) -> dict:
    """Daily trigger -> POST /repo-review -> log. Fires at 03:00 PT."""
    return {
        "name": WORKFLOW_NAME_REPO_REVIEW,
        "nodes": [
            {
                "parameters": {
                    "rule": {"interval": [{"field": "days", "daysInterval": 1,
                                           "triggerAtHour": 3,
                                           "triggerAtMinute": 0}]}
                },
                "id": "trigger-1",
                "name": "Daily at 03:00",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [240, 300],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": webhook_url,
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "X-Webhook-Secret", "value": webhook_secret},
                            {"name": "Content-Type", "value": "application/json"},
                        ]
                    },
                    "options": {
                        "timeout": 3600000,   # 1 hr — repo cloning + Sonnet can be slow
                        "response": {"response": {"neverError": True}},
                    },
                },
                "id": "http-1",
                "name": "Review Repos",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [560, 300],
            },
            {
                "parameters": {
                    "conditions": {
                        "options": {"caseSensitive": True, "typeValidation": "loose"},
                        "conditions": [
                            {
                                "id": "cond-1",
                                "leftValue": "={{ $json.status }}",
                                "rightValue": "ok",
                                "operator": {"type": "string", "operation": "notEquals"},
                            }
                        ],
                        "combinator": "and",
                    }
                },
                "id": "if-1",
                "name": "Failed?",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2.2,
                "position": [880, 300],
            },
        ],
        "connections": {
            "Daily at 03:00": {"main": [[{"node": "Review Repos", "type": "main", "index": 0}]]},
            "Review Repos":   {"main": [[{"node": "Failed?",      "type": "main", "index": 0}]]},
        },
        "settings": {
            "executionOrder": "v1",
            "saveExecutionProgress": True,
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
    }


def build_lint_workflow(webhook_url: str, webhook_secret: str) -> dict:
    """Daily wiki lint at 02:00 PT — one hour before the repo review."""
    return {
        "name": WORKFLOW_NAME_LINT,
        "nodes": [
            {
                "parameters": {
                    "rule": {"interval": [{"field": "days", "daysInterval": 1,
                                           "triggerAtHour": 2,
                                           "triggerAtMinute": 0}]}
                },
                "id": "trigger-1",
                "name": "Daily at 02:00",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [240, 300],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": webhook_url,
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "X-Webhook-Secret", "value": webhook_secret},
                            {"name": "Content-Type", "value": "application/json"},
                        ]
                    },
                    "options": {
                        "timeout": 1800000,
                        "response": {"response": {"neverError": True}},
                    },
                },
                "id": "http-1",
                "name": "Lint Wiki",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [560, 300],
            },
            {
                "parameters": {
                    "conditions": {
                        "options": {"caseSensitive": True, "typeValidation": "loose"},
                        "conditions": [
                            {
                                "id": "cond-1",
                                "leftValue": "={{ $json.status }}",
                                "rightValue": "ok",
                                "operator": {"type": "string", "operation": "notEquals"},
                            }
                        ],
                        "combinator": "and",
                    }
                },
                "id": "if-1",
                "name": "Failed?",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2.2,
                "position": [880, 300],
            },
        ],
        "connections": {
            "Daily at 02:00": {"main": [[{"node": "Lint Wiki", "type": "main", "index": 0}]]},
            "Lint Wiki":      {"main": [[{"node": "Failed?",   "type": "main", "index": 0}]]},
        },
        "settings": {
            "executionOrder": "v1",
            "saveExecutionProgress": True,
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
    }


def find_existing(api_key: str, name: str = WORKFLOW_NAME) -> dict | None:
    r = requests.get(f"{N8N_BASE}/workflows", headers=_headers(api_key),
                     verify=False, timeout=15)
    r.raise_for_status()
    for wf in r.json().get("data", []):
        if wf.get("name") == name:
            return wf
    return None


def build_github_scan_workflow(webhook_url: str, webhook_secret: str) -> dict:
    """Hourly trigger -> POST /github-scan -> log."""
    return {
        "name": WORKFLOW_NAME_GITHUB,
        "nodes": [
            {
                "parameters": {
                    "rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}
                },
                "id": "trigger-1",
                "name": "Every hour",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [240, 300],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": webhook_url,
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "X-Webhook-Secret", "value": webhook_secret},
                            {"name": "Content-Type", "value": "application/json"},
                        ]
                    },
                    "options": {
                        "timeout": 1800000,
                        "response": {"response": {"neverError": True}},
                    },
                },
                "id": "http-1",
                "name": "Scan GitHub",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [560, 300],
            },
            {
                "parameters": {
                    "conditions": {
                        "options": {"caseSensitive": True, "typeValidation": "loose"},
                        "conditions": [
                            {
                                "id": "cond-1",
                                "leftValue": "={{ $json.status }}",
                                "rightValue": "ok",
                                "operator": {"type": "string", "operation": "notEquals"},
                            }
                        ],
                        "combinator": "and",
                    }
                },
                "id": "if-1",
                "name": "Failed?",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2.2,
                "position": [880, 300],
            },
        ],
        "connections": {
            "Every hour":  {"main": [[{"node": "Scan GitHub", "type": "main", "index": 0}]]},
            "Scan GitHub": {"main": [[{"node": "Failed?",     "type": "main", "index": 0}]]},
        },
        "settings": {
            "executionOrder": "v1",
            "saveExecutionProgress": True,
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--webhook-url",
                        default="http://10.100.254.200:8765/poll",
                        help="Cortex webhook URL n8n will POST to")
    parser.add_argument("--webhook-secret",
                        default=os.environ.get("WEBHOOK_SECRET", ""),
                        help="Shared secret (defaults to $WEBHOOK_SECRET)")
    parser.add_argument("--workflow",
                        choices=["mail", "github", "repo-review", "lint", "all"],
                        default="all",
                        help="Which workflow(s) to upsert (default: all)")
    parser.add_argument("--github-scan-url",
                        default="http://10.100.254.200:8765/github-scan",
                        help="Cortex /github-scan endpoint")
    parser.add_argument("--repo-review-url",
                        default="http://10.100.254.200:8765/repo-review",
                        help="Cortex /repo-review endpoint")
    parser.add_argument("--lint-url",
                        default="http://10.100.254.200:8765/lint",
                        help="Cortex /lint endpoint")
    args = parser.parse_args()

    if not args.webhook_secret:
        raise SystemExit("WEBHOOK_SECRET env var (or --webhook-secret) required")

    api_key = _api_key()

    targets = []
    if args.workflow in ("mail", "all"):
        targets.append((WORKFLOW_NAME,
                        build_workflow(args.webhook_url, args.webhook_secret)))
    if args.workflow in ("github", "all"):
        targets.append((WORKFLOW_NAME_GITHUB,
                        build_github_scan_workflow(args.github_scan_url,
                                                   args.webhook_secret)))
    if args.workflow in ("repo-review", "all"):
        targets.append((WORKFLOW_NAME_REPO_REVIEW,
                        build_repo_review_workflow(args.repo_review_url,
                                                   args.webhook_secret)))
    if args.workflow in ("lint", "all"):
        targets.append((WORKFLOW_NAME_LINT,
                        build_lint_workflow(args.lint_url,
                                            args.webhook_secret)))

    if args.dry_run:
        for name, wf in targets:
            print(f"\n# === {name} ===")
            print(json.dumps(wf, indent=2))
        return

    for name, wf in targets:
        existing = find_existing(api_key, name)
        if existing:
            wf_id = existing["id"]
            r = requests.put(f"{N8N_BASE}/workflows/{wf_id}",
                             headers=_headers(api_key), json=wf,
                             verify=False, timeout=30)
            r.raise_for_status()
            print(f"Updated workflow id={wf_id}: {name}")
        else:
            r = requests.post(f"{N8N_BASE}/workflows",
                              headers=_headers(api_key), json=wf,
                              verify=False, timeout=30)
            r.raise_for_status()
            wf_id = r.json().get("id", "?")
            print(f"Created workflow id={wf_id}: {name}")

        try:
            r = requests.post(f"{N8N_BASE}/workflows/{wf_id}/activate",
                              headers=_headers(api_key), verify=False, timeout=15)
            if r.ok:
                print(f"  Activated.")
            else:
                print(f"  Activate returned {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            print(f"  Activate failed: {exc}")

        print(f"  UI: https://n8n.ai.technijian.com/workflow/{wf_id}")


if __name__ == "__main__":
    main()
