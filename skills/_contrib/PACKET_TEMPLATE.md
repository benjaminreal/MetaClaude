# Evidence packet: <change-id>

**Implementer:** <harness / model / session id>
**Branch:** contrib/<change-id>
**Base:** <full sha>
**Commit:** <full sha of the commit to install>
**Level:** <1 | 2 | 3>
**Skills and versions:** <skill> <old> -> <new>[, …]

## What changed

One line per file or group of files, and the reason for each.

## Tests added first

| Test | Fails on base (command and result) | Passes on commit (command and result) |
|---|---|---|

## Gate

`GATE.json`: verdict, head and tool hash. Paste the summary lines.

## Standards checklist

For each section of STANDARDS.md §4 (A–G): "followed", or the exact exception
with the owner's approval quoted.

## Not verified

Everything you could not check, and why. Do not leave this empty if anything
was skipped.

## External model runs

Model, route, purpose, whether the data was private, request count, cost, or
"none".
