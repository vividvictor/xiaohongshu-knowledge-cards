import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.stderr.write(
        "[xiaohongshu-knowledge-cards] Pillow is required to render knowledge cards.\n"
        "Install it into the active Python environment, for example:\n"
        "  WorkBuddy managed venv: "
        "%USERPROFILE%\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\pip.exe install Pillow\n"
        "  Any other environment:  python -m pip install Pillow\n"
    )
    raise SystemExit(2)


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
    "fact_grid",
}

SUPPORTED_DENSITIES = {"dense", "balanced", "airy"}

# Values use a 1080px-wide canvas baseline and are scaled proportionally.
# Dense is intentionally the default: knowledge cards are read at arm's length,
# not from across a room, so they can carry more copy than posters while still
# retaining a clear four-level hierarchy.
DENSITY_PROFILES = {
    "dense": {
        "cover_title": 78,
        "section": 46,
        "body": 30,
        "body_bold": 32,
        "small": 21,
        "micro": 18,
        "margin_ratio": 0.065,
        "header_top": 112,
        "footer_offset": 126,
        "line_gap": 7,
        "block_gap": 12,
        "ai_visual_ratio": 0.32,
    },
    "balanced": {
        "cover_title": 84,
        "section": 52,
        "body": 33,
        "body_bold": 36,
        "small": 23,
        "micro": 20,
        "margin_ratio": 0.074,
        "header_top": 128,
        "footer_offset": 142,
        "line_gap": 9,
        "block_gap": 18,
        "ai_visual_ratio": 0.40,
    },
    "airy": {
        "cover_title": 90,
        "section": 58,
        "body": 36,
        "body_bold": 40,
        "small": 25,
        "micro": 22,
        "margin_ratio": 0.085,
        "header_top": 144,
        "footer_offset": 158,
        "line_gap": 11,
        "block_gap": 24,
        "ai_visual_ratio": 0.48,
    },
}

# Regular- and bold-weight CJK font candidates per OS. Each list is searched
# in order; the first existing file wins. Bold is resolved independently so
# headers can render heavier than body text instead of sharing a single weight.
_FONT_REGULAR_BY_OS = {
    "windows": [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simfang.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
        r"C:\Windows\Fonts\Deng.ttf",
    ],
    "darwin": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Songti.ttc",
    ],
    "linux": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ],
}
_FONT_BOLD_BY_OS = {
    "windows": [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simkai.ttf",
        r"C:\Windows\Fonts\NotoSansSC-VF.ttf",  # variable font; bold synthesised via wght
        r"C:\Windows\Fonts\NotoSerifSC-VF.ttf",
    ],
    "darwin": [
        "/System/Library/Fonts/STHeiti Bold.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Songti.ttc",
    ],
    "linux": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ],
}


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


def _detect_os():
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _query_fc_list():
    """Discover installed CJK font files via fontconfig (Linux/macOS only)."""
    fc = shutil.which("fc-list")
    if not fc:
        return []
    try:
        out = subprocess.run(
            [fc, ":lang=zh-cn", "family", "file"],
            capture_output=True, text=True, timeout=3, check=False,
        ).stdout
    except Exception:
        return []
    files = []
    for line in out.splitlines():
        if "file:" not in line:
            continue
        path = line.split("file:", 1)[1].strip()
        if path and Path(path).exists():
            files.append(path)
    return files


def _open_font(path, size):
    """Open a font, falling back to face 0 for TrueType collections."""
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        return ImageFont.truetype(path, size=size, index=0)


def _apply_bold_variation(font, path):
    """Push the wght axis of a variable font to ~700. No-op on static fonts."""
    if not path or "VF" not in Path(path).stem:
        return
    try:
        font.set_variation_by_axes(["wght"], [700])
        return
    except Exception:
        pass
    try:
        font.set_variation_by_name("Bold")
    except Exception:
        pass


def load_font(size, role="regular", font_path=None, bold_font_path=None):
    """Return a CJK-capable font at ``size``.

    ``role`` selects the regular or bold face. Bold is resolved independently
    so headers and body text render with distinct weights. When no bold face
    is available the regular face is returned as a last resort (still better
    than silently rendering tofu). Raises ``CardError`` if no CJK font is
    found at all.
    """
    os_key = _detect_os()

    if role == "regular":
        override = font_path
        candidates = _FONT_REGULAR_BY_OS[os_key]

        if override and Path(override).exists():
            return _open_font(override, size)
        for path in candidates:
            try:
                return _open_font(path, size)
            except OSError:
                continue
        for path in _query_fc_list():
            name = Path(path).name.lower()
            if (
                any(tag in name for tag in ("regular", "medium", "normal"))
                or "cjk" in name
                or "noto" in name
            ):
                try:
                    return _open_font(path, size)
                except OSError:
                    continue
        raise CardError(
            "No CJK font found. Install a Chinese font (Noto Sans CJK, "
            "Microsoft YaHei, PingFang, or similar) or pass --font to "
            "point at a TTF/TTC file."
        )

    # role == "bold"
    if bold_font_path and Path(bold_font_path).exists():
        font = _open_font(bold_font_path, size)
        _apply_bold_variation(font, bold_font_path)
        return font
    for path in _FONT_BOLD_BY_OS[os_key]:
        try:
            font = _open_font(path, size)
            _apply_bold_variation(font, path)
            return font
        except OSError:
            continue
    for path in _query_fc_list():
        name = Path(path).name.lower()
        if any(tag in name for tag in ("bold", "black", "heavy")):
            try:
                font = _open_font(path, size)
                _apply_bold_variation(font, path)
                return font
            except OSError:
                continue
    # Synthesise bold from a variable regular face, else mirror the regular face.
    if font_path and Path(font_path).exists() and "VF" in Path(font_path).stem:
        font = _open_font(font_path, size)
        _apply_bold_variation(font, font_path)
        return font
    return load_font(size, role="regular", font_path=font_path)


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


def normalize_density(raw):
    density = str(raw or "dense").strip().lower()
    aliases = {"compact": "dense", "normal": "balanced", "spacious": "airy"}
    density = aliases.get(density, density)
    if density not in SUPPORTED_DENSITIES:
        raise CardError(
            f"Unsupported density: {density}. Use dense, balanced, or airy."
        )
    return density


def layout_profile(deck, size):
    density = normalize_density(deck.get("density"))
    base = DENSITY_PROFILES[density]
    scale = size[0] / DEFAULT_SIZE[0]
    profile = dict(base)
    for key in (
        "cover_title",
        "section",
        "body",
        "body_bold",
        "small",
        "micro",
        "header_top",
        "footer_offset",
        "line_gap",
        "block_gap",
    ):
        profile[key] = max(1, int(round(base[key] * scale)))
    profile["density"] = density
    return profile


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
    ai_modes = ("ai-visual", "ai", "generated", "image")
    for idx, page in enumerate(pages, 1):
        page_mode = str(page.get("visual_mode") or deck.get("visual_mode") or "").strip().lower()
        if page_mode in ai_modes and not page.get("image_path"):
            raise CardError(
                f"Page {idx} ({page.get('type')}) uses visual_mode 'ai-visual' but is "
                f"missing image_path. Generate the visual first and set image_path."
            )
        if page_mode in ai_modes and page.get("type") == "cover" and not page.get("visual_concept"):
            raise CardError(
                "AI cover must contain visual_concept derived from the current source topic; "
                "do not reuse a fixed generic cover concept."
            )
        if page_mode in ai_modes and page.get("type") == "cover":
            theme_keywords = page.get("theme_keywords")
            if (
                not isinstance(theme_keywords, list)
                or not 1 <= len(theme_keywords) <= 4
                or any(not str(keyword).strip() for keyword in theme_keywords)
            ):
                raise CardError("AI cover theme_keywords must contain 1 to 4 source-specific terms")
            concept_text = " ".join(
                [str(page.get("visual_concept", "")), str(page.get("image_prompt", ""))]
            ).lower()
            if not any(str(keyword).strip().lower() in concept_text for keyword in theme_keywords):
                raise CardError(
                    "AI cover visual_concept or image_prompt must include at least one "
                    "theme_keywords term from the current source."
                )
        if "visual_ratio" in page:
            try:
                visual_ratio = float(page["visual_ratio"])
            except (TypeError, ValueError):
                raise CardError(f"Page {idx} visual_ratio must be a number")
            if not 0.26 <= visual_ratio <= 0.50:
                raise CardError(f"Page {idx} visual_ratio must be between 0.26 and 0.50")
    deck["palette"] = normalize_palette(deck.get("palette", {}))
    deck["density"] = normalize_density(deck.get("density"))
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


def line_height(draw, font, line_gap=0):
    return text_size(draw, "国Ag", font)[1] + line_gap


def draw_wrapped(
    draw,
    text,
    xy,
    font,
    fill,
    max_width,
    line_gap=10,
    max_lines=None,
    context="text",
):
    x, y = xy
    lines = wrap_by_width(draw, text, font, max_width)
    if max_lines is not None and len(lines) > max_lines:
        raise CardError(
            f"{context} needs {len(lines)} lines but the layout allows {max_lines}; "
            "shorten it, split the page, or use density 'dense'."
        )
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height(draw, font, line_gap)
    return y


def wrapped_height(draw, text, font, max_width, line_gap=10):
    return len(wrap_by_width(draw, text, font, max_width)) * line_height(draw, font, line_gap)


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


def _hex_to_rgb(value):
    value = str(value).lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def cover_fit_paste(base, image, box):
    """Resize ``image`` to cover ``box`` (center-crop) and paste it onto ``base``."""
    x1, y1, x2, y2 = box
    tw, th = x2 - x1, y2 - y1
    src = image.convert("RGB")
    src_ratio = src.width / src.height
    target_ratio = tw / th
    if src_ratio > target_ratio:
        new_h = th
        new_w = int(round(th * src_ratio))
    else:
        new_w = tw
        new_h = int(round(tw / src_ratio))
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    crop = resized.crop((left, top, left + tw, top + th))
    base.paste(crop, (x1, y1))
    return crop


def add_bottom_scrim(base, box, max_alpha=220):
    """Paint a vertical dark gradient on ``base``.

    Starts already half-dark so overlaid title text stays legible even when the
    generated image is light; deepens to ``max_alpha`` at the very bottom.
    """
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(h):
        alpha = int(max_alpha * (0.45 + 0.55 * (i / max(1, h))))
        od.line([(0, i), (w, i)], fill=(0, 0, 0, alpha))
    base.paste(overlay, (x1, y1), overlay)


def draw_top_pill(image, draw, text, fonts, size):
    """Draw a translucent dark pill with light text at the top-left (over an image)."""
    if not text:
        return
    margin = int(size[0] * 0.078)
    font = fonts["small"]
    tw, th = text_size(draw, text, font)
    pad_x, pad_y = 22, 14
    box = (margin, 58, margin + tw + pad_x * 2, 58 + th + pad_y * 2)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(box, radius=20, fill=(0, 0, 0, 120))
    image.paste(overlay, (0, 0), overlay)
    draw.text((margin + pad_x, 58 + pad_y), text, font=font, fill="#FFFFFF")


def load_page_image(page, base_dir):
    """Load the generated visual for an ``ai-visual`` page, failing loudly if missing."""
    raw = page.get("image_path")
    if not raw:
        raise CardError(
            "Page uses visual_mode 'ai-visual' but has no image_path. Generate the "
            "visual image first (see SKILL.md '用生图生成视觉' section) and set image_path."
        )
    path = Path(raw)
    if not path.is_absolute() and base_dir:
        path = Path(base_dir) / path
    if not path.exists():
        raise CardError(f"image_path does not exist: {path}")
    try:
        return Image.open(path).convert("RGB")
    except Exception as exc:
        raise CardError(f"Could not open image_path {path}: {exc}")


def draw_ai_cover(draw, image, page, deck, fonts, palette, size, image_obj):
    width, height = size
    accent = palette["accent"]
    cover_fit_paste(image, image_obj, (0, 0, width, height))
    draw.rectangle((0, 0, width, 32), fill=accent)
    scrim_h = int(height * 0.46)
    add_bottom_scrim(image, (0, height - scrim_h, width, height), max_alpha=185)
    margin = int(width * 0.085)
    kicker = page.get("kicker") or deck.get("audience") or ""
    if kicker:
        draw_top_pill(image, draw, kicker, fonts, size)
    title = page.get("title") or deck["title"]
    subtitle = page.get("subtitle") or deck.get("subtitle", "")
    y = height - scrim_h + int(height * 0.05)
    y = draw_wrapped(
        draw,
        title,
        (margin, y),
        fonts["cover_title"],
        "#FFFFFF",
        width - margin * 2,
        line_gap=16,
        max_lines=3,
        context="cover title",
    )
    if subtitle:
        y += 16
        draw_wrapped(
            draw,
            subtitle,
            (margin, y),
            fonts["body"],
            "#F5F5F5",
            width - margin * 2,
            line_gap=10,
            max_lines=2,
            context="cover subtitle",
        )
    draw.text((margin, height - 70), "知识卡片", font=fonts["small"], fill="#FFFFFF")


def draw_ai_content(draw, image, page, page_index, total, deck, fonts, palette, size, image_obj):
    width, height = size
    accent = palette["accent"]
    profile = fonts["_profile"]
    margin = int(width * profile["margin_ratio"])
    visual_ratio = float(page.get("visual_ratio", profile["ai_visual_ratio"]))
    band_bottom = int(height * visual_ratio)
    cover_fit_paste(image, image_obj, (0, 0, width, band_bottom))
    draw.line((0, band_bottom, width, band_bottom), fill=accent, width=6)
    draw_top_pill(image, draw, deck["title"], fonts, size)
    y = band_bottom + max(28, profile["block_gap"] * 2)
    section_title = page.get("section_title") or "接上页"
    y = draw_wrapped(
        draw,
        section_title,
        (margin, y),
        fonts["section"],
        palette["text"],
        width - margin * 2,
        line_gap=profile["line_gap"],
        max_lines=2,
        context=f"content page {page_index} section title",
    )
    y += profile["block_gap"]
    bottom_y = height - profile["footer_offset"]
    for block in page.get("blocks", []):
        y = draw_block(draw, block, margin, y, width - margin * 2, fonts, palette)
        if y > bottom_y - profile["block_gap"]:
            raise CardError(
                f"Content page {page_index} overflows the safe area by "
                f"{int(y - (bottom_y - profile['block_gap']))}px. Split the page, "
                "reduce copy, lower visual_ratio, or use density 'dense'."
            )
    draw.line((margin, bottom_y, width - margin, bottom_y), fill=accent, width=4)
    page_text = page_label(page_index, total)
    tw, th = text_size(draw, page_text, fonts["small"])
    draw.text((width - margin - tw, bottom_y + 18), page_text, font=fonts["small"], fill=palette["text"])


def draw_ai_ending(draw, image, page, deck, fonts, palette, size, image_obj):
    width, height = size
    accent = palette["accent"]
    cover_fit_paste(image, image_obj, (0, 0, width, height))
    draw.rectangle((0, 0, width, 32), fill=accent)
    scrim_h = int(height * 0.5)
    add_bottom_scrim(image, (0, height - scrim_h, width, height), max_alpha=180)
    margin = int(width * 0.085)
    title = page.get("title", "最后记住这句话")
    y = height - scrim_h + int(height * 0.04)
    y = draw_wrapped(
        draw,
        title,
        (margin, y),
        fonts["section"],
        "#FFFFFF",
        width - margin * 2,
        line_gap=14,
        max_lines=2,
        context="ending title",
    )
    y += 36
    for item in page.get("summary", []):
        draw.text((margin, y + 3), "•", font=fonts["body_bold"], fill=accent)
        y = draw_wrapped(
            draw,
            item,
            (margin + 46, y),
            fonts["body"],
            "#F5F5F5",
            width - margin * 2 - 46,
            line_gap=10,
            max_lines=3,
            context="ending summary",
        )
        y += 18
    quote = page.get("quote")
    if quote:
        y += 20
        y = draw_wrapped(
            draw,
            quote,
            (margin, y),
            fonts["body_bold"],
            "#FFFFFF",
            width - margin * 2,
            line_gap=14,
            max_lines=4,
            context="ending quote",
        )
    if y > height - 72:
        raise CardError("Ending page overflows the canvas; shorten or split its copy.")


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


def cover_visual_source(page, deck):
    visual_mode = str(page.get("visual_mode") or deck.get("visual_mode") or "").strip().lower()
    if visual_mode in ("ai-visual", "ai", "generated", "image"):
        return "ai-visual"
    if visual_mode in ("typographic", "none", "text"):
        return "typographic"
    if visual_mode in ("graphic", "code-graphic"):
        return "code-graphic"
    visual_brief = str(page.get("visual_brief") or deck.get("visual_brief") or "").strip()
    return "code-graphic" if visual_brief else "typographic"


def draw_typographic_cover(draw, title, subtitle, deck, fonts, palette, size):
    width, height = size
    margin = int(width * 0.085)
    text = palette["text"]
    accent = palette["accent"]

    draw.line((margin, int(height * 0.55), width - margin, int(height * 0.55)), fill=accent, width=5)
    draw.line((margin, int(height * 0.575), width - margin, int(height * 0.575)), fill=text, width=2)

    label = deck.get("angle") or deck.get("promise") or "知识卡片"
    draw_wrapped(draw, label, (margin, int(height * 0.61)), fonts["small"], text, width - margin * 2, line_gap=8, max_lines=2)

    keyword = deck.get("audience") or "小红书知识卡片"
    draw.rounded_rectangle(
        (margin, int(height * 0.77), width - margin, int(height * 0.855)),
        radius=22,
        outline=accent,
        width=4,
    )
    draw_wrapped(draw, keyword, (margin + 30, int(height * 0.795)), fonts["body_bold"], accent, width - margin * 2 - 60, line_gap=8, max_lines=1)

    if not subtitle:
        draw.text((margin, height - 120), "KNOWLEDGE CARDS", font=fonts["small"], fill=text)


def draw_cover(draw, image, page, deck, fonts, palette, size):
    width, height = size
    margin = int(width * 0.085)
    accent = palette["accent"]
    draw.rectangle((0, 0, width, height), fill=palette["background"])
    draw.rectangle((0, 0, width, 32), fill=accent)

    title = page.get("title") or deck["title"]
    subtitle = page.get("subtitle") or deck.get("subtitle", "")
    y = int(height * 0.11)
    y = draw_wrapped(
        draw,
        title,
        (margin, y),
        fonts["cover_title"],
        palette["text"],
        width - margin * 2,
        line_gap=18,
        max_lines=3,
        context="cover title",
    )
    if subtitle:
        y += 18
        y = draw_wrapped(
            draw,
            subtitle,
            (margin, y),
            fonts["body"],
            palette["text"],
            width - margin * 2,
            line_gap=10,
            max_lines=2,
            context="cover subtitle",
        )

    if cover_visual_source(page, deck) == "code-graphic":
        visual_box = (margin, int(height * 0.52), width - margin, int(height * 0.86))
        draw_code_graphic_visual(draw, visual_box, palette)
    else:
        draw_typographic_cover(draw, title, subtitle, deck, fonts, palette, size)

    draw.text((margin, height - 120), "知识卡片", font=fonts["small"], fill=palette["text"])


def draw_header_footer(draw, page_index, total, deck, fonts, palette, size):
    width, height = size
    profile = fonts["_profile"]
    margin = int(width * profile["margin_ratio"])
    top_y = profile["header_top"]
    bottom_y = height - profile["footer_offset"]
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
    profile = fonts["_profile"]
    line_gap = profile["line_gap"]
    block_gap = profile["block_gap"]

    if block_type == "paragraph":
        return draw_wrapped(
            draw,
            block.get("text", ""),
            (x, y),
            fonts["body"],
            text,
            max_width,
            line_gap=line_gap,
        ) + block_gap

    if block_type in ("bullet_list", "numbered_list"):
        items = block.get("items", [])
        for idx, item in enumerate(items, 1):
            marker = f"{idx}." if block_type == "numbered_list" else "•"
            marker_width = max(38, text_size(draw, marker, fonts["body_bold"])[0] + 12)
            draw.text((x, y + 2), marker, font=fonts["body_bold"], fill=accent)
            y = draw_wrapped(
                draw,
                item,
                (x + marker_width, y),
                fonts["body"],
                text,
                max_width - marker_width,
                line_gap=line_gap,
            )
            y += max(6, block_gap // 2)
        return y + block_gap // 2

    if block_type == "quote":
        inner_width = max_width - 110
        content_h = wrapped_height(
            draw, block.get("text", ""), fonts["body_bold"], inner_width, line_gap
        )
        box_h = max(120, content_h + 60)
        draw.rounded_rectangle((x, y, x + max_width, y + box_h), radius=18, outline=accent, width=4)
        draw.text((x + 24, y + 16), "\u201c", font=fonts["section"], fill=accent)
        draw_wrapped(
            draw,
            block.get("text", ""),
            (x + 78, y + 28),
            fonts["body_bold"],
            text,
            inner_width,
            line_gap=line_gap,
        )
        return y + box_h + block_gap

    if block_type == "callout":
        title = block.get("title", "重点")
        inner_width = max_width - 52
        title_h = wrapped_height(draw, title, fonts["body_bold"], inner_width, line_gap)
        body_h = wrapped_height(
            draw, block.get("text", ""), fonts["body"], inner_width, line_gap
        )
        box_h = max(134, 24 + title_h + 10 + body_h + 24)
        draw.rounded_rectangle((x, y, x + max_width, y + box_h), radius=18, fill=accent)
        text_y = draw_wrapped(
            draw,
            title,
            (x + 26, y + 22),
            fonts["body_bold"],
            bg,
            inner_width,
            line_gap=line_gap,
        )
        draw_wrapped(
            draw,
            block.get("text", ""),
            (x + 26, text_y + 8),
            fonts["body"],
            bg,
            inner_width,
            line_gap=line_gap,
        )
        return y + box_h + block_gap

    if block_type in ("flow", "steps"):
        items = block.get("items", [])
        if not items:
            return y
        cols = min(len(items), 3)
        gap = max(14, block_gap)
        box_w = int((max_width - gap * (cols - 1)) / cols)
        row_heights = []
        for start in range(0, len(items), cols):
            row_items = items[start:start + cols]
            content_heights = [
                wrapped_height(draw, item, fonts["small"], box_w - 64, line_gap)
                for item in row_items
            ]
            row_heights.append(max(88, max(content_heights, default=0) + 32))
        current_y = y
        for row, row_h in enumerate(row_heights):
            for col, item in enumerate(items[row * cols:(row + 1) * cols]):
                idx = row * cols + col
                bx = x + col * (box_w + gap)
                draw.rounded_rectangle(
                    (bx, current_y, bx + box_w, current_y + row_h),
                    radius=16,
                    outline=accent,
                    width=4,
                )
                label = str(idx + 1) if block_type == "steps" else "→"
                draw.text((bx + 14, current_y + 14), label, font=fonts["body_bold"], fill=accent)
                draw_wrapped(
                    draw,
                    item,
                    (bx + 54, current_y + 16),
                    fonts["small"],
                    text,
                    box_w - 64,
                    line_gap=line_gap,
                )
            current_y += row_h + gap
        return current_y

    if block_type == "comparison":
        gap = max(16, block_gap)
        col_w = int((max_width - gap) / 2)
        left = (block.get("left_title", "A"), block.get("left", []))
        right = (block.get("right_title", "B"), block.get("right", []))
        box_h = max(
            comparison_col_height(draw, col_w, left[0], left[1], fonts),
            comparison_col_height(draw, col_w, right[0], right[1], fonts),
        )
        draw_comparison_col(draw, x, y, col_w, box_h, left[0], left[1], fonts, palette)
        draw_comparison_col(
            draw,
            x + col_w + gap,
            y,
            col_w,
            box_h,
            right[0],
            right[1],
            fonts,
            palette,
        )
        return y + box_h + block_gap

    if block_type == "fact_grid":
        return draw_fact_grid(draw, block.get("items", []), x, y, max_width, fonts, palette)

    return draw_wrapped(
        draw,
        block.get("text", ""),
        (x, y),
        fonts["body"],
        text,
        max_width,
        line_gap=line_gap,
    ) + block_gap


def comparison_col_height(draw, width, title, items, fonts):
    profile = fonts["_profile"]
    inner_width = width - 40
    total = 20 + wrapped_height(
        draw, title, fonts["body_bold"], inner_width, profile["line_gap"]
    ) + 12
    for item in items:
        total += wrapped_height(
            draw, f"• {item}", fonts["small"], inner_width, profile["line_gap"]
        ) + 6
    return max(220, total + 18)


def draw_comparison_col(draw, x, y, width, height, title, items, fonts, palette):
    profile = fonts["_profile"]
    inner_width = width - 40
    draw.rounded_rectangle(
        (x, y, x + width, y + height), radius=18, outline=palette["accent"], width=4
    )
    text_y = draw_wrapped(
        draw,
        title,
        (x + 20, y + 18),
        fonts["body_bold"],
        palette["accent"],
        inner_width,
        line_gap=profile["line_gap"],
    ) + 10
    for item in items:
        text_y = draw_wrapped(
            draw,
            f"• {item}",
            (x + 20, text_y),
            fonts["small"],
            palette["text"],
            inner_width,
            line_gap=profile["line_gap"],
        ) + 6


def normalize_fact_item(item):
    if isinstance(item, dict):
        return str(item.get("title", "")), str(item.get("text", ""))
    return "", str(item)


def draw_fact_grid(draw, items, x, y, max_width, fonts, palette):
    if not items:
        return y
    profile = fonts["_profile"]
    gap = max(12, profile["block_gap"])
    cols = 2 if len(items) > 1 else 1
    box_w = int((max_width - gap * (cols - 1)) / cols)
    rows = math.ceil(len(items) / cols)
    current_y = y
    for row in range(rows):
        row_items = items[row * cols:(row + 1) * cols]
        heights = []
        for raw_item in row_items:
            title, body = normalize_fact_item(raw_item)
            title_h = (
                wrapped_height(draw, title, fonts["body_bold"], box_w - 36, profile["line_gap"])
                if title
                else 0
            )
            body_h = wrapped_height(
                draw, body, fonts["small"], box_w - 36, profile["line_gap"]
            )
            heights.append(max(112, 18 + title_h + (8 if title else 0) + body_h + 18))
        row_h = max(heights)
        for col, raw_item in enumerate(row_items):
            title, body = normalize_fact_item(raw_item)
            bx = x + col * (box_w + gap)
            draw.rounded_rectangle(
                (bx, current_y, bx + box_w, current_y + row_h),
                radius=16,
                outline=palette["accent"],
                width=3,
            )
            text_y = current_y + 16
            if title:
                text_y = draw_wrapped(
                    draw,
                    title,
                    (bx + 18, text_y),
                    fonts["body_bold"],
                    palette["accent"],
                    box_w - 36,
                    line_gap=profile["line_gap"],
                ) + 6
            draw_wrapped(
                draw,
                body,
                (bx + 18, text_y),
                fonts["small"],
                palette["text"],
                box_w - 36,
                line_gap=profile["line_gap"],
            )
        current_y += row_h + gap
    return current_y


def draw_content(draw, page, page_number, total, deck, fonts, palette, size):
    width, height = size
    draw.rectangle((0, 0, width, height), fill=palette["background"])
    margin, top, right, bottom = draw_header_footer(draw, page_number, total, deck, fonts, palette, size)
    content_width = right - margin
    y = top
    section_title = page.get("section_title") or "接上页"
    profile = fonts["_profile"]
    y = draw_wrapped(
        draw,
        section_title,
        (margin, y),
        fonts["section"],
        palette["text"],
        content_width,
        line_gap=profile["line_gap"],
        max_lines=2,
        context=f"content page {page_number} section title",
    )
    y += profile["block_gap"]
    for block in page.get("blocks", []):
        y = draw_block(draw, block, margin, y, content_width, fonts, palette)
        if y > bottom:
            raise CardError(
                f"Content page {page_number} overflows the safe area by "
                f"{int(y - bottom)}px. Split the page, reduce copy, or use density 'dense'."
            )


def draw_ending(draw, page, deck, fonts, palette, size):
    width, height = size
    margin = int(width * 0.085)
    draw.rectangle((0, 0, width, height), fill=palette["background"])
    y = int(height * 0.18)
    title = page.get("title", "最后记住这句话")
    y = draw_wrapped(
        draw,
        title,
        (margin, y),
        fonts["section"],
        palette["text"],
        width - margin * 2,
        line_gap=14,
        max_lines=2,
        context="ending title",
    )
    y += 48
    for item in page.get("summary", []):
        draw.text((margin, y + 3), "•", font=fonts["body_bold"], fill=palette["accent"])
        y = draw_wrapped(
            draw,
            item,
            (margin + 46, y),
            fonts["body"],
            palette["text"],
            width - margin * 2 - 46,
            line_gap=10,
            max_lines=3,
            context="ending summary",
        )
        y += 22
    quote = page.get("quote")
    if quote:
        y += 24
        y = draw_wrapped(
            draw,
            quote,
            (margin, y),
            fonts["body_bold"],
            palette["accent"],
            width - margin * 2,
            line_gap=14,
            max_lines=4,
            context="ending quote",
        )
    if y > height - 150:
        raise CardError("Ending page overflows the safe area; shorten or split its copy.")
    draw.rectangle((0, height - 120, width, height), fill=palette["accent"])
    end_text = "END"
    tw, th = text_size(draw, end_text, fonts["body_bold"])
    draw.text(((width - tw) / 2, height - 82), end_text, font=fonts["body_bold"], fill=palette["background"])


def make_fonts(size, density="dense", font_path=None, bold_font_path=None):
    profile = layout_profile({"density": density}, size)
    return {
        "cover_title": load_font(
            profile["cover_title"], role="bold", font_path=font_path, bold_font_path=bold_font_path
        ),
        "section": load_font(
            profile["section"], role="bold", font_path=font_path, bold_font_path=bold_font_path
        ),
        "body": load_font(
            profile["body"], role="regular", font_path=font_path, bold_font_path=bold_font_path
        ),
        "body_bold": load_font(
            profile["body_bold"], role="bold", font_path=font_path, bold_font_path=bold_font_path
        ),
        "small": load_font(
            profile["small"], role="regular", font_path=font_path, bold_font_path=bold_font_path
        ),
        "micro": load_font(
            profile["micro"], role="regular", font_path=font_path, bold_font_path=bold_font_path
        ),
        "_profile": profile,
    }


def get_visual_source(page, deck):
    return cover_visual_source(page, deck)


def page_label(page_index, total):
    width = max(2, len(str(total)))
    return f"{page_index:0{width}d}/{total:0{width}d}"


def visible_character_count(page):
    ignored_keys = {
        "type",
        "visual_mode",
        "image_path",
        "image_prompt",
        "visual_concept",
        "visual_ratio",
        "theme_keywords",
    }

    def collect(value, key=None):
        if key in ignored_keys:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "".join(collect(item) for item in value)
        if isinstance(value, dict):
            return "".join(collect(item, item_key) for item_key, item in value.items())
        return ""

    return len("".join(collect(page).split()))


def write_manifest(deck, out_dir, size, font_path, bold_font_path=None, manifest_path=None):
    pages = []
    total = len(deck["pages"])
    for idx, page in enumerate(deck["pages"], 1):
        entry = {
            "index": idx,
            "type": page["type"],
            "file": f"page-{idx:02d}.png",
            "visual_source": get_visual_source(page, deck),
            "content_char_count": visible_character_count(page),
        }
        if page["type"] == "content":
            entry["section_title"] = page.get("section_title", "")
            entry["page_label"] = page_label(idx, total)
            entry["block_types"] = [block.get("type", "paragraph") for block in page.get("blocks", [])]
        if entry["visual_source"] == "ai-visual":
            entry["image_path"] = str(page.get("image_path", ""))
            entry["visual_concept"] = page.get("visual_concept", "")
            if page.get("theme_keywords"):
                entry["theme_keywords"] = page["theme_keywords"]
            if page.get("image_prompt"):
                entry["image_prompt"] = page["image_prompt"]
        if page.get("visual_ratio") is not None:
            entry["visual_ratio"] = float(page["visual_ratio"])
        pages.append(entry)
    manifest = {
        "title": deck["title"],
        "subtitle": deck.get("subtitle", ""),
        "audience": deck.get("audience", ""),
        "promise": deck.get("promise", ""),
        "angle": deck.get("angle", ""),
        "visual_brief": deck.get("visual_brief", ""),
        "density": deck["density"],
        "layout_system": "content-first-grid-v2",
        "size": list(size),
        "page_count": total,
        "palette": deck["palette"],
        "font_path": font_path or "auto",
        "font_bold_path": bold_font_path or "auto",
        "font_style": "four-level-cjk-sans",
        "pages": pages,
        "quality_checks": deck.get("quality_checks", []),
    }
    target = manifest_path or (out_dir / "manifest.json")
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def render_deck(deck, out_dir, size=DEFAULT_SIZE, font_path=None, bold_font_path=None, manifest_path=None, write_manifest_file=True, base_dir=None):
    deck = validate_deck(deck)
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = make_fonts(size, deck["density"], font_path, bold_font_path)
    palette = deck["palette"]
    total = len(deck["pages"])
    for idx, page in enumerate(deck["pages"], 1):
        image = Image.new("RGB", size, palette["background"])
        draw = ImageDraw.Draw(image)
        source = get_visual_source(page, deck)
        if source == "ai-visual":
            page_image = load_page_image(page, base_dir)
            if page["type"] == "cover":
                draw_ai_cover(draw, image, page, deck, fonts, palette, size, page_image)
            elif page["type"] == "ending":
                draw_ai_ending(draw, image, page, deck, fonts, palette, size, page_image)
            else:
                draw_ai_content(draw, image, page, idx, total, deck, fonts, palette, size, page_image)
        elif page["type"] == "cover":
            draw_cover(draw, image, page, deck, fonts, palette, size)
        elif page["type"] == "ending":
            draw_ending(draw, page, deck, fonts, palette, size)
        else:
            draw_content(draw, page, idx, total, deck, fonts, palette, size)
        image.save(out_dir / f"page-{idx:02d}.png")
    if write_manifest_file:
        write_manifest(deck, out_dir, size, font_path, bold_font_path, manifest_path)
    return total


def sample_deck():
    return {
        "title": "把知识变成行动",
        "subtitle": "一套适合小红书的知识卡片结构",
        "audience": "想把长内容做成小红书卡片的人",
        "promise": "用一条主线把知识压缩成可看完、可记住、可复述的卡片组",
        "angle": "从传播目标倒推卡片结构，而不是把原文机械分页",
        "density": "dense",
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
                "visual_mode": "ai-visual",
                "kicker": "知识卡片方法论",
                "visual_concept": "散乱的文章纸片经过漏斗重组为三张清晰卡片，并延伸成一条向前的行动路径",
                "theme_keywords": ["文章", "知识卡片", "行动"],
                "image_prompt": "Editorial illustration of scattered article fragments reorganizing into three clear cards and an action path; no text or letters; 3:4 vertical.",
            },
            {
                "type": "content",
                "section_title": "先抓主线",
                "blocks": [
                    {"type": "callout", "title": "核心判断", "text": "卡片不是压缩全文，而是提炼一条可传播的认知路径。"},
                    {"type": "steps", "items": ["找问题", "给框架", "落行动"]},
                    {
                        "type": "bullet_list",
                        "items": [
                            "每页围绕一个核心问题组织信息，不等于每页只能有一句话",
                            "标题说明本页回答什么，正文用短句、事实格和对比列讲透",
                            "能画成流程就不要堆段落，能并列比较就不要反复解释",
                            "保留事实、条件、数字和边界，删除只起修饰作用的重复句",
                            "内容装不下时拆成承接页，不缩小到难读，也不静默截断",
                        ],
                    },
                    {
                        "type": "fact_grid",
                        "items": [
                            {"title": "信息密度", "text": "默认 dense，一页可容纳 5—8 个短要点。"},
                            {"title": "排版原则", "text": "四级字阶、统一网格、固定安全边距。"},
                            {"title": "视觉比例", "text": "内容图默认只占 32%，让空间优先服务正文。"},
                            {"title": "溢出处理", "text": "渲染器直接报错，要求改写或拆页。"},
                        ],
                    },
                ],
            },
            {
                "type": "content",
                "section_title": "用图形承载逻辑",
                "visual_mode": "ai-visual",
                "visual_concept": "信息从输入节点经过结构化处理流向清晰的视觉输出",
                "visual_ratio": 0.30,
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
                "visual_mode": "ai-visual",
                "visual_concept": "一张完成的知识卡片向外扩散出清晰的同心波纹",
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


def make_placeholder(out_dir, idx, palette, size=DEFAULT_SIZE):
    """Create a deterministic abstract image so --sample can exercise ai-visual without ImageGen."""
    rng_state = [idx * 9301 + 49297]

    def rng():
        rng_state[0] = (rng_state[0] * 9301 + 49297) % 233280
        return rng_state[0] / 233280.0

    bg = _hex_to_rgb(palette["background"])
    accent = _hex_to_rgb(palette["accent"])
    text = _hex_to_rgb(palette["text"])
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    for y in range(size[1]):
        t = y / size[1]
        col = tuple(int(bg[c] * (1 - t * 0.7) + accent[c] * t * 0.55) for c in range(3))
        d.line([(0, y), (size[0], y)], fill=col)
    for _ in range(7):
        cx = int(rng() * size[0])
        cy = int(rng() * size[1] * 0.7)
        r = int(120 + rng() * 260)
        fill = tuple(int(accent[c] * (0.25 + rng() * 0.5)) for c in range(3))
        fill = tuple(min(255, c) for c in fill)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    for _ in range(4):
        x1 = int(rng() * size[0])
        y1 = int(rng() * size[1] * 0.6)
        x2 = int(rng() * size[0])
        y2 = int(rng() * size[1] * 0.6)
        d.line([(x1, y1), (x2, y2)], fill=tuple(int(text[c] * 0.5) for c in range(3)), width=6)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"placeholder-{idx:02d}.png"
    img.save(path)
    return path


def sample_with_assets(out_dir, size=DEFAULT_SIZE):
    deck = sample_deck()
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(deck["pages"], 1):
        if str(page.get("visual_mode") or "").strip().lower() == "ai-visual":
            page["image_path"] = str(make_placeholder(assets, i, deck["palette"], size))
    return deck


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render 3:4 Xiaohongshu knowledge cards.")
    parser.add_argument("--input", type=Path, help="Input card JSON file.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory.")
    parser.add_argument("--sample", action="store_true", help="Render a built-in sample deck.")
    parser.add_argument("--font", help="Override regular font file path (TTF/TTC).")
    parser.add_argument("--font-bold", dest="font_bold", help="Override bold font file path (TTF/TTC).")
    parser.add_argument("--manifest", type=Path, help="Manifest JSON path. Defaults to <out>/manifest.json.")
    parser.add_argument("--size", type=parse_size, default=DEFAULT_SIZE, help="Output size, default 1080x1440.")
    args = parser.parse_args(argv)

    try:
        if args.sample:
            deck = sample_with_assets(args.out, args.size)
        elif args.input:
            deck = json.loads(args.input.read_text(encoding="utf-8"))
        else:
            raise CardError("Provide --sample or --input")
        base_dir = args.input.parent if args.input else Path.cwd()
        count = render_deck(
            deck,
            args.out,
            args.size,
            args.font,
            args.font_bold,
            args.manifest,
            base_dir=base_dir,
        )
    except CardError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Render failed: {exc}", file=sys.stderr)
        return 1

    print(f"Rendered {count} pages to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
