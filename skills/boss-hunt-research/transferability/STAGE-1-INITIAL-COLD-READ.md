# Stage 1 Initial Cold Read

**Artifact tested:** candidate 1.0.0 draft  
**Date:** 2026-08-21  
**Method:** author-side cold read against the defined competent user, before independent Stage 2 testing

| Gap | Section | Patch |
|---|---|---|
| The reader could not tell whether the old documented `tracker_id` should be renamed, copied, or treated as authority. | Pre-flight / process | Canonicalized `target_id`, added optional `source_tracker_id`, target schema, and a fixture that executes without translation. |
| Non-working Hunter/profile access had no precise distinction or result ceiling. | Adaptations | Added the six-state dependency/capability contract and exact fallback/blocker results. |
| The sequence could be read as permitting Hunter before currentness and hook quality were established. | Core Workflow | Added ordered planner gates and mechanical Hunter preconditions after guards, route, currentness, hook/proof, and first-party miss/block. |
| The user could reasonably assume V2 should be upgraded in place. | Version / compatibility | Preserved the V2 schema, added explicit `LEGACY_SCHEMA_REFUSED`, and prohibited rewriting or re-hashing frozen history. |

All four gaps were patched before Stage 2. The canonical documented target now runs exactly as written.
