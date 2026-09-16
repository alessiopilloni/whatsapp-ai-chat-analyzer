"""Servizio di trascrizione audio che usa AI per leggere i messaggi vocali.

Questo modulo è il cuore dell'uso dell'intelligenza artificiale nel progetto:
trasforma file audio come .opus o .mp3 in testo scritto in italiano, così da poter
inserire i contenuti vocali all'interno della chat come se fossero messaggi normali.

In termini di esame, questo file mostra come l'IA non sostituisce il codice,
ma lo arricchisce: il programma prepara i file, chiama Whisper e poi salva il risultato.
"""

import os
import shutil
import tempfile
import threading
from pathlib import Path

from chat_parser import AUDIO_EXTENSIONS

# Cache delle trascrizioni già completate nella sessione attuale.
# In questo modo il sistema non rifà lo stesso lavoro più volte.
TRANSCRIPTIONS = {}
# Il modello Whisper viene caricato una sola volta per risparmiare tempo e risorse.
WHISPER_MODEL = None
# Blocca il caricamento concorrente del modello in caso di richieste multiple.
WHISPER_LOCK = threading.Lock()


def ensure_ffmpeg():
    """Assicura che ffmpeg sia disponibile per leggere correttamente i file audio."""
    if shutil.which("ffmpeg") is not None:
        return
    try:
        import imageio_ffmpeg

        ffmpeg_dir = tempfile.mkdtemp(prefix="whisper-ffmpeg-")
        os.symlink(imageio_ffmpeg.get_ffmpeg_exe(), os.path.join(ffmpeg_dir, "ffmpeg"))
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except (ImportError, OSError, RuntimeError):
        # Se ffmpeg non è disponibile, la trascrizione potrebbe fallire.
        pass


def transcribe_audio(folder, filename):
    """Trascrive un file audio e restituisce il testo riconosciuto con uno stato."""
    global WHISPER_MODEL

    folder = Path(folder).resolve()
    target = (folder / filename).resolve()

    if target.parent != folder or not target.is_file():
        return {"status": "error", "text": "Audio non trovato."}
    if target.stat().st_size == 0:
        return {
            "status": "empty",
            "text": "File audio vuoto: serve riesportare o ricopiare il vocale originale.",
        }
    if filename in TRANSCRIPTIONS:
        return {"status": "ok", "text": TRANSCRIPTIONS[filename]}

    try:
        import whisper

        ensure_ffmpeg()
        with WHISPER_LOCK:
            if WHISPER_MODEL is None:
                WHISPER_MODEL = whisper.load_model("turbo")
            result = WHISPER_MODEL.transcribe(str(target), language="it", fp16=False)

        # Se il modello non riconosce il parlato, inserisce un messaggio di fallback.
        text = result["text"].strip() or "[Nessun parlato riconosciuto]"
        TRANSCRIPTIONS[filename] = text
        return {"status": "ok", "text": text}
    except Exception as exc:
        return {"status": "error", "text": f"Trascrizione non disponibile: {exc}"}


def transcribe_all_audio(folder):
    """Trascrive tutti gli audio presenti nella cartella e ritorna i risultati."""
    audio_files = sorted(
        path.name
        for path in Path(folder).iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    results = {}
    for index, filename in enumerate(audio_files, 1):
        result = transcribe_audio(folder, filename)
        results[filename] = result
        print(f"Trascrizione {index}/{len(audio_files)}: {filename} -> {result['status']}")
    return {"results": results, "total": len(audio_files)}
