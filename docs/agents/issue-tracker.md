# Issue tracker: GitHub

Issues and specifications for this repository live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- Create an issue with `gh issue create --title "..." --body "..."`.
- Read an issue with `gh issue view <number> --comments`.
- List issues with `gh issue list`, using appropriate `--label` and `--state` filters.
- Comment with `gh issue comment <number> --body "..."`.
- Apply or remove labels with `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Close an issue with `gh issue close <number> --comment "..."`.

Infer the repository from `git remote -v`; `gh` does this automatically when run inside this clone.

## Pull requests as a triage surface

PRs as a request surface: no.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

- A map is a GitHub issue labelled `wayfinder:map`; child tickets are GitHub sub-issues where available.
- Child tickets use one `wayfinder:<type>` label: `research`, `prototype`, `grilling`, or `task`.
- Use native GitHub issue dependencies for blocking relationships. If unavailable, place `Blocked by: #<number>` at the top of the child issue body.
- Claim a ticket before work with `gh issue edit <number> --add-assignee @me`.
- Resolve a ticket by posting its decision as a comment, closing it, then adding a linked one-line summary to the map's Decisions so far section.
