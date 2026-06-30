# AGENTS.md

## 关于本目录

本目录用于维护本地 Codex skill 和相关验证脚本。默认语言为中文，代码、命令、变量名使用英文。

## 工作规则

- 新增或调整目录结构前，先更新本文件中的规则，再按规则实践。
- 不删除文件、目录或 Git 历史，除非用户明确要求。
- 不修改 `.env`、密钥、token、CI/CD 配置。
- 不执行 `git push`、`git rebase`、`git reset --hard`、强制推送。
- 不安装新的全局依赖，不修改系统配置。
- 改完必须主动运行相关验证命令，并在回复中说明验证结果。

## Skill 结构约定

- 每个 skill 使用独立目录，目录名与 skill 名一致，使用小写字母、数字和连字符。
- 每个 skill 必须包含 `SKILL.md`。
- 面向 Codex UI 的元数据放在 `agents/openai.yaml`。
- 可执行辅助工具放在 `scripts/`。
- 需要按需加载的详细说明放在 `references/`。
- 不为 skill 额外创建 README、安装指南或变更日志，除非用户明确要求。

## 验证约定

- 新建或修改 skill 后，运行 `skill-creator` 的 `quick_validate.py`。
- 新增脚本后，运行对应测试或示例命令。
- 涉及图片生成或渲染时，至少验证输出文件存在、尺寸正确、中文字体可渲染。
