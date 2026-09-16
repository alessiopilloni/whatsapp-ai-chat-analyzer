"""Server HTTP locale e accesso sicuro ai file dell'export selezionato."""

import json
import mimetypes
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse

from audio_transcriber import transcribe_all_audio, transcribe_audio
from chat_parser import empty_chat_state, load_chat


def save_synchronized_chat(folder):
    """Salva la chat con gli allegati e le trascrizioni disponibili."""
    folder = Path(folder).resolve()
    data = load_chat(folder)
    if data.get("error"):
        return {"ok": False, "error": data["error"]}

    transcription_data = transcribe_all_audio(folder)
    results = transcription_data["results"]
    output = folder / "chat_completa_sincronizzata.txt"

    with output.open("w", encoding="utf-8") as stream:
        for message in data["messages"]:
            content = message["text"]
            for attachment in message["attachments"]:
                name = attachment["name"]
                if attachment["type"] == "audio" and name in results:
                    content += f"\n[Trascrizione Audio {name}]: {results[name]['text']}"
                elif attachment["type"] == "image":
                    content += f"\n[Immagine Collegata]: {name}"
                elif attachment["type"] == "video":
                    content += f"\n[Video Collegato]: {name}"
                elif attachment["type"] == "document":
                    content += f"\n[Documento collegato]: {name}"
            stream.write(
                f"[{message['timestamp']}] {message['sender']}:\n"
                f"{content}\n\n{'=' * 50}\n\n"
            )

    return {"ok": True, "filename": output.name, "path": str(output)}


def open_external(path):
    """Apre un allegato con l'applicazione predefinita del sistema operativo."""
    if os.name == "nt":
        os.startfile(path)
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def sys_platform():
    """Restituisce il nome della piattaforma, con fallback per sistemi senza os.uname."""
    return os.uname().sysname.lower() if hasattr(os, "uname") else ""


def choose_folder(current):
    """Mostra il selettore Tk in un processo separato dal server HTTP."""
    current = Path.home()
    dialog_code = (
        "import tkinter as tk; "
        "from tkinter import filedialog; "
        "root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True); "
        "selected = filedialog.askdirectory(initialdir=__import__('sys').argv[1], "
        "title=\"Scegli la cartella dell'export WhatsApp\"); "
        "root.destroy(); print(selected) if selected else None"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", dialog_code, str(current)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    selected = completed.stdout.strip()
    return Path(selected).resolve() if completed.returncode == 0 and selected else None


def create_handler(page):
    """Crea il gestore HTTP con la pagina frontend e la cartella condivisa."""
    class Handler(BaseHTTPRequestHandler):
        folder = None

        def log_message(self, fmt, *args):
            """Disabilita i log standard del server per mantenere pulito il terminale."""
            return

        def write_response(self, data):
            """Invia una risposta ignorando la disconnessione anticipata del browser."""
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def send_json(self, payload, status=200):
            """Serializza un payload Python e lo invia come risposta JSON."""
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            """Instrada le richieste della pagina, delle API e degli allegati."""
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path == "/":
                body = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.write_response(body)
                return
            if path == "/api/state":
                self.send_json(load_chat(self.folder) if self.folder else empty_chat_state())
                return
            if path == "/api/choose":
                selected = choose_folder(self.folder)
                if selected:
                    type(self).folder = selected
                self.send_json(load_chat(self.folder) if self.folder else empty_chat_state())
                return
            if path.startswith("/api/transcript/"):
                name = path.rsplit("/", 1)[1]
                self.send_json(transcribe_audio(self.folder, name))
                return
            if path == "/api/transcribe-all":
                self.send_json(transcribe_all_audio(self.folder))
                return
            if path == "/api/save":
                if not self.folder:
                    self.send_json({"ok": False, "error": "Nessuna cartella selezionata."}, 400)
                    return
                self.send_json(save_synchronized_chat(self.folder))
                return
            if path.startswith("/media/") or path.startswith("/open/"):
                self._serve_media(path)
                return
            self.send_error(404)

        def _serve_media(self, path):
            """Serve un allegato locale, supportando anche le richieste Range audio/video."""
            name = path.split("/", 2)[2]
            target = (self.folder / name).resolve()
            if target.parent != self.folder.resolve() or not target.is_file():
                self.send_error(404)
                return
            if path.startswith("/open/"):
                open_external(str(target))
                self.send_json({"ok": True})
                return
            try:
                size = target.stat().st_size
                range_header = self.headers.get("Range")
                start, end = 0, size - 1
                status = 200
                if range_header and range_header.startswith("bytes="):
                    start_text, end_text = range_header[6:].split("-", 1)
                    start = int(start_text or 0)
                    end = int(end_text) if end_text else size - 1
                    end = min(end, size - 1)
                    status = 206
                with target.open("rb") as media:
                    media.seek(start)
                    data = media.read(end - start + 1)
            except (OSError, ValueError):
                self.send_error(404)
                return
            content_type = (
                "audio/ogg"
                if target.suffix.lower() == ".opus"
                else mimetypes.guess_type(target.name)[0]
                or "application/octet-stream"
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Disposition", "inline")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            self.write_response(data)

    return Handler
