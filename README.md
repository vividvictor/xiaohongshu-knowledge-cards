# 小红书知识卡片 Skill

这是一个 Codex skill，用于把文章、笔记、提纲或主题生成 3:4 多页小红书知识卡片 PNG。

它的重点不是把长文机械分页，而是先提炼读者收益和传播角度，再用列表、流程、对比、重点框、引用等结构，把一个观点做成更容易看完、记住和转发的卡片组。

## 特点

- 固定输出 3:4 竖版卡片，默认尺寸 `1080x1440`。
- 自动生成封面页、内容页和结尾页。
- 不单独调用生图，封面和内容视觉通过代码绘制的数据可视化、几何图形、排版和文字格式完成。
- 整套卡片颜色不超过 3 种。
- 默认使用较粗的中文非衬线字体。
- 内容页页码使用纯数字格式，例如 `02/06`。
- 渲染后生成 `manifest.json`，记录页数、尺寸、调色板、页码、字体风格和视觉来源。

## 目录结构

```text
xiaohongshu-knowledge-cards/
  SKILL.md
  agents/
    openai.yaml
  references/
    card-content-schema.md
  scripts/
    render_cards.py
tests/
  test_render_cards.py
```

## 安装方法

把本仓库克隆到本地后，将 skill 目录复制到 Codex skills 目录。

Windows PowerShell 示例：

```powershell
git clone https://github.com/vividvictor/xiaohongshu-knowledge-cards.git
Copy-Item -Recurse -Force `
  .\xiaohongshu-knowledge-cards\xiaohongshu-knowledge-cards `
  $env:USERPROFILE\.codex\skills\xiaohongshu-knowledge-cards
```

如果你的 `CODEX_HOME` 不是默认位置，把目标路径换成：

```powershell
$env:CODEX_HOME\skills\xiaohongshu-knowledge-cards
```

安装后，在 Codex 中可以用类似下面的请求触发：

```text
使用 $xiaohongshu-knowledge-cards 把这篇文章生成小红书知识卡片
```

## 直接使用渲染脚本

也可以不安装 skill，直接用脚本把 JSON 渲染成 PNG。

生成内置示例：

```powershell
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py `
  --sample `
  --out .\output\sample-cards
```

使用自己的 JSON：

```powershell
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py `
  --input .\cards.json `
  --out .\output\cards
```

指定 manifest 输出位置：

```powershell
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py `
  --input .\cards.json `
  --out .\output\cards `
  --manifest .\output\cards\checks.json
```

## JSON 样例

```json
{
  "title": "把知识变成行动",
  "subtitle": "从文章到卡片的3步表达法",
  "audience": "想把长内容做成小红书卡片的人",
  "promise": "用一条主线把知识压缩成可看完、可记住、可复述的卡片组",
  "angle": "从传播目标倒推卡片结构，而不是把原文机械分页",
  "visual_brief": "抽象的信息流、结构重组和行动路径",
  "palette": {
    "background": "#F9F5EF",
    "text": "#1F2933",
    "accent": "#D94A38"
  },
  "pages": [
    {
      "type": "cover",
      "title": "把知识变成行动",
      "subtitle": "从文章到卡片的3步表达法"
    },
    {
      "type": "content",
      "section_title": "先抓主线",
      "blocks": [
        {
          "type": "callout",
          "title": "核心判断",
          "text": "卡片不是压缩全文，而是提炼一条可传播的认知路径。"
        },
        {
          "type": "steps",
          "items": ["找问题", "给框架", "落行动"]
        }
      ]
    },
    {
      "type": "ending",
      "title": "最后记住这句话",
      "summary": ["知识卡片的目标不是完整，而是让人愿意看完并记住。"],
      "quote": "能被复述的知识，才真正完成了传播。"
    }
  ],
  "quality_checks": [
    "每页只表达一个核心意思",
    "整套卡片颜色不超过 3 种"
  ]
}
```

## 支持的内容模块

- `paragraph`：短段落。
- `bullet_list`：并列要点。
- `numbered_list`：编号列表。
- `steps`：步骤流程。
- `flow`：因果、递进、前后变化。
- `comparison`：左右对比。
- `quote`：金句或强记忆点。
- `callout`：重点提醒或核心判断。

## 输出文件

渲染后输出目录会包含：

```text
page-01.png
page-02.png
page-03.png
manifest.json
```

`manifest.json` 会记录：

- 标题、受众、承诺和编辑角度。
- 输出尺寸和总页数。
- 调色板。
- 每页类型和文件名。
- 内容页页码，例如 `02/06`。
- 字体风格：`bold-sans`。
- 封面视觉来源：`code-graphic`。

## 验证

修改 skill 或脚本后，建议运行：

```powershell
python -m unittest tests.test_render_cards
python -X utf8 C:\Users\1\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\xiaohongshu-knowledge-cards
```

如果使用的是 Codex bundled Python，也可以把 `python` 换成你的本地 Python 路径。`quick_validate.py` 需要可用的 `yaml` 模块。
