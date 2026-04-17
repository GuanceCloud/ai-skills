# 仓库协作约定

- 始终使用简体中文回复。
- 当用户明确说出“提交代码”时，按以下流程直接执行，不只停留在建议层面：
  1. 查看当前 `git status`、`git diff` 与变更文件，确认本次提交范围。
  2. 根据变更同步 `README.md`：
     - 新增或删除目录、Skill、脚本、命令、依赖、协作规则时，必须更新。
     - 若改动不影响仓库用法或协作方式，可不改，但需要在最终回复中明确说明原因。
  3. 整理暂存区，避免遗漏应提交文件。
  4. 生成清晰的 commit message，默认使用中文，必要时补充 body。
  5. commit 时附加固定 trailer：`Generated-by: OpenAI Codex`。
  6. 默认 push 到当前分支对应的 upstream；若当前分支没有 upstream，则执行 `git push -u origin <current-branch>`。
- 如果用户只说“提交代码”而没有额外说明，默认提交当前工作区内与本次任务相关的全部改动。
