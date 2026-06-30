# 卡片内容 Schema

使用 UTF-8 JSON。

## 顶层字段

- `title`：字符串，必填。用于内容页顶部标题，也作为封面标题兜底。
- `subtitle`：字符串，可选。封面副标题。
- `audience`：字符串，推荐填写。这套卡片面向的读者。
- `promise`：字符串，推荐填写。承诺给读者的有用结果。
- `angle`：字符串，推荐填写。筛选源内容的编辑角度。
- `visual_brief`：字符串，推荐填写。封面代码图形的可视化方向，例如数据可视化、几何图形、排版和文字风格。不要用它调用生图。
- `palette`：对象或数组，必填。最多 3 种颜色。
  - 对象键建议使用 `background`、`text`、`accent`。
  - 颜色值必须是类似 `#FFFFFF` 的十六进制颜色。
- `visual_path`：渲染器会忽略该字段。除非重新设计 skill，否则视觉输出保持代码原生。
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
        { "type": "callout", "title": "核心判断", "text": "卡片不是压缩全文，而是提炼一条可传播的认知路径。" },
        { "type": "steps", "items": ["找问题", "给框架", "落行动"] }
      ]
    },
    {
      "type": "ending",
      "title": "最后记住这句话",
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
  "subtitle": "一句话说明"
}
```

### Content

内容页必须包含 `section_title` 和非空的 `blocks` 数组。如果本页承接上一页，`section_title` 设为 `接上页`。

```json
{
  "type": "content",
  "section_title": "二级标题",
  "blocks": [
    { "type": "paragraph", "text": "短段落。" },
    { "type": "bullet_list", "items": ["要点一", "要点二"] },
    { "type": "numbered_list", "items": ["第一步", "第二步"] },
    { "type": "steps", "items": ["输入", "处理", "输出"] },
    { "type": "flow", "items": ["问题", "机制", "结果"] },
    { "type": "comparison", "left_title": "误区", "left": ["..."], "right_title": "正确做法", "right": ["..."] },
    { "type": "quote", "text": "一句金句。" },
    { "type": "callout", "title": "关键提醒", "text": "一句重点。" }
  ]
}
```

### Ending

结尾页必须包含 `summary` 或 `quote`。

```json
{
  "type": "ending",
  "title": "最后记住这句话",
  "summary": ["总结一", "总结二"],
  "quote": "真正的改变，来自可重复的小动作。"
}
```

## 支持的 Blocks

- `paragraph`: `{ "type": "paragraph", "text": "短段落。" }`
- `bullet_list`: `{ "type": "bullet_list", "items": ["要点一", "要点二"] }`
- `numbered_list`: `{ "type": "numbered_list", "items": ["第一步", "第二步"] }`
- `steps`: `{ "type": "steps", "items": ["输入", "处理", "输出"] }`
- `flow`: `{ "type": "flow", "items": ["问题", "机制", "结果"] }`
- `comparison`: `{ "type": "comparison", "left_title": "误区", "left": ["..."], "right_title": "正确做法", "right": ["..."] }`
- `quote`: `{ "type": "quote", "text": "一句金句。" }`
- `callout`: `{ "type": "callout", "title": "关键提醒", "text": "一句重点。" }`

未知 block 类型无效。

## Manifest 输出

渲染器默认写出 `manifest.json`，其中记录：

- `title`、`subtitle`、`audience`、`promise`、`angle`、`visual_brief`
- `size`、`page_count`、`palette`、`font_path`、`font_style`
- 每一页的文件名、页面类型、内容页页码、block 类型、封面视觉来源
- `quality_checks`

## 写作规则

- 每页只讲一个核心意思。
- 优先使用图形化 block，不堆长段落。
- 段落文字要足够短，避免为了塞内容把字号缩到不可读。
- 整套卡片颜色不超过 3 种。
- 使用较粗的非衬线字体。
