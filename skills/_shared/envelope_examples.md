# Standalone envelope recipes (2.2.2 / 3.2.2)

Use `python3 scripts/runtime_cli.py new-envelope ROOT` from this package first.
It derives skill/version and a helper-stamped start from the snapshot. The
skeleton deliberately fails validation while either external state is
`unprobed`; discover services, record the observed four-state result, then
validate. Examples below are synthetic shapes, not evidence to copy into a
live invocation. Replace the entire local snapshot with constructor output.

Routine unavailable opening: set both services to their observed non-working
states; retain empty scope and approval false. Current opening: set intended
`project`, observed working state, matching receipt identity and actual rows.
Closing draft: add M2 paths and exact M3 operations; validate before scope is
added, then freeze. A draft with unapproved scope correctly fails only
SCOPE_UNAPPROVED. Closing approved: run approve-draft with exact scope_lines,
copy that string into approval, retain the original snapshot and validate.
For index-only opening omit entry and pass `--index-draft INDEX`. Opening has no
task creation or pending/capture mutation scope. A close may include
"pending_learnings.md" beside the session/index in M2; it renders optional stage
permission (or use {"path":"pending_learnings.md","operation":"stage"}).
Pending-only scopes default to replace. Explicit delete is never auto-added;
archive scopes also render only requested operations. Each later independent
chain uses new-envelope for both timestamps; capture over fifteen minutes after
start refuses ESTALEEVIDENCE. Never copy an earlier start. Each pending
edit/disposition/delete needs non-empty `write-approved --owner-reply "<words>"`
and current `--expect`; approvals older than six hours cannot authorize a revision.
Stage uses the close approval once after append verification:
`write-approved ENVELOPE RECEIPT pending_learnings.md CONTENT --operation stage
--expect <current-sha256|absent>`. Preserve all current bytes and append only
new candidate blocks; read back before showing them. Keep needs no write.
For other dispositions show their frozen scope_lines with the question.

The static timestamps below demonstrate shapes and are stale for new work.
Use constructor timestamps (including captured_at), actual observed receipts
and helper approvals in a live invocation; new evidence has a six-hour lifetime.
Only bound interrupted recovery reuses its original receipt; see recovery.md for
`freeze-draft --continue <parent-intent>` and unfinished child abandonment.

The four complete envelopes below demonstrate nesting: schema_version belongs
at the envelope, capability_profile and every MCP receipt, not inside local
booleans or external state values. Times require timezone offsets; 120 seconds
is allowed in both directions. Never type live start/approval timestamps.

## Opening unavailable

```json
{
  "schema_version": "1.0",
  "invocation_id": "inv-0001",
  "invocation_started_at": "2026-08-03T22:00:00Z",
  "skill": "newbeginning",
  "workspace_root": "/w",
  "project": "Synthetic",
  "capability_profile": {
    "schema_version": "1.0",
    "local": {
      "shell_available": true,
      "git_available": true,
      "temporary_workspace_available": true,
      "parallel_read_only_available": true
    },
    "external": {
      "tasks_mcp": "absent",
      "open_brain": "absent"
    },
    "external_detail": {
      "tasks_mcp": {
        "project_ref": null
      },
      "open_brain": {
        "reason": "no capture_thought in tool list"
      }
    }
  },
  "local_snapshot": {
    "workspace_root": "/w",
    "observed_at": "2026-08-03T22:00:00Z",
    "index": {
      "path": "project_index.md",
      "sha256": "aaa",
      "mtime": "...",
      "words": 412
    },
    "session": {
      "path": "project_session.md",
      "tail_sha256": "bbb",
      "latest_session_number": 38
    },
    "pending_learnings": {
      "present": false
    },
    "git": {
      "available": false
    },
    "sync_conflicts": [],
    "projection_bytes_emitted": 3184,
    "local_date": "2026-08-03",
    "local_utc_offset": "-06:00",
    "unfinished_operations": []
  },
  "mcp_receipts": [
    {
      "schema_version": "1.0",
      "capability": "tasks_mcp",
      "identity": {
        "project_ref": null,
        "view": "task_urgency",
        "project": "Synthetic"
      },
      "tool_result_id": null,
      "observed_at": "2026-08-03T22:31:04Z",
      "operation_fingerprint": "sha256:query-task-urgency-open-project",
      "row_fingerprint": null,
      "row_count": 0,
      "status": "unavailable",
      "capability_state": "absent"
    }
  ],
  "mutation_scope": {
    "M2": [],
    "M3": [],
    "M4": []
  },
  "approval": {
    "granted": false,
    "scope_string": null
  },
  "source_hashes_used_for_draft": {
    "index": "aaa",
    "session_tail": "bbb"
  },
  "skill_version": "2.2.2",
  "returned_rows_by_capability": {}
}
```

## Opening current

```json
{
  "schema_version": "1.0",
  "invocation_id": "inv-0001",
  "invocation_started_at": "2026-08-03T22:00:00Z",
  "skill": "newbeginning",
  "workspace_root": "/w",
  "project": "Synthetic",
  "capability_profile": {
    "schema_version": "1.0",
    "local": {
      "shell_available": true,
      "git_available": true,
      "temporary_workspace_available": true,
      "parallel_read_only_available": true
    },
    "external": {
      "tasks_mcp": "working",
      "open_brain": "absent"
    },
    "external_detail": {
      "tasks_mcp": {
        "project_ref": "proj-ref-placeholder"
      },
      "open_brain": {
        "reason": "no capture_thought in tool list"
      }
    }
  },
  "local_snapshot": {
    "workspace_root": "/w",
    "observed_at": "2026-08-03T22:00:00Z",
    "index": {
      "path": "project_index.md",
      "sha256": "aaa",
      "mtime": "...",
      "words": 412
    },
    "session": {
      "path": "project_session.md",
      "tail_sha256": "bbb",
      "latest_session_number": 38
    },
    "pending_learnings": {
      "present": false
    },
    "git": {
      "available": false
    },
    "sync_conflicts": [],
    "projection_bytes_emitted": 3184,
    "local_date": "2026-08-03",
    "local_utc_offset": "-06:00",
    "unfinished_operations": []
  },
  "mcp_receipts": [
    {
      "schema_version": "1.0",
      "capability": "tasks_mcp",
      "identity": {
        "project_ref": "proj-ref-placeholder",
        "view": "task_urgency",
        "project": "Synthetic"
      },
      "tool_result_id": "tr-0001",
      "observed_at": "2026-08-03T22:31:04Z",
      "operation_fingerprint": "sha256:query-task-urgency-open-project",
      "row_fingerprint": "sha256:1fea3c68e64b039d9323f5264ecec3a0ec789ab499db9b863e7c437e3ca17b32",
      "row_count": 2,
      "status": "current"
    }
  ],
  "mutation_scope": {
    "M2": [],
    "M3": [],
    "M4": []
  },
  "approval": {
    "granted": false,
    "scope_string": null
  },
  "source_hashes_used_for_draft": {
    "index": "aaa",
    "session_tail": "bbb"
  },
  "skill_version": "2.2.2",
  "returned_rows_by_capability": {
    "tasks_mcp": [
      {
        "id": "task-aaaa",
        "title": "First synthetic task",
        "priority": 1,
        "status": "open",
        "project": "Synthetic"
      },
      {
        "id": "task-bbbb",
        "title": "Second synthetic task",
        "priority": 2,
        "status": "open",
        "project": "Synthetic"
      }
    ]
  }
}
```

## Closing draft

```json
{
  "schema_version": "1.0",
  "invocation_id": "inv-0001",
  "invocation_started_at": "2026-08-03T22:00:00Z",
  "skill": "closingtime",
  "workspace_root": "/w",
  "project": "Synthetic",
  "capability_profile": {
    "schema_version": "1.0",
    "local": {
      "shell_available": true,
      "git_available": true,
      "temporary_workspace_available": true,
      "parallel_read_only_available": true
    },
    "external": {
      "tasks_mcp": "working",
      "open_brain": "absent"
    },
    "external_detail": {
      "tasks_mcp": {
        "project_ref": "proj-ref-placeholder"
      },
      "open_brain": {
        "reason": "no capture_thought in tool list"
      }
    }
  },
  "local_snapshot": {
    "workspace_root": "/w",
    "observed_at": "2026-08-03T22:00:00Z",
    "index": {
      "path": "project_index.md",
      "sha256": "aaa",
      "mtime": "...",
      "words": 412
    },
    "session": {
      "path": "project_session.md",
      "tail_sha256": "bbb",
      "latest_session_number": 38
    },
    "pending_learnings": {
      "present": false
    },
    "git": {
      "available": false
    },
    "sync_conflicts": [],
    "projection_bytes_emitted": 3184,
    "local_date": "2026-08-03",
    "local_utc_offset": "-06:00",
    "unfinished_operations": []
  },
  "mcp_receipts": [
    {
      "schema_version": "1.0",
      "capability": "tasks_mcp",
      "identity": {
        "project_ref": "proj-ref-placeholder",
        "view": "task_urgency",
        "project": "Synthetic"
      },
      "tool_result_id": "tr-0001",
      "observed_at": "2026-08-03T22:31:04Z",
      "operation_fingerprint": "sha256:query-task-urgency-open-project",
      "row_fingerprint": "sha256:1fea3c68e64b039d9323f5264ecec3a0ec789ab499db9b863e7c437e3ca17b32",
      "row_count": 2,
      "status": "current"
    }
  ],
  "mutation_scope": {
    "M2": [
      "project_session.md"
    ],
    "M3": [],
    "M4": []
  },
  "approval": {
    "granted": false,
    "scope_string": null
  },
  "source_hashes_used_for_draft": {
    "index": "aaa",
    "session_tail": "bbb"
  },
  "skill_version": "3.2.2",
  "returned_rows_by_capability": {
    "tasks_mcp": [
      {
        "id": "task-aaaa",
        "title": "First synthetic task",
        "priority": 1,
        "status": "open",
        "project": "Synthetic"
      },
      {
        "id": "task-bbbb",
        "title": "Second synthetic task",
        "priority": 2,
        "status": "open",
        "project": "Synthetic"
      }
    ]
  }
}
```

## Closing approved

```json
{
  "schema_version": "1.0",
  "invocation_id": "inv-0001",
  "invocation_started_at": "2026-08-03T22:00:00Z",
  "skill": "closingtime",
  "workspace_root": "/w",
  "project": "Synthetic",
  "capability_profile": {
    "schema_version": "1.0",
    "local": {
      "shell_available": true,
      "git_available": true,
      "temporary_workspace_available": true,
      "parallel_read_only_available": true
    },
    "external": {
      "tasks_mcp": "working",
      "open_brain": "absent"
    },
    "external_detail": {
      "tasks_mcp": {
        "project_ref": "proj-ref-placeholder"
      },
      "open_brain": {
        "reason": "no capture_thought in tool list"
      }
    }
  },
  "local_snapshot": {
    "workspace_root": "/w",
    "observed_at": "2026-08-03T22:00:00Z",
    "index": {
      "path": "project_index.md",
      "sha256": "aaa",
      "mtime": "...",
      "words": 412
    },
    "session": {
      "path": "project_session.md",
      "tail_sha256": "bbb",
      "latest_session_number": 38
    },
    "pending_learnings": {
      "present": false
    },
    "git": {
      "available": false
    },
    "sync_conflicts": [],
    "projection_bytes_emitted": 3184,
    "local_date": "2026-08-03",
    "local_utc_offset": "-06:00",
    "unfinished_operations": []
  },
  "mcp_receipts": [
    {
      "schema_version": "1.0",
      "capability": "tasks_mcp",
      "identity": {
        "project_ref": "proj-ref-placeholder",
        "view": "task_urgency",
        "project": "Synthetic"
      },
      "tool_result_id": "tr-0001",
      "observed_at": "2026-08-03T22:31:04Z",
      "operation_fingerprint": "sha256:query-task-urgency-open-project",
      "row_fingerprint": "sha256:1fea3c68e64b039d9323f5264ecec3a0ec789ab499db9b863e7c437e3ca17b32",
      "row_count": 2,
      "status": "current"
    }
  ],
  "mutation_scope": {
    "M2": [
      "project_session.md"
    ],
    "M3": [],
    "M4": []
  },
  "approval": {
    "granted": true,
    "scope_string": "M2 append project_session.md (+ journal receipt under private-artifacts/session-journal/)"
  },
  "source_hashes_used_for_draft": {
    "index": "aaa",
    "session_tail": "bbb"
  },
  "skill_version": "3.2.2",
  "returned_rows_by_capability": {
    "tasks_mcp": [
      {
        "id": "task-aaaa",
        "title": "First synthetic task",
        "priority": 1,
        "status": "open",
        "project": "Synthetic"
      },
      {
        "id": "task-bbbb",
        "title": "Second synthetic task",
        "priority": 2,
        "status": "open",
        "project": "Synthetic"
      }
    ]
  }
}
```

## Receipt shapes

Current Tasks: identity includes intended project plus service project_ref; current
Open Brain: identity carries observed service/account/project_ref as applicable,
consistent with external_detail. Both carry actual returned rows and recomputed
fingerprint/count. Unavailable: status unavailable, capability_state one of the
three non-working states, row_fingerprint null; error/conflicted shapes use the
same non-current fields with their status and never grant authority.

Use fingerprint-operation on the exact query text and fingerprint-rows on the
actual result. After Tasks mutations attach a freshly validated current
`mirror_receipt` to the approved envelope, preserving the frozen snapshot, and
pass its actual rows via write-approved --mirror-rows. The original receipt
remains observation evidence. Archive payloads require local_payload_hashes
with their exact SHA-256 before freeze; pending revisions carry payload hashes
in individual durable transition intents and record owner_reply per revision.
