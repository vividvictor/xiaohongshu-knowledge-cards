---
name: xiaohongshu-knowledge-cards
description: 将文章、笔记、提纲或主题转成高信息密度的 3:4 多页知识卡片 PNG；封面主视觉必须根据当前内容主题动态生成，并用本地排版保证中文准确。适用于小红书知识卡片、文章转卡片、图片卡片、图文卡片组和社交平台知识图解。
metadata:
  version: "2.0.0"
  author: "vividvictor"
  workbuddy:
    display_name: "小红书知识卡片"
    display_name_en: "Xiaohongshu Knowledge Cards"
    description_zh: "把长内容转成封面主题匹配、正文高密度且中文清晰的多页知识卡片。"
    description_en: "Turn source content into dense 3:4 knowledge-card PNGs with a topic-specific generated cover and reliable local typography."
---

# 小红书知识卡片

把用户内容转成可发布的 `1080x1440` 多页卡片。封面负责停留，正文负责信息，二者不能用同一套密度规则。

## 执行流程

1. 完整读取源内容，提炼 `theme`、`audience`、`promise`、`angle`、核心结论和 5—8 个可视化要点。事实、数字与专名不得擅自补写。
2. 为本次内容单独建立封面概念：具体主体 + 动作/关系 + 读者结果 + 情绪。不得复用固定的“知识变成行动”等通用图。
3. 选择信息布局与视觉风格。默认 `density: "dense"`；只有金句、情绪或单一观点页才改用 `balanced` / `airy`。
4. 先读 [卡片内容 Schema](references/card-content-schema.md)，再创建 UTF-8 JSON。涉及密度、网格、字阶或视觉比例时同时读 [排版系统](references/layout-design.md)。
5. 按 [运行时兼容](references/runtime-compatibility.md) 选择当前环境的原生生图能力。封面优先 `ai-visual`；内容页只有在图片能解释逻辑时才使用 `ai-visual`，否则用本地结构化排版。
6. 用 `scripts/render_cards.py` 合成中文文字层。任何文字都由 Pillow 渲染；生成图内禁止文字。
7. 检查全部 PNG 和 `manifest.json`。发现溢出时拆页或改写，不得缩成不可读字号，也不得删除未放下的 block。

## 动态封面契约

封面主视觉必须来自用户本次提供的内容主题，而不是固定模板图。

- 从源内容提取 2—4 个不可替换的主题词、一个核心动作或冲突、一个结果意象。
- 把源内容中 1—4 个不可替换词写入 `theme_keywords`，把具体画面写入 `visual_concept`；把实际送给生图工具的完整提示词写入 `image_prompt`。概念或提示词必须至少出现一个主题词。
- 提示词必须明确 `3:4 vertical`、整套 palette、标题安全区，并重复要求 `no text, no words, no letters, no labels, no numbers, no typography`。
- 生成完成后把本地路径写入 `image_path`。渲染器会拒绝没有 `visual_concept` 的 AI 封面。
- 封面图允许使用统一的系列风格，但主体、动作、隐喻必须随内容改变。

## 高密度正文

- 风格与布局分开选择：风格控制色彩、线条、质感；布局控制信息数量和阅读顺序。
- 默认 `dense`：一页建议 5—8 个短要点或约 180—320 个中文字符；用四级字阶、统一网格和固定安全边距保持可读性。
- `ai-visual` 内容页在 `dense` 下默认只占页面高度的 32%；可用 `visual_ratio` 在 `0.26—0.50` 内调整。图片不是装饰，不能挤占关键正文。
- 优先使用 `fact_grid`、`comparison`、`flow`、`steps`、`bullet_list`、`callout`；少用大段 `paragraph`。
- 每页只保留一个核心问题，但允许用多个模块讲透。内容装不下时拆成“主题 / 接上页”，不要截断。

## 运行命令

使用当前环境中已经可用且安装了 Pillow 的 Python；不要自行安装全局依赖。

```bash
python xiaohongshu-knowledge-cards/scripts/render_cards.py --input cards.json --out output
python xiaohongshu-knowledge-cards/scripts/render_cards.py --sample --out output
python xiaohongshu-knowledge-cards/scripts/render_cards.py --input cards.json --out output --font /path/to/regular.ttf --font-bold /path/to/bold.ttf
```

脚本输出 `page-01.png`、`page-02.png`…和 `manifest.json`。相对 `image_path` 以输入 JSON 所在目录为基准。

## 验收

- 所有 PNG 都是 3:4，中文无乱码、豆腐块、遮挡或越界。
- 封面 `theme_keywords`、`visual_concept` 与用户主题有不可替换的对应关系；换成别的主题就不成立。
- 页码为纯数字 `02/06`；正文页上下分隔线、标题与页码完整可见。
- `manifest.json` 记录 `density`、`layout_system`、每页 `visual_source`、`content_char_count`；所有 AI 页记录 `image_path` 和 `visual_concept`。
- 渲染器测试通过，`skill-creator/scripts/quick_validate.py` 通过。
