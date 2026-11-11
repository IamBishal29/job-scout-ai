---
name: next-task
description: Pick up the next JobPilot backlog issue and take it through plan, build, test, pull request and a learning note.
---

1. Read PROGRESS.md.
   - A branch is in progress: switch to it and resume from "Next step".
   - Otherwise: `git switch main && git pull`, then pick the lowest-numbered open issue
     in the current milestone (`gh issue list --milestone "<name>"`).
   Tell me in one line which issue and why.
2. Plan in under 10 lines: files to touch, approach, the concept involved.
   If there is a real decision (see CLAUDE.md "When to ask me"), ask with
   AskUserQuestion. Otherwise continue without waiting.
3. Create the branch, implement in small commits, add or update tests, and run lint and
   tests until they pass.
4. Write `docs/learning/NN-topic.md` for the concept and commit it on the same branch.
5. Push and open the PR with `gh pr create` (Closes #n, summary, how to test).
6. Update PROGRESS.md (done, next issue, open questions for me), commit, push.
7. Finish with: the PR link, a 5-line concept summary, and what I should check in
   "Files changed" before merging.
