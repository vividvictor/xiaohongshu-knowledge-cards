import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PYTHON = r"C:\Users\1\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
SCRIPT = ROOT / "xiaohongshu-knowledge-cards" / "scripts" / "render_cards.py"


class RenderCardsTest(unittest.TestCase):
    def run_renderer(self, args):
        return subprocess.run(
            [PYTHON, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_sample_render_outputs_3_to_4_png_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "cards"
            result = self.run_renderer(["--sample", "--out", str(out_dir)])

            self.assertEqual(result.returncode, 0, result.stderr)
            pages = sorted(out_dir.glob("page-*.png"))
            self.assertGreaterEqual(len(pages), 3)
            for page in pages:
                with Image.open(page) as image:
                    self.assertEqual(image.size, (1080, 1440))

    def test_sample_render_writes_manifest_with_page_labels_and_strategy_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "cards"
            result = self.run_renderer(["--sample", "--out", str(out_dir)])

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["title"], "把知识变成行动")
            self.assertEqual(manifest["size"], [1080, 1440])
            self.assertEqual(manifest["page_count"], 4)
            self.assertEqual(manifest["audience"], "想把长内容做成小红书卡片的人")
            self.assertEqual(manifest["promise"], "用一条主线把知识压缩成可看完、可记住、可复述的卡片组")
            self.assertEqual(manifest["pages"][1]["page_label"], "02/04")
            self.assertEqual(manifest["pages"][0]["visual_source"], "ai-visual")
            self.assertIn("文章纸片", manifest["pages"][0]["visual_concept"])
            self.assertEqual(manifest["density"], "dense")
            self.assertEqual(manifest["layout_system"], "content-first-grid-v2")
            self.assertEqual(manifest["font_style"], "four-level-cjk-sans")
            self.assertGreater(manifest["pages"][1]["content_char_count"], 180)

    def test_custom_manifest_uses_numeric_page_labels_without_chinese(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "cards"
            manifest_path = Path(tmp) / "checks.json"
            result = self.run_renderer(["--sample", "--out", str(out_dir), "--manifest", str(manifest_path)])

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            labels = [page["page_label"] for page in manifest["pages"] if "page_label" in page]
            self.assertEqual(labels, ["02/04", "03/04"])
            self.assertFalse(any("页" in label or "第" in label or "共" in label for label in labels))

    def test_cover_without_visual_brief_uses_typographic_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            external_visual = tmp_path / "external.png"
            Image.new("RGB", (240, 240), "#00FF00").save(external_visual)
            card_json = tmp_path / "cards.json"
            card_json.write_text(
                json.dumps(
                    {
                        "title": "测试标题",
                        "visual_path": str(external_visual),
                        "palette": {
                            "background": "#FFFFFF",
                            "text": "#111111",
                            "accent": "#E5484D",
                        },
                        "pages": [
                            {"type": "cover", "title": "测试标题"},
                            {
                                "type": "content",
                                "section_title": "观点",
                                "blocks": [{"type": "paragraph", "text": "内容"}],
                            },
                            {"type": "ending", "summary": ["结束语"]},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out_dir = tmp_path / "out"
            result = self.run_renderer(["--input", str(card_json), "--out", str(out_dir)])

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["pages"][0]["visual_source"], "typographic")
            self.assertNotIn("visual_path", manifest["pages"][0])

    def test_palette_rejects_more_than_three_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            card_json = tmp_path / "cards.json"
            card_json.write_text(
                json.dumps(
                    {
                        "title": "测试标题",
                        "palette": {
                            "background": "#FFFFFF",
                            "text": "#111111",
                            "accent": "#E5484D",
                            "extra": "#00AA88",
                        },
                        "pages": [
                            {
                                "type": "cover",
                                "title": "测试标题",
                                "subtitle": "测试副标题",
                            },
                            {
                                "type": "content",
                                "section_title": "观点",
                                "blocks": [
                                    {
                                        "type": "paragraph",
                                        "text": "这是用于测试的内容。",
                                    }
                                ],
                            },
                            {
                                "type": "ending",
                                "summary": ["结束语"],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = self.run_renderer(["--input", str(card_json), "--out", str(tmp_path / "out")])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Palette must contain no more than 3 colors", result.stderr)

    def test_rejects_unknown_blocks_and_empty_content_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            card_json = tmp_path / "cards.json"
            card_json.write_text(
                json.dumps(
                    {
                        "title": "测试标题",
                        "palette": {
                            "background": "#FFFFFF",
                            "text": "#111111",
                            "accent": "#E5484D",
                        },
                        "pages": [
                            {"type": "cover", "title": "测试标题"},
                            {"type": "content", "section_title": "空内容", "blocks": []},
                            {"type": "content", "section_title": "未知块", "blocks": [{"type": "mystery", "text": "x"}]},
                            {"type": "ending", "summary": ["结束语"]},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = self.run_renderer(["--input", str(card_json), "--out", str(tmp_path / "out")])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Content page 2 must contain at least one block", result.stderr)

    def test_ai_cover_requires_topic_specific_visual_concept(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "cover.png"
            Image.new("RGB", (600, 800), "#446688").save(image_path)
            card_json = tmp_path / "cards.json"
            card_json.write_text(
                json.dumps(
                    {
                        "title": "动态封面测试",
                        "palette": {"background": "#FFFFFF", "text": "#111111", "accent": "#E5484D"},
                        "pages": [
                            {"type": "cover", "visual_mode": "ai-visual", "image_path": str(image_path)},
                            {"type": "content", "section_title": "正文", "blocks": [{"type": "paragraph", "text": "内容"}]},
                            {"type": "ending", "summary": ["结束语"]},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = self.run_renderer(["--input", str(card_json), "--out", str(tmp_path / "out")])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("visual_concept derived from the current source topic", result.stderr)

    def test_ai_cover_concept_must_reference_source_theme_keywords(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "cover.png"
            Image.new("RGB", (600, 800), "#446688").save(image_path)
            card_json = tmp_path / "cards.json"
            card_json.write_text(
                json.dumps(
                    {
                        "title": "火星移民",
                        "palette": {"background": "#FFFFFF", "text": "#111111", "accent": "#E5484D"},
                        "pages": [
                            {
                                "type": "cover",
                                "visual_mode": "ai-visual",
                                "image_path": str(image_path),
                                "theme_keywords": ["火星", "移民"],
                                "visual_concept": "抽象的纸片变成卡片",
                            },
                            {"type": "content", "section_title": "正文", "blocks": [{"type": "paragraph", "text": "内容"}]},
                            {"type": "ending", "summary": ["结束语"]},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = self.run_renderer(["--input", str(card_json), "--out", str(tmp_path / "out")])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("theme_keywords term from the current source", result.stderr)

    def test_dense_layout_keeps_high_information_page_and_fact_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            long_copy = "高密度知识卡需要保留事实、条件、方法和边界，同时用短句与清晰层级降低阅读负担。" * 7
            card_json = tmp_path / "cards.json"
            card_json.write_text(
                json.dumps(
                    {
                        "title": "高密度排版",
                        "density": "dense",
                        "palette": {"background": "#F8F5EF", "text": "#202A35", "accent": "#D94A38"},
                        "pages": [
                            {"type": "cover", "title": "高密度排版"},
                            {
                                "type": "content",
                                "section_title": "一页容纳更多有效信息",
                                "blocks": [
                                    {"type": "paragraph", "text": long_copy},
                                    {
                                        "type": "fact_grid",
                                        "items": [
                                            {"title": "字阶", "text": "标题、正文、强调、元信息四级。"},
                                            {"title": "网格", "text": "统一边距与模块间距。"},
                                        ],
                                    },
                                ],
                            },
                            {"type": "ending", "summary": ["信息多不等于排版乱。"]},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out_dir = tmp_path / "out"

            result = self.run_renderer(["--input", str(card_json), "--out", str(out_dir)])

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertGreater(manifest["pages"][1]["content_char_count"], 250)
            self.assertIn("fact_grid", manifest["pages"][1]["block_types"])

    def test_content_overflow_fails_instead_of_dropping_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            card_json = tmp_path / "cards.json"
            card_json.write_text(
                json.dumps(
                    {
                        "title": "溢出测试",
                        "density": "dense",
                        "palette": {"background": "#FFFFFF", "text": "#111111", "accent": "#E5484D"},
                        "pages": [
                            {"type": "cover", "title": "溢出测试"},
                            {
                                "type": "content",
                                "section_title": "不能静默丢字",
                                "blocks": [
                                    {"type": "paragraph", "text": "这段文字必须完整保留。" * 160},
                                    {"type": "callout", "title": "最后一个模块", "text": "不能被跳过。"},
                                ],
                            },
                            {"type": "ending", "summary": ["结束语"]},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = self.run_renderer(["--input", str(card_json), "--out", str(tmp_path / "out")])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("overflows the safe area", result.stderr)


if __name__ == "__main__":
    unittest.main()
