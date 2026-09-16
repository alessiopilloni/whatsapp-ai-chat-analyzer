import tempfile
import unittest
from pathlib import Path

from whatsapp_viewer import load_chat, parse_chat_log


class WhatsAppViewerTests(unittest.TestCase):
    def test_parse_media_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in (
                "PTT-20260707-WA0003.opus",
                "IMG-20260707-WA0011.jpg",
                "VID-20260812-WA0051.mp4",
                "note.pdf",
            ):
                (folder / name).touch()

            messages = parse_chat_log(
                """06/07/26, 08:37 - silviapilloni: ‎PTT-20260707-WA0003.opus (file allegato)
06/07/26, 08:57 - silviapilloni: ‎IMG-20260707-WA0011.jpg (file allegato)
06/07/26, 09:00 - cry: ‎VID-20260812-WA0051.mp4 (file allegato)
06/07/26, 09:10 - cry: note.pdf (file allegato) https://example.com
""",
                folder,
            )

            self.assertEqual([m["attachments"][0]["type"] for m in messages], ["audio", "image", "video", "document"])
            self.assertEqual(messages[-1]["links"], ["https://example.com"])
            self.assertTrue(all(m["attachments"][0]["exists"] for m in messages))

    def test_load_chat_uses_chat_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Chat di prova.txt").write_text(
                "06/07/26, 10:00 - cry: Ciao\n", encoding="utf-8"
            )
            data = load_chat(folder)
            self.assertEqual(data["chat_file"], "Chat di prova.txt")
            self.assertEqual(data["messages"][0]["sender"], "cry")


if __name__ == "__main__":
    unittest.main()
