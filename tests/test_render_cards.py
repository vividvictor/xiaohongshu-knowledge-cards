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
            self.assertEqual(manifest["pages"][0]["visual_source"], "code-graphic")
            self.assertEqual(manifest["font_style"], "bold-sans")

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


if __name__ == "__main__":
    unittest.main()
