"""Modulo di supporto per leggere e strutturare un export WhatsApp.

Questo file prende un file di testo exportato da WhatsApp, riconosce i messaggi,
separa i dati di ogni conversazione e identifica allegati e link.

Il suo scopo è trasformare un testo grezzo in una struttura dati facilmente
utilizzabile da un'interfaccia web o da un'applicazione di analisi.

In chiave di esame, questo modulo rappresenta la parte di "preparazione dati":
prima di ogni analisi intelligente, serve ordinare e organizzare le informazioni.
"""

import re
from pathlib import Path

# Espressione regolare per riconoscere una riga di chat WhatsApp del tipo:
# "12/12/24, 20:30 - Nome: testo del messaggio"
# Serve a separare automaticamente timestamp, mittente e contenuto.
MESSAGE_RE = re.compile(r"^(\d{2}/\d{2}/\d{2,4},\s\d{2}:\d{2})\s-\s([^:]+):\s?(.*)$")

# Riconosce nomi di file presenti nel testo, come immagini, audio, video o documenti.
# Questi nomi vengono poi collegati ai file realmente presenti nella cartella.
FILE_RE = re.compile(r"[\u200e\u200f]?([\w .()'\-]+\.(?:opus|mp3|m4a|aac|wav|jpg|jpeg|png|webp|gif|bmp|mp4|mov|avi|mkv|webm|3gp|pdf|doc|docx|xls|xlsx|ppt|pptx|txt|md|csv|json|log|xml|html|htm|rtf))", re.I)

# Trova link HTTP/HTTPS nel testo di un messaggio per renderli cliccabili.
URL_RE = re.compile(r"https?://[^\s<>]+", re.I)

# Insiemi usati per classificare gli allegati in base all'estensione del file.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
AUDIO_EXTENSIONS = {".opus", ".mp3", ".m4a", ".aac", ".wav"}


def empty_chat_state():
    """Restituisce lo stato iniziale prima che l'utente scelga una cartella."""
    return {
        "folder": None,
        "chat_file": None,
        "messages": [],
        "error": "Scegli una cartella con un export WhatsApp.",
    }


def find_chat_file(folder):
    """Trova il file .txt principale della chat nella cartella selezionata."""
    # Cerca tutti i file di testo e preferisce quelli che hanno "chat" nel nome,
    # escludendo eventuali file di backup o versioni sincronizzate.
    candidates = sorted(Path(folder).glob("*.txt"))
    preferred = [
        path for path in candidates
        if "chat" in path.name.lower() and "sincronizzata" not in path.name.lower()
    ]
    return preferred[0] if preferred else (candidates[0] if candidates else None)


def attachment_type(filename):
    """Classifica un allegato come immagine, video, audio o documento."""
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    return "document"


def parse_chat_log(content, folder):
    """Trasforma il testo della chat in una lista di messaggi strutturati."""
    messages = []
    current = None
    # Mappa i file della cartella in modo da verificare se un allegato esiste davvero.
    files = {path.name: path for path in Path(folder).iterdir() if path.is_file()}

    def finish(message):
        """Conclude il messaggio corrente quando arriva la riga successiva."""
        if message is None:
            return

        attachments = []
        used = set()

        # Cerca eventuali file citati all'interno del testo del messaggio.
        for match in FILE_RE.finditer(message["text"]):
            name = match.group(1).strip()
            if name in used:
                continue
            used.add(name)
            attachments.append({
                "name": name,
                "type": attachment_type(name),
                "exists": name in files,
            })

        # Salva allegati e link in modo da poterli mostrare nell'interfaccia.
        message["attachments"] = attachments
        message["links"] = [
            url.rstrip(".,;:!?)]") for url in URL_RE.findall(message["text"])
        ]
        messages.append(message)

    # Scorre ogni riga del file e crea un messaggio quando trova una nuova voce.
    for raw_line in content.splitlines():
        match = MESSAGE_RE.match(raw_line)
        if match:
            finish(current)
            timestamp, sender, text = match.groups()
            current = {
                "timestamp": timestamp,
                "sender": sender.strip(),
                "text": text.strip(),
            }
        elif current is not None:
            # Le righe successive a un messaggio sono parte del suo testo.
            current["text"] += "\n" + raw_line.strip()

    finish(current)
    return messages


def load_chat(folder):
    """Carica la chat e prepara il contenuto in formato pronto per l'uso."""
    if folder is None:
        return empty_chat_state()

    folder = Path(folder)
    chat_file = find_chat_file(folder)

    if chat_file is None:
        return {
            "folder": str(folder.resolve()),
            "chat_file": None,
            "messages": [],
            "error": "Nessun file .txt di chat trovato nella cartella.",
        }

    try:
        # In molti casi il file WhatsApp usa la codifica UTF-8 con BOM.
        content = chat_file.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        # Se il testo è in una codifica diversa, si prova Latin-1.
        content = chat_file.read_text(encoding="latin-1")

    return {
        "folder": str(folder.resolve()),
        "chat_file": chat_file.name,
        "messages": parse_chat_log(content, folder),
        "error": None,
    }
