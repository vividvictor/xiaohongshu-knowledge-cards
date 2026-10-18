# Codex / WorkBuddy 运行时兼容

需要生图、选择 Python 或处理缺失能力时读取本文件。按能力检测，不按产品名称猜测。

## 生图能力选择

1. 用户在当前请求中指定了生图后端时，使用该后端。
2. 否则检查当前运行时实际提供的原生图片生成 skill 或工具：
   - Codex 常见为 `imagegen` skill 和对应图片生成工具；先读该 skill 的 `SKILL.md`，按其接口调用。
   - WorkBuddy 常见为内置 ImageGen 或同等图片生成能力；按当前工具说明调用。
3. 不要在跨运行时 skill 中写死某个伪函数签名。实际参数、尺寸名称和返回路径以当前工具为准。
4. 没有生图能力时，封面降级为 `code-graphic` 或 `typographic`，并向用户说明；不要伪造 `image_path`。

生成图只提供视觉层。标题、正文、页码、数字和标签全部由 Pillow 合成。

## 封面生成

封面必须先完成主题分析，再调用生图：

1. 从源内容提取具体主题词、核心动作/冲突、结果意象和情绪。
2. 保存 1—4 个源内容 `theme_keywords`，再形成 `visual_concept`。概念必须对当前主题具有排他性，不能替换成任意文章仍成立。
3. 形成 `image_prompt`：主题概念 + 系列风格 + 三色 palette + 3:4 构图 + 底部标题安全区 + 禁止任何文字。
4. 生成图片，保存到 deck JSON 同级或子目录，再填写相对 `image_path`。

内容页和结尾页可以使用 AI 图，但不是强制。只有图片能解释机制、空间关系、过程或隐喻时才使用；纯装饰图应省略。

## Python 与 Pillow

优先使用当前宿主已经提供且能 `import PIL` 的 Python。可先只读检查：

```bash
python -c "from PIL import Image; print(Image.__version__)"
```

若失败：

- Codex 可查询宿主提供的 workspace Python/依赖路径。
- WorkBuddy 可检查其项目或隔离 venv 的 Python。
- 不自行安装全局依赖。需要安装 Pillow 时，说明目标解释器和命令，并遵守当前项目的授权规则。

渲染器会在 Windows、macOS、Linux 上自动寻找常见中文字体；也可用 `--font` 和 `--font-bold` 显式指定。找不到中文字体时应报错停止，不能输出豆腐块。

## 路径与命令

- 文档中的路径使用 `/`，Python `Path` 负责平台差异。
- 不假设当前工作目录就是 skill 目录；根据已加载 skill 的实际路径定位脚本。
- `image_path` 相对输入 JSON 所在目录解析。
- 输出保留在用户指定目录；不要写入宿主安装目录。

## WorkBuddy 元数据

Codex 的校验器只允许开放 Agent Skills 顶层字段，而 WorkBuddy Marketplace 发布格式另有顶层必填字段。为保证同一源目录能被 Codex 和本地 WorkBuddy 共用：

- 顶层只使用 `name`、`description` 和 `metadata`。
- WorkBuddy 的双语展示信息、版本与作者放在 `metadata.workbuddy`。
- Codex 专用 UI 元数据放在 `agents/openai.yaml`；WorkBuddy 可忽略该文件。
- 如果用户明确要求发布到 WorkBuddy Marketplace，再从这份源 skill 生成平台专用发布包；不要为发布格式破坏 Codex 源 skill 的校验。
