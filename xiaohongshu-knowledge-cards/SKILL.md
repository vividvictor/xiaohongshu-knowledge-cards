---
name: xiaohongshu-knowledge-cards
description: 根据用户提供的文章、笔记、提纲或主题，生成 3:4 多页小红书知识卡片 PNG。只使用代码绘制的数据可视化、几何图形、排版和文字格式，不单独调用生图。适用于用户要求小红书知识卡片、知识卡片、文章转卡片、主题转卡片、3:4 多页图文卡片、封面/内容页/结尾页卡片组或社交平台知识卡片图片输出。
---

# 小红书知识卡片

## 概述

把源内容转成可发布的 3:4 小红书知识卡片组。目标不是把文字机械分页，而是让一个有用观点更容易被看完、记住和转发。

## 第一性原理流程

1. 定义读者收益：这套卡片写给谁，读完后能理解什么、做什么。
2. 选择一个切入角度：删掉所有不服务这个角度的内容。
3. 设计页结构：封面承诺、3 到 6 页内容页、结尾总结。
4. 把每个内容页转成一个视觉推理模块：列表、步骤、流程、对比、引用或重点框。
5. 选择不超过 3 种颜色：背景色、文字色、强调色。
6. 默认使用较粗的中文非衬线字体。
7. 不调用生图。有明确核心图形时，封面用代码绘制的数据可视化或几何图形；没有核心图形时，封面用纯文字、线条和排版完成。
8. 按 `references/card-content-schema.md` 创建 JSON。
9. 渲染后检查 `manifest.json` 和 PNG 页面。

```bash
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py --input .\cards.json --out .\output
```

使用下面命令生成确定性的示例：

```bash
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py --sample --out .\output
```

## 页面规则

- 输出尺寸固定为 3:4，默认 `1080x1440`。
- 第 1 页是封面：必须有标题，可以有一句短副标题。有明确核心图形时使用代码绘制的图形化主视觉；没有特别要展现的核心图时，不要硬塞图，使用纯文字、线条和排版封面。
- 最后一页是结尾页：总结、金句或行动提示。底部必须有明显的纯色强调条。
- 中间内容页必须有上分隔线和下分隔线。
- 内容页上分隔线左上方写文章标题，字号与页码一致。
- 内容页下分隔线右下方写纯数字页码，例如 `02/06`。页码中不要出现中文。
- 内容区左上角放本页二级标题。如果本页承接上一页，标题写 `接上页`。
- 中间内容页要结构清晰，方便扫读。

## JSON 约定

正式生成前先读 `references/card-content-schema.md`。JSON 应包含这些策略字段：

- `audience`：目标读者。
- `promise`：这套卡片承诺给读者的有用结果。
- `angle`：用于筛选源内容的编辑角度。
- `visual_brief`：封面代码图形的可视化方向。只有存在明确核心图形时填写；没有核心图形时留空。
- `quality_checks`：最终卡片必须满足的具体检查项。

渲染器会拒绝这些输入：页面顺序错误、调色板超过 3 种颜色、不支持的 block 类型、空内容页、没有 `summary` 或 `quote` 的结尾页。

## 内容模块

优先用图形化思维表达，不要堆长段落。可用这些 block 类型：

- `bullet_list`：并列要点。
- `numbered_list` 或 `steps`：有顺序的流程。
- `flow`：因果、递进、前后变化。
- `comparison`：对比、误区纠正、两面分析。
- `quote`：强记忆点或金句。
- `callout`：提醒、关键洞察、一句话原则。

少用 `paragraph`。如果一个段落包含多个判断，拆成图形化模块。

## 脚本接口

```bash
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py --input .\cards.json --out .\output
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py --sample --out .\output
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py --input .\cards.json --out .\output --manifest .\output\checks.json
python .\xiaohongshu-knowledge-cards\scripts\render_cards.py --input .\cards.json --out .\output --font C:\Windows\Fonts\NotoSansSC-VF.ttf --size 1080x1440
```

脚本会写出 `page-01.png`、`page-02.png` 等文件，并默认生成 `manifest.json`。用 `--manifest` 可以指定其他 manifest 路径。

## 验收检查

交付前必须验证：

- 修改 skill 后，`quick_validate.py` 必须显示 skill 有效。
- 修改渲染脚本行为后，渲染器测试必须通过。
- 所有输出 PNG 必须是 3:4。
- `manifest.json` 必须记录标题、受众、承诺、页数、调色板、纯数字页码、粗体非衬线字体标记和封面视觉来源。封面视觉来源可以是 `code-graphic` 或 `typographic`。
- 抽查渲染样例，确认封面、内容页分隔线、页码和结尾强调条都可见。
