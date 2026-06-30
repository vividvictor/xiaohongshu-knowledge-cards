import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_SIZE = (1080, 1440)
SUPPORTED_BLOCK_TYPES = {
    "paragraph",
    "bullet_list",
    "numbered_list",
    "quote",
    "flow",
    "comparison",
    "steps",
    "callout",
}
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\Arial.ttf",
]


class CardError(ValueError):
    pass


def parse_size(value):
    try:
        width_text, height_text = value.lower().split("x", 1)
        size = (int(width_text), int(height_text))
    except Exception as exc:
        raise argparse.ArgumentTypeError("Size must use WIDTHxHEIGHT, for example 1080x1440") from exc
    if size[0] <= 0 or size[1] <= 0:
        raise argparse.ArgumentTypeError("Size values must be positive")
    if size[0] * 4 != size[1] * 3:
        raise argparse.ArgumentTypeError("Size must use a 3:4 ratio")
    return size


def load_font(size, font_path=None):
    candidates = [font_path] if font_path else []
    candidates.extend(FONT_CANDIDATES)
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def normalize_palette(raw):
    if isinstance(raw, dict):
        values = list(raw.values())
        if len(values) > 3:
            raise CardError("Palette must contain no more than 3 colors")
        palette = {
            "background": raw.get("background", "#FFFFFF"),
            "text": raw.get("text", "#111111"),
            "accent": raw.get("accent", values[-1] if values else "#E5484D"),
        }
    elif isinstance(raw, list):
        if len(raw) > 3:
            raise CardError("Palette must contain no more than 3 colors")
        palette = {
            "background": raw[0] if len(raw) > 0 else "#FFFFFF",
            "text": raw[1] if len(raw) > 1 else "#111111",
            "accent": raw[2] if len(raw) > 2 else "#E5484D",
        }
    else:
        raise CardError("Palette must be an object or array")
    for value in palette.values():
        if not isinstance(value, str) or not value.startswith("#") or len(value) not in (4, 7):
            raise CardError(f"Invalid color value: {value}")
    return palette


def validate_deck(deck):
    if not isinstance(deck, dict):
        raise CardError("Input JSON must be an object")
    if not deck.get("title"):
        raise CardError("Missing required field: title")
    pages = deck.get("pages")
    if not isinstance(pages, list) or len(pages) < 3:
        raise CardError("Pages must contain cover, at least one content page, and ending")
    if pages[0].get("type") != "cover":
        raise CardError("First page must use type: cover")
    if pages[-1].get("type") != "ending":
        raise CardError("Last page must use type: ending")
    for idx, page in enumerate(pages[1:-1], 2):
        if page.get("type") != "content":
            raise CardError("Middle pages must use type: content")
        if not page.get("section_title"):
            raise CardError(f"Content page {idx} must contain section_title")
        blocks = page.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise CardError(f"Content page {idx} must contain at least one block")
        for block_idx, block in enumerate(blocks, 1):
            block_type = block.get("type", "paragraph")
            if block_type not in SUPPORTED_BLOCK_TYPES:
                raise CardError(f"Content page {idx} block {block_idx} uses unsupported type: {block_type}")
    ending = pages[-1]
    if not ending.get("summary") and not ending.get("quote"):
        raise CardError("Ending page must contain summary or quote")
    deck["palette"] = normalize_palette(deck.get("palette", {}))
    return deck


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_by_width(draw, text, font, max_width):
    lines = []
    for paragraph in str(text).splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if text_size(draw, candidate, font)[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def draw_wrapped(draw, text, xy, font, fill, max_width, line_gap=10, max_lines=None):
    x, y = xy
    lines = wrap_by_width(draw, text, font, max_width)
    if max_lines is not None:
        lines = lines[:max_lines]
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += text_size(draw, line or "字", font)[1] + line_gap
    return y


def crop_cover(image, box):
    target_w = box[2] - box[0]
    target_h = box[3] - box[1]
    src = image.convert("RGB")
    src_ratio = src.width / src.height
    target_ratio = target_w / target_h
    if src_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def draw_code_graphic_visual(draw, box, palette):
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    bg = palette["background"]
    text = palette["text"]
    accent = palette["accent"]
    draw.rounded_rectangle(box, radius=28, fill=accent)

    chart_base = y2 - int(height * 0.22)
    bar_w = int(width * 0.075)
    gap = int(width * 0.055)
    start_x = x1 + int(width * 0.12)
    values = [0.34, 0.58, 0.46, 0.78, 0.52]
    points = []
    for idx, value in enumerate(values):
        bx = start_x + idx * (bar_w + gap)
        top = chart_base - int(height * value * 0.58)
        draw.rounded_rectangle((bx, top, bx + bar_w, chart_base), radius=10, fill=bg if idx % 2 else text)
        points.append((bx + bar_w // 2, top - 26))

    for left, right in zip(points, points[1:]):
        draw.line((left, right), fill=bg, width=5)
    for px, py in points:
        draw.ellipse((px - 14, py - 14, px + 14, py + 14), fill=bg, outline=text, width=4)

    lever_y = y1 + int(height * 0.25)
    draw.line((x1 + int(width * 0.18), lever_y + 70, x2 - int(width * 0.12), lever_y - 36), fill=text, width=8)
    draw.ellipse((x1 + int(width * 0.15), lever_y + 42, x1 + int(width * 0.25), lever_y + 142), fill=bg, outline=text, width=5)
    draw.ellipse((x2 - int(width * 0.19), lever_y - 82, x2 - int(width * 0.09), lever_y + 18), fill=bg, outline=text, width=5)

    center = (x1 + int(width * 0.53), y1 + int(height * 0.31))
    for radius in (62, 112, 164):
        draw.arc((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), 210, 335, fill=bg, width=5)


def draw_cover(draw, image, page, deck, fonts, palette, size):
    width, height = size
    margin = int(width * 0.085)
    accent = palette["accent"]
    draw.rectangle((0, 0, width, height), fill=palette["background"])
    draw.rectangle((0, 0, width, 32), fill=accent)

    title = page.get("title") or deck["title"]
    subtitle = page.get("subtitle") or deck.get("subtitle", "")
    y = int(height * 0.11)
    y = draw_wrapped(draw, title, (margin, y), fonts["cover_title"], palette["text"], width - margin * 2, line_gap=18, max_lines=3)
    if subtitle:
        y += 18
        y = draw_wrapped(draw, subtitle, (margin, y), fonts["body"], palette["text"], width - margin * 2, line_gap=10, max_lines=2)

    visual_box = (margin, int(height * 0.52), width - margin, int(height * 0.86))
    draw_code_graphic_visual(draw, visual_box, palette)

    draw.text((margin, height - 120), "知识卡片", font=fonts["small"], fill=palette["text"])


def draw_header_footer(draw, page_index, total, deck, fonts, palette, size):
    width, height = size
    margin = int(width * 0.078)
    top_y = 138
    bottom_y = height - 155
    draw.line((margin, top_y, width - margin, top_y), fill=palette["accent"], width=4)
    draw.line((margin, bottom_y, width - margin, bottom_y), fill=palette["accent"], width=4)
    draw.text((margin, top_y - 42), deck["title"], font=fonts["small"], fill=palette["text"])
    page_text = page_label(page_index, total)
    tw, th = text_size(draw, page_text, fonts["small"])
    draw.text((width - margin - tw, bottom_y + 18), page_text, font=fonts["small"], fill=palette["text"])
    return margin, top_y + 55, width - margin, bottom_y - 45


def draw_block(draw, block, x, y, max_width, fonts, palette):
    block_type = block.get("type", "paragraph")
    text = palette["text"]
    accent = palette["accent"]
    bg = palette["background"]

    if block_type == "paragraph":
        return draw_wrapped(draw, block.get("text", ""), (x, y), fonts["body"], text, max_width, line_gap=12) + 18

    if block_type in ("bullet_list", "numbered_list"):
        items = block.get("items", [])
        for idx, item in enumerate(items, 1):
            marker = f"{idx}." if block_type == "numbered_list" else "•"
            draw.text((x, y + 4), marker, font=fonts["body_bold"], fill=accent)
            y = draw_wrapped(draw, item, (x + 46, y), fonts["body"], text, max_width - 46, line_gap=10)
            y += 14
        return y + 8

    if block_type == "quote":
        box_h = 150
        draw.rounded_rectangle((x, y, x + max_width, y + box_h), radius=18, outline=accent, width=4)
        draw.text((x + 28, y + 20), "“", font=fonts["section"], fill=accent)
        draw_wrapped(draw, block.get("text", ""), (x + 78, y + 34), fonts["body_bold"], text, max_width - 110, line_gap=10, max_lines=2)
        return y + box_h + 26

    if block_type == "callout":
        start_y = y
        draw.rounded_rectangle((x, y, x + max_width, y + 170), radius=18, fill=accent)
        title = block.get("title", "重点")
        draw.text((x + 28, y + 24), title, font=fonts["body_bold"], fill=bg)
        draw_wrapped(draw, block.get("text", ""), (x + 28, y + 78), fonts["body"], bg, max_width - 56, line_gap=10, max_lines=2)
        return start_y + 196

    if block_type in ("flow", "steps"):
        items = block.get("items", [])
        if not items:
            return y
        cols = min(len(items), 3)
        gap = 22
        box_w = int((max_width - gap * (cols - 1)) / cols)
        rows = math.ceil(len(items) / cols)
        for idx, item in enumerate(items):
            col = idx % cols
            row = idx // cols
            bx = x + col * (box_w + gap)
            by = y + row * 140
            draw.rounded_rectangle((bx, by, bx + box_w, by + 104), radius=16, outline=accent, width=4)
            label = str(idx + 1) if block_type == "steps" else "→"
            draw.text((bx + 18, by + 17), label, font=fonts["body_bold"], fill=accent)
            draw_wrapped(draw, item, (bx + 58, by + 19), fonts["small"], text, box_w - 76, line_gap=7, max_lines=2)
        return y + rows * 140 + 12

    if block_type == "comparison":
        gap = 24
        col_w = int((max_width - gap) / 2)
        left_h = draw_comparison_col(draw, x, y, col_w, block.get("left_title", "A"), block.get("left", []), fonts, palette)
        right_h = draw_comparison_col(draw, x + col_w + gap, y, col_w, block.get("right_title", "B"), block.get("right", []), fonts, palette)
        return y + max(left_h, right_h) + 24

    return draw_wrapped(draw, block.get("text", ""), (x, y), fonts["body"], text, max_width, line_gap=12) + 18


def draw_comparison_col(draw, x, y, width, title, items, fonts, palette):
    start_y = y
    draw.rounded_rectangle((x, y, x + width, y + 300), radius=18, outline=palette["accent"], width=4)
    draw.text((x + 24, y + 22), title, font=fonts["body_bold"], fill=palette["accent"])
    y += 76
    for item in items[:4]:
        y = draw_wrapped(draw, f"• {item}", (x + 24, y), fonts["small"], palette["text"], width - 48, line_gap=7, max_lines=2)
        y += 8
    return max(300, y - start_y)


def draw_content(draw, page, page_number, total, deck, fonts, palette, size):
    width, height = size
    draw.rectangle((0, 0, width, height), fill=palette["background"])
    margin, top, right, bottom = draw_header_footer(draw, page_number, total, deck, fonts, palette, size)
    content_width = right - margin
    y = top
    section_title = page.get("section_title") or "接上页"
    y = draw_wrapped(draw, section_title, (margin, y), fonts["section"], palette["text"], content_width, line_gap=12, max_lines=2)
    y += 28
    for block in page.get("blocks", []):
        if y > bottom - 80:
            break
        y = draw_block(draw, block, margin, y, content_width, fonts, palette)


def draw_ending(draw, page, deck, fonts, palette, size):
    width, height = size
    margin = int(width * 0.085)
    draw.rectangle((0, 0, width, height), fill=palette["background"])
    y = int(height * 0.18)
    title = page.get("title", "最后记住这句话")
    y = draw_wrapped(draw, title, (margin, y), fonts["section"], palette["text"], width - margin * 2, line_gap=14, max_lines=2)
    y += 48
    for item in page.get("summary", []):
        draw.text((margin, y + 3), "•", font=fonts["body_bold"], fill=palette["accent"])
        y = draw_wrapped(draw, item, (margin + 46, y), fonts["body"], palette["text"], width - margin * 2 - 46, line_gap=12, max_lines=2)
        y += 22
    quote = page.get("quote")
    if quote:
        y += 24
        draw_wrapped(draw, quote, (margin, y), fonts["body_bold"], palette["accent"], width - margin * 2, line_gap=14, max_lines=3)
    draw.rectangle((0, height - 120, width, height), fill=palette["accent"])
    end_text = "END"
    tw, th = text_size(draw, end_text, fonts["body_bold"])
    draw.text(((width - tw) / 2, height - 82), end_text, font=fonts["body_bold"], fill=palette["background"])


def make_fonts(size, font_path=None):
    scale = size[0] / DEFAULT_SIZE[0]
    def s(value):
        return max(12, int(value * scale))
    return {
        "cover_title": load_font(s(86), font_path),
        "section": load_font(s(56), font_path),
        "body": load_font(s(34), font_path),
        "body_bold": load_font(s(38), font_path),
        "small": load_font(s(24), font_path),
    }


def get_visual_source(page, deck):
    return "code-graphic"


def page_label(page_index, total):
    width = max(2, len(str(total)))
    return f"{page_index:0{width}d}/{total:0{width}d}"


def write_manifest(deck, out_dir, size, font_path, manifest_path=None):
    pages = []
    total = len(deck["pages"])
    for idx, page in enumerate(deck["pages"], 1):
        entry = {
            "index": idx,
            "type": page["type"],
            "file": f"page-{idx:02d}.png",
        }
        if page["type"] == "content":
            entry["section_title"] = page.get("section_title", "")
            entry["page_label"] = page_label(idx, total)
            entry["block_types"] = [block.get("type", "paragraph") for block in page.get("blocks", [])]
        if page["type"] == "cover":
            entry["visual_source"] = get_visual_source(page, deck)
        pages.append(entry)
    manifest = {
        "title": deck["title"],
        "subtitle": deck.get("subtitle", ""),
        "audience": deck.get("audience", ""),
        "promise": deck.get("promise", ""),
        "angle": deck.get("angle", ""),
        "visual_brief": deck.get("visual_brief", ""),
        "size": list(size),
        "page_count": total,
        "palette": deck["palette"],
        "font_path": font_path or "auto",
        "font_style": "bold-sans",
        "pages": pages,
        "quality_checks": deck.get("quality_checks", []),
    }
    target = manifest_path or (out_dir / "manifest.json")
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def render_deck(deck, out_dir, size=DEFAULT_SIZE, font_path=None, manifest_path=None, write_manifest_file=True):
    deck = validate_deck(deck)
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = make_fonts(size, font_path)
    palette = deck["palette"]
    total = len(deck["pages"])
    for idx, page in enumerate(deck["pages"], 1):
        image = Image.new("RGB", size, palette["background"])
        draw = ImageDraw.Draw(image)
        if page["type"] == "cover":
            draw_cover(draw, image, page, deck, fonts, palette, size)
        elif page["type"] == "ending":
            draw_ending(draw, page, deck, fonts, palette, size)
        else:
            draw_content(draw, page, idx, total, deck, fonts, palette, size)
        image.save(out_dir / f"page-{idx:02d}.png")
    if write_manifest_file:
        write_manifest(deck, out_dir, size, font_path, manifest_path)
    return total


def sample_deck():
    return {
        "title": "把知识变成行动",
        "subtitle": "一套适合小红书的知识卡片结构",
        "audience": "想把长内容做成小红书卡片的人",
        "promise": "用一条主线把知识压缩成可看完、可记住、可复述的卡片组",
        "angle": "从传播目标倒推卡片结构，而不是把原文机械分页",
        "visual_brief": "抽象的信息流、结构重组和行动路径，适合知识型封面主视觉",
        "palette": {
            "background": "#F9F5EF",
            "text": "#1F2933",
            "accent": "#D94A38",
        },
        "pages": [
            {
                "type": "cover",
                "title": "把知识变成行动",
                "subtitle": "从文章到卡片的3步表达法",
            },
            {
                "type": "content",
                "section_title": "先抓主线",
                "blocks": [
                    {"type": "callout", "title": "核心判断", "text": "卡片不是压缩全文，而是提炼一条可传播的认知路径。"},
                    {"type": "steps", "items": ["找问题", "给框架", "落行动"]},
                    {"type": "bullet_list", "items": ["每页只讲一个重点", "标题要像二级标题", "能画成流程就不要堆段落"]},
                ],
            },
            {
                "type": "content",
                "section_title": "用图形承载逻辑",
                "blocks": [
                    {"type": "flow", "items": ["信息输入", "结构重组", "视觉输出"]},
                    {
                        "type": "comparison",
                        "left_title": "低效表达",
                        "left": ["长段落", "重点分散", "颜色太多"],
                        "right_title": "卡片表达",
                        "right": ["短句", "层级清楚", "三色以内"],
                    },
                ],
            },
            {
                "type": "ending",
                "title": "最后记住这句话",
                "summary": ["知识卡片的目标不是完整，而是让人愿意看完并记住。", "先确定主线，再决定每页的视觉结构。"],
                "quote": "能被复述的知识，才真正完成了传播。",
            },
        ],
        "quality_checks": [
            "每页只表达一个核心意思",
            "内容页优先使用图形化 block",
            "整套卡片颜色不超过 3 种",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render 3:4 Xiaohongshu knowledge cards.")
    parser.add_argument("--input", type=Path, help="Input card JSON file.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory.")
    parser.add_argument("--sample", action="store_true", help="Render a built-in sample deck.")
    parser.add_argument("--font", help="Override font file path.")
    parser.add_argument("--manifest", type=Path, help="Manifest JSON path. Defaults to <out>/manifest.json.")
    parser.add_argument("--size", type=parse_size, default=DEFAULT_SIZE, help="Output size, default 1080x1440.")
    args = parser.parse_args(argv)

    try:
        if args.sample:
            deck = sample_deck()
        elif args.input:
            deck = json.loads(args.input.read_text(encoding="utf-8"))
        else:
            raise CardError("Provide --sample or --input")
        count = render_deck(deck, args.out, args.size, args.font, args.manifest)
    except CardError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Render failed: {exc}", file=sys.stderr)
        return 1

    print(f"Rendered {count} pages to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
