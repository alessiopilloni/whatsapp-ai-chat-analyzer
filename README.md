# WhatsApp AI Chat Analyzer

Questo progetto analizza una chat WhatsApp esportata in formato testo e arricchisce i messaggi con informazioni utili, come allegati e trascrizioni dei messaggi vocali.

## Obiettivo

L'applicazione è pensata per trasformare una conversazione WhatsApp in un file più completo e leggibile, integrando:

- messaggi testuali della chat,
- riferimenti ai file multimediali,
- trascrizioni automatiche dei messaggi vocali tramite intelligenza artificiale.

## Funzionalità principali

- lettura dell'export WhatsApp in formato `.txt`,
- riconoscimento dei messaggi con timestamp e mittente,
- individuazione di allegati e link,
- trascrizione di file audio con Whisper,
- generazione di una chat finale sincronizzata e leggibile.

## Struttura dei file

- `chat_parser.py`: legge e struttura la chat in messaggi organizzati.
- `audio_transcriber.py`: trascrive i file audio usando l'IA di Whisper.
- `process_chat.py`: unisce chat, allegati e trascrizioni in un file finale.
- `requirements.txt`: dipendenze del progetto.
- `.gitignore`: file ignorati da Git.

## Requisiti

Per eseguire il progetto è necessario Python 3.10+ e le dipendenze riportate in `requirements.txt`.

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Esecuzione

Per generare la chat completa sincronizzata:

```bash
.venv/bin/python process_chat.py
```

In alternativa, è possibile passare una cartella specifica:

```bash
.venv/bin/python process_chat.py /percorso/della/cartella

Per avviare l'interfaccia grafica locale:

```bash
.venv/bin/python whatsapp_viewer.py
```
```

## Uso dell'intelligenza artificiale

Il progetto usa OpenAI Whisper per convertire i messaggi vocali in testo, consentendo di includere anche i contenuti audio dentro la conversazione. Questo rende la chat più completa e più semplice da analizzare, archiviare e consultare.

## Note

Il progetto è stato pensato come esempio pratico di integrazione tra:

- dati testuali,
- file multimediali,
- applicazioni AI per elaborazione del linguaggio e audio.
