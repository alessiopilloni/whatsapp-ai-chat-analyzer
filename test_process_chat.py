import unittest

from process_chat import sync_media_message


class ProcessChatMediaTest(unittest.TestCase):
    def test_sync_media_message_handles_media_types(self):
        message = (
            "cry: VID-20260812-WA0051.mp4 (file allegato) "
            "IMG-20260707-WA0011.jpg (file allegato) "
            "note.txt (file allegato)"
        )

        result = sync_media_message(message, audio_transcriptions={}, media_files={})

        self.assertIn("[Video Collegato]: VID-20260812-WA0051.mp4", result)
        self.assertIn("[Immagine Collegata]: IMG-20260707-WA0011.jpg", result)
        self.assertIn("[Documento di testo collegato]: note.txt", result)


if __name__ == "__main__":
    unittest.main()
