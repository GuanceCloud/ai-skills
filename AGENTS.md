# Repository Collaboration Guidelines

- Always respond in Simplified Chinese.
- When the user explicitly says "commit code", execute the process directly instead of only giving suggestions:
  1. Check `git status`, `git diff`, and changed files to confirm the commit scope.
  2. Update `README.md` when directories, Skills, scripts, commands, dependencies, or collaboration rules are added or removed.
  3. If `README.md` is not changed because repository usage or collaboration behavior is unaffected, state the reason in the final response.
  4. Stage the intended files and avoid missing related changes.
  5. Create a clear commit message, using Chinese by default when appropriate.
  6. Add the fixed trailer: `Generated-by: OpenAI Codex`.
  7. Push to the current branch upstream by default; if no upstream exists, run `git push -u origin <current-branch>`.
- If the user only says "commit code" without more detail, commit all current workspace changes related to this task by default.
