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

Run `gh issue view <number> --comments` for the body, comments, and labels. For tickets whose parent or dependencies matter, also run `gh api repos/<owner>/<repo>/issues/<number>` and inspect `parent_issue_url` and `issue_dependencies_summary`. List specific blockers with `gh api repos/<owner>/<repo>/issues/<number>/dependencies/blocked_by` and downstream dependents with `gh api repos/<owner>/<repo>/issues/<number>/dependencies/blocking`.

## Wayfinding operations

- A map is a GitHub issue labelled `wayfinder:map`; child tickets are GitHub sub-issues where available.
- Child tickets use one `wayfinder:<type>` label: `research`, `prototype`, `grilling`, or `task`.
- List a parent issue's children with `gh api repos/<owner>/<repo>/issues/<number>/sub_issues --paginate`.
- Add a child with `gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>`.
- Remove a child with `gh api --method DELETE repos/<owner>/<repo>/issues/<parent>/sub_issues/<child-db-id>`.
- Use native GitHub issue dependencies for blocking relationships: `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`. Use the numeric database id, obtained with `gh api repos/<owner>/<repo>/issues/<number> --jq .id`, not the issue number or node id. Remove an incorrect edge with `gh api --method DELETE repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by/<blocker-db-id>`. If unavailable, place `Blocked by: #<number>` at the top of the child issue body.
- Claim a ticket before work with `gh issue edit <number> --add-assignee @me`.
- Resolve a ticket by posting its decision as a comment, closing it, then adding a linked one-line summary to the map's Decisions so far section.
