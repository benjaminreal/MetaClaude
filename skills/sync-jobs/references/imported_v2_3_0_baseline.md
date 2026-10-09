# Imported v2.3.0 baseline

The public engine was reconciled from an installation-local v2.3.0 package
before source-acquisition feature work began.

- Cache files and private profile overlays are excluded.
- The pre-feature engine passed its 80-test regression suite.
- Skill validation passed before feature changes.
- Local source paths and private-profile hashes are intentionally omitted from
  this public receipt.

This is historical implementation evidence, not a runtime dependency. The
branch must be rewritten onto the public base before publication so earlier
unpushed commits containing private overlays are not included.
