# 卡片内容 Schema

使用 UTF-8 JSON。

## 顶层字段

- `title`：字符串，必填。用于内容页顶部标题，也作为封面标题兜底。
- `subtitle`：字符串，可选。封面副标题。
- `audience`：字符串，推荐填写。这套卡片面向的读者。
- `promise`：字符串，推荐填写。承诺给读者的有用结果。
- `angle`：字符串，推荐填写。筛选源内容的编辑角度。
- `density`：字符串，可选，默认 `dense`。可用 `dense`、`balanced`、`airy`；同时控制字号、边距、行距、模块间距和 AI 内容图默认高度。
- `visual_brief`：字符串，可选。仅 `code-graphic` 兜底模式使用，描述代码绘制的可视化方向。当前运行时没有生图能力时可填写并把 `visual_mode` 设为 `code-graphic`。
- `visual_mode`：字符串，可选，默认按以下规则解析：
  - `ai-visual` / `ai` / `generated` / `image`：使用 ImageGen 生成的图片，由 Pillow 合成文字。该页必须同时设置 `image_path`。
  - `code-graphic` / `graphic`：使用代码绘制的几何/数据可视化主视觉（通常用于 Codex 兜底）。
  - `typographic` / `none` / `text`：使用纯文字、线条和排版的封面。
  - 不填：若顶层或封面页存在非空 `visual_brief` 则降级 `code-graphic`，否则 `typographic`。
- `visual_ratio`：仅页面字段，可选。`ai-visual` 内容页的图片高度比例，范围 `0.26—0.50`；不填时按 `density` 取 `0.32 / 0.40 / 0.48`。
- `palette`：对象或数组，必填。最多 3 种颜色。
  - 对象键建议使用 `background`、`text`、`accent`。
  - 颜色值必须是类似 `#FFFFFF` 的十六进制颜色。
- `visual_path`：保留字段但渲染器不使用。历史数据兼容。
- `pages`：数组，必填。第一页必须是 `cover`，最后一页必须是 `ending`，中间页必须是 `content`。
- `quality_checks`：数组，推荐填写。交付前要验证的具体检查项。

## 最小完整示例

```json
{
  "title": "把知识变成行动",
  "subtitle": "从文章到卡片的3步表达法",
  "audience": "想把长内容做成小红书卡片的人",
  "promise": "用一条主线把知识压缩成可看完、可记住、可复述的卡片组",
  "angle": "从传播目标倒推卡片结构，而不是把原文机械分页",
  "density": "dense",
  "palette": {
    "background": "#F9F5EF",
    "text": "#1F2933",
    "accent": "#D94A38"
  },
  "pages": [
    {
      "type": "cover",
      "title": "把知识变成行动",
      "subtitle": "从文章到卡片的3步表达法",
      "visual_mode": "ai-visual",
      "kicker": "知识卡片方法论",
      "theme_keywords": ["文章", "知识卡片", "行动"],
      "visual_concept": "散乱的文章纸片经过漏斗重组为三张清晰卡片，并延伸成一条行动路径",
      "image_prompt": "Editorial illustration of article fragments reorganizing into three cards and an action path; no text, no letters; 3:4 vertical.",
      "image_path": "output/assets/cover.png"
    },
    {
      "type": "content",
      "section_title": "先抓主线",
      "blocks": [
        { "type": "callout", "title": "核心判断", "text": "卡片不是压缩全文，而是提炼一条可传播的认知路径。" },
        { "type": "steps", "items": ["找问题", "给框架", "落行动"] }
      ]
    },
    {
      "type": "ending",
      "title": "最后记住这句话",
      "visual_mode": "ai-visual",
      "visual_concept": "完成的知识卡片向外扩散出清晰的同心波纹",
      "image_path": "output/assets/ending.png",
      "summary": ["知识卡片的目标不是完整，而是让人愿意看完并记住。"],
      "quote": "能被复述的知识，才真正完成了传播。"
    }
  ],
  "quality_checks": ["每页只表达一个核心意思", "整套卡片颜色不超过 3 种"]
}
```

## 页面类型

### Cover

```json
{
  "type": "cover",
  "title": "主题标题",
  "subtitle": "一句话说明",
  "visual_mode": "ai-visual",
  "kicker": "左上角小标签",
  "theme_keywords": ["来自源内容的主题词", "核心对象"],
  "visual_concept": "根据当前内容主题提炼的具体主体、动作和结果意象",
  "image_prompt": "实际使用的完整无文字生图提示词",
  "image_path": "output/assets/cover.png"
}
```

封面默认规则：
- 设置 `visual_mode: "ai-visual"` 且提供 `image_path`：用生成图做全屏主视觉，底部暗罩叠白色标题、副标题、底部小字 `知识卡片`。
- 设置 `visual_mode: "code-graphic"`：用代码绘制的几何/数据可视化主视觉；建议同时填写顶层 `visual_brief`。
- 设置 `visual_mode: "typographic"` 或不填且无 `visual_brief`：纯文字 + 线条 + 排版的封面。

AI 封面必须填写 1—4 个 `theme_keywords` 和 `visual_concept`，且概念必须根据本次用户内容的主题动态生成，不能复用固定通用图。`visual_concept` 或 `image_prompt` 至少包含一个主题词。`image_prompt` 推荐保存实际提示词，便于复核。`kicker` 只在 AI 封面生效，会作为左上角半透明胶囊里的品牌小字。

### Content

内容页必须包含 `section_title` 和非空的 `blocks` 数组。如果本页承接上一页，`section_title` 设为 `接上页`。

```json
{
  "type": "content",
  "section_title": "二级标题",
  "visual_mode": "ai-visual",
  "visual_concept": "这张内容图解释的机制或关系",
  "visual_ratio": 0.30,
  "image_path": "output/assets/logic.png",
  "blocks": [
    { "type": "paragraph", "text": "短段落。" },
    { "type": "bullet_list", "items": ["要点一", "要点二"] },
    { "type": "numbered_list", "items": ["第一步", "第二步"] },
    { "type": "steps", "items": ["输入", "处理", "输出"] },
    { "type": "flow", "items": ["问题", "机制", "结果"] },
    { "type": "comparison", "left_title": "误区", "left": ["..."], "right_title": "正确做法", "right": ["..."] },
    { "type": "fact_grid", "items": [{"title": "概念 A", "text": "简短解释"}, {"title": "概念 B", "text": "简短解释"}] },
    { "type": "quote", "text": "一句金句。" },
    { "type": "callout", "title": "关键提醒", "text": "一句重点。" }
  ]
}
```

`ai-visual` 内容页：图片放在顶部，正文放在下方。默认图片比例随 `density` 为 32% / 40% / 48%；高密度页建议 `0.26—0.34`。只有图片能解释机制、关系或过程时才使用此模式。`image_path` 相对 deck JSON 所在目录解析。`code-graphic` / `typographic` 内容页只展示文字与结构化模块。

### Ending

```json
{
  "type": "ending",
  "title": "最后记住这句话",
  "visual_mode": "ai-visual",
  "visual_concept": "与总结直接相关的结果意象",
  "image_path": "output/assets/ending.png",
  "summary": ["总结一", "总结二"],
  "quote": "真正的改变，来自可重复的小动作。"
}
```

结尾页必须包含 `summary` 或 `quote`。`ai-visual` 模式会全屏展示生成图并用底部暗罩叠白字标题、要点、金句。

## 支持的 Blocks

- `paragraph`: `{ "type": "paragraph", "text": "短段落。" }`
- `bullet_list`: `{ "type": "bullet_list", "items": ["要点一", "要点二"] }`
- `numbered_list`: `{ "type": "numbered_list", "items": ["第一步", "第二步"] }`
- `steps`: `{ "type": "steps", "items": ["输入", "处理", "输出"] }`
- `flow`: `{ "type": "flow", "items": ["问题", "机制", "结果"] }`
- `comparison`: `{ "type": "comparison", "left_title": "误区", "left": ["..."], "right_title": "正确做法", "right": ["..."] }`
- `fact_grid`: `{ "type": "fact_grid", "items": [{"title": "术语", "text": "解释"}, "也可直接使用短句"] }`
- `quote`: `{ "type": "quote", "text": "一句金句。" }`
- `callout`: `{ "type": "callout", "title": "关键提醒", "text": "一句重点。" }`

未知 block 类型无效。

## Manifest 输出

渲染器默认写出 `manifest.json`，其中记录：

- `title`、`subtitle`、`audience`、`promise`、`angle`、`visual_brief`
- `density`、`layout_system`、`size`、`page_count`、`palette`、字体路径和字阶标记
- 每页的文件名、页面类型、`visual_source`、可见字符数；内容页另含页码和 block 类型
- 所有 AI 页的 `image_path` 与 `visual_concept`；提供 `image_prompt` 时一并记录
- `quality_checks`

## 写作规则

- 每页只讲一个核心问题，但可以用多个模块讲透。
- `dense` 页建议 5—8 个短要点或约 180—320 个中文字符；优先使用结构化 block，不堆长段落。
- 段落文字要足够短，避免为了塞内容把字号缩到不可读。
- 整套卡片颜色不超过 3 种。
- 使用较粗的非衬线字体。
- `ai-visual` 模式下，**概念图一定不要写文字**（prompt 里强调 no text/no words/no letters），所有文字交由 Pillow 合成，避免乱码。
- AI 封面的 `visual_concept` 必须随当前内容主题变化；没有生图能力时才降级 `code-graphic` 或 `typographic`。
- 渲染器对文字超行或页面溢出直接报错。拆页或改写，不得静默截断。
