"""Pipeline principale per trasformare una chat WhatsApp in una versione completa.

Questo script unisce tre elementi: la chat testuale, i file multimediali presenti
nella cartella e le trascrizioni generate dall'IA.

L'obiettivo finale è produrre un file text-only dove ogni messaggio viene arricchito
con informazioni sugli allegati e, soprattutto, con il testo letto dagli audio.

Questa è la parte più "intelligente" del progetto: qui si usa l'IA di Whisper
per trasformare messaggi vocali in testo leggibile e inserirli nella conversazione.
"""

import os
import re
import shutil
import tempfile
import argparse

import pandas as pd
import torch
import whisper

# Tipi di file che possono essere trovati nella cartella dell'export.
AUDIO_EXTENSIONS = (".opus", ".mp3", ".m4a", ".aac", ".wav")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp")
TEXT_DOCUMENT_EXTENSIONS = (
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".log",
    ".xml",
    ".html",
    ".htm",
    ".rtf",
)

# Pattern usato per riconoscere le righe della chat WhatsApp e i file allegati citati.
MESSAGE_PATTERN = re.compile(r'^(\d{2}/\d{2}/\d{2,4},\s\d{2}:\d{2})\s-\s([^:]+):\s(.*)$')
MEDIA_FILENAME_PATTERN = re.compile(
    r'([\w\-]+\.(?:opus|mp3|m4a|aac|wav|jpg|jpeg|png|webp|gif|bmp|mp4|mov|avi|mkv|webm|3gp|txt|md|csv|json|log|xml|html|htm|rtf))',
    re.IGNORECASE,
)


def ensure_ffmpeg_for_whisper():
    """Controlla che ffmpeg sia disponibile per far lavorare Whisper correttamente."""
    # Whisper usa ffmpeg per leggere file audio in molti formati, incluso .opus.
    if shutil.which("ffmpeg") is not None:
        return

    try:
        import imageio_ffmpeg

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = tempfile.mkdtemp(prefix="whisper-ffmpeg-")
        os.symlink(ffmpeg_path, os.path.join(ffmpeg_dir, "ffmpeg"))
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except (ImportError, OSError, RuntimeError):
        # Se ffmpeg non è disponibile, il programma continua ma potrebbe fallire.
        pass


def load_audio_transcriptions():
    """Usa l'intelligenza artificiale Whisper per trascrivere tutti gli audio della cartella."""
    # Questa è la fase più avanzata del progetto: i file vocali vengono trasformati in
    # testo e diventano parte della conversazione. In sede di tesina, questa sezione
    # rappresenta l'uso concreto dell'IA come supporto all'analisi di messaggi non testuali.
    ensure_ffmpeg_for_whisper()

    # Sceglie GPU se disponibile, altrimenti CPU.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Esecuzione su dispositivo: {device}")
    if device == "cuda":
        print(f"GPU in uso: {torch.cuda.get_device_name(0)}")

    print("Caricamento del modello Whisper...")
    # Whisper è il modello AI usato per riconoscere il parlato dai file audio.
    model = whisper.load_model("turbo", device=device)

    audio_transcriptions = {}
    audio_files = [f for f in os.listdir('.') if f.lower().endswith(AUDIO_EXTENSIONS)]
    audio_files.sort()

    print(f"Trovati {len(audio_files)} file audio. Inizio trascrizione...")

    for idx, filename in enumerate(audio_files, 1):
        print(f"[{idx}/{len(audio_files)}] Trascrizione audio: {filename}...")
        try:
            # Transcribe trasforma il file audio in testo in italiano.
            result = model.transcribe(filename, language="it", fp16=(device == "cuda"))
            audio_transcriptions[filename] = result["text"].strip()
        except Exception as e:
            print(f"Errore su {filename}: {e}")
            audio_transcriptions[filename] = "[Errore nella trascrizione]"

    return audio_transcriptions


def collect_media_files():
    """Raccoglie i file multimediali presenti nella cartella per associarli ai messaggi."""
    files = {
        "images": {f for f in os.listdir('.') if f.lower().endswith(IMAGE_EXTENSIONS)},
        "videos": {f for f in os.listdir('.') if f.lower().endswith(VIDEO_EXTENSIONS)},
        "documents": {f for f in os.listdir('.') if f.lower().endswith(TEXT_DOCUMENT_EXTENSIONS)},
    }
    return files


def sync_media_message(message, audio_transcriptions=None, media_files=None):
    """Inserisce nel testo del messaggio il nome e la trascrizione di audio o allegati collegati."""
    # Questa funzione è il punto di integrazione tra i tre livelli del sistema:
    # - chat testuale,
    # - file multimediali presenti nella cartella,
    # - trascrizioni generate dall'IA.
    # L'obiettivo è rendere la conversazione "completa" anche quando i contenuti sono
    # vocali o allegati non testuali.
    audio_transcriptions = audio_transcriptions or {}
    media_files = media_files or {"images": set(), "videos": set(), "documents": set()}

    found_files = MEDIA_FILENAME_PATTERN.findall(message)
    extra_content = []

    for media_file in found_files:
        file_name = media_file.strip()
        lower_name = file_name.lower()

        # Se nel messaggio è citato un audio, si aggiunge la trascrizione IA.
        if file_name in audio_transcriptions:
            extra_content.append(f"\n[Trascrizione Audio {file_name}]: {audio_transcriptions[file_name]}")
            continue

        # Altrimenti si indicano gli allegati come immagine, video o documento.
        if lower_name.endswith(IMAGE_EXTENSIONS):
            extra_content.append(f"\n[Immagine Collegata]: {file_name}")
            continue

        if lower_name.endswith(VIDEO_EXTENSIONS):
            extra_content.append(f"\n[Video Collegato]: {file_name}")
            continue

        if lower_name.endswith(TEXT_DOCUMENT_EXTENSIONS):
            extra_content.append(f"\n[Documento di testo collegato]: {file_name}")
            continue

        if file_name in media_files.get("images", set()):
            extra_content.append(f"\n[Immagine Collegata]: {file_name}")
            continue

        if file_name in media_files.get("videos", set()):
            extra_content.append(f"\n[Video Collegato]: {file_name}")
            continue

        if file_name in media_files.get("documents", set()):
            extra_content.append(f"\n[Documento di testo collegato]: {file_name}")
            continue

    # Se non sono stati trovati riferimenti espliciti, cerca comunque un audio
    # il cui nome è citato nel messaggio e lo aggiunge in fondo. Questo fallback
    # rende il sistema più robusto rispetto a export leggermente diversi e mantiene
    # l'informazione anche quando la struttura del messaggio non è perfetta.
    if not extra_content:
        for audio_file, text in audio_transcriptions.items():
            if audio_file in message:
                extra_content.append(f"\n[Trascrizione Audio {audio_file}]: {text}")

    if extra_content:
        return message + "".join(extra_content)
    return message


def sync_media(row, audio_transcriptions=None, media_files=None):
    """Funzione di supporto per applicare l'arricchimento a una riga del DataFrame."""
    return sync_media_message(row["message"], audio_transcriptions=audio_transcriptions, media_files=media_files)


def parse_chat_file(chat_file):
    """Legge il file della chat e lo trasforma in una lista di messaggi."""
    chat_data = []

    if not os.path.exists(chat_file):
        return chat_data

    with open(chat_file, 'r', encoding='utf-8') as f:
        current_entry = None
        for line in f:
            match = MESSAGE_PATTERN.match(line)
            if match:
                if current_entry:
                    chat_data.append(current_entry)
                timestamp, sender, text = match.groups()
                current_entry = {'timestamp': timestamp, 'sender': sender, 'message': text}
            else:
                if current_entry:
                    current_entry['message'] += f"\n{line.strip()}"
        if current_entry:
            chat_data.append(current_entry)

    return chat_data


def find_chat_file():
    """Trova il file TXT della chat senza dipendere dal nome dell'esportazione."""
    candidates = sorted(
        filename
        for filename in os.listdir('.')
        if filename.lower().endswith('.txt')
        and filename.lower() != 'chat_completa_sincronizzata.txt'
    )
    preferred = [filename for filename in candidates if 'chat' in filename.lower()]
    return preferred[0] if preferred else (candidates[0] if candidates else None)


def main():
    """Esegue la procedura completa e crea un file di chat sincronizzata."""
    parser = argparse.ArgumentParser(description="Integra chat e allegati WhatsApp")
    parser.add_argument("folder", nargs="?", default=".", help="Cartella dell'export WhatsApp")
    args = parser.parse_args()

    # Il programma lavora dentro la cartella scelta dall'utente: l'idea è ottenere
    # un ambiente locale e controllato dove la chat, i media e le trascrizioni possono
    # essere elaborati come un unico dataset coerente.
    folder = os.path.abspath(os.path.expanduser(args.folder))
    os.chdir(folder)

    # Prima fase: trascrizione IA degli audio.
    audio_transcriptions = load_audio_transcriptions()
    media_files = collect_media_files()
    chat_file = find_chat_file()
    chat_data = parse_chat_file(chat_file) if chat_file else []
    df = pd.DataFrame(chat_data)

    # A questo punto la pipeline lavora su un DataFrame: la conversazione viene
    # arricchita in modo da trasformare una chat semplice in un archivio analizzabile
    # e facilmente consultabile.

    if df.empty:
        print("Nessun messaggio trovato o file di chat non presente.")
        return

    # Seconda fase: arricchimento dei messaggi con media e trascrizioni.
    df["full_content"] = df.apply(
        sync_media,
        axis=1,
        audio_transcriptions=audio_transcriptions,
        media_files=media_files,
    )

    # Terza fase: salvataggio in un file finale, leggibile e completo.
    output_filename = 'chat_completa_sincronizzata.txt'
    with open(output_filename, 'w', encoding='utf-8') as f:
        for _, row in df.iterrows():
            f.write(f"[{row['timestamp']}] {row['sender']}:\n{row['full_content']}\n\n{'='*50}\n\n")

    print(f"Completato! Chat integrata e salvata in '{output_filename}'.")


if __name__ == "__main__":
    main()

