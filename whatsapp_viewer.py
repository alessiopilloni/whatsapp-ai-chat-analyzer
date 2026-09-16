#!/usr/bin/env python3
"""Punto di ingresso del viewer locale per gli export WhatsApp."""

import argparse
import json
import mimetypes
import os
import subprocess
import threading
import tkinter as tk
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import filedialog
from urllib.parse import unquote, urlparse

from audio_transcriber import transcribe_all_audio, transcribe_audio
from chat_parser import load_chat, parse_chat_log
from viewer_server import create_handler


def open_external(path):
    """Apre un file con il programma predefinito del sistema operativo."""
    if os.name == "nt":
        os.startfile(path)
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def sys_platform():
    """Restituisce il nome della piattaforma per la funzione open_external."""
    return os.uname().sysname.lower() if hasattr(os, "uname") else ""


# Pagina completa servita dal server: layout, stile e comportamento client.
PAGE = r'''<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WhatsApp Archive</title>
<style>
/* Variabili cromatiche e regole base dell'archivio. */
:root{--ink:#18342d;--muted:#6b7b75;--paper:#f4f1e9;--panel:#fffdf8;--mine:#d9f3d2;--accent:#d4573b;--line:#d9ddd4}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 Georgia,serif}
.app{min-height:100vh;display:grid;grid-template-columns:280px minmax(0,1fr);grid-template-rows:92px 1fr}.topbar{grid-column:1/-1;background:#18342d;color:#f8f4e8;display:flex;align-items:center;justify-content:space-between;padding:18px 28px}.brand{font:700 24px Georgia}.brand small{display:block;color:#a9c5b5;font:12px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em}.actions{display:flex;align-items:center;gap:12px}.choose,.bulk{border:1px solid #a9c5b5;background:transparent;color:#fffdf8;border-radius:4px;padding:10px 14px;cursor:pointer;font:600 13px ui-monospace,monospace}.bulk{background:#d4573b;border-color:#d4573b}.status{color:#d8eadb;font:11px ui-monospace,monospace}.sidebar{padding:26px 22px;border-right:1px solid var(--line);background:#ebe9df}.eyebrow{font:11px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.12em;color:var(--accent)}h1{font-size:28px;line-height:1.05;margin:9px 0 18px}.meta{color:var(--muted);font:12px ui-monospace,monospace;overflow-wrap:anywhere}.stats{margin-top:34px;padding-top:16px;border-top:1px solid #cbd1c7;display:grid;gap:8px}.stat{display:flex;justify-content:space-between}.stat b{font-size:18px}.chat{max-width:950px;width:100%;margin:0 auto;padding:34px clamp(18px,5vw,70px) 64px}.empty{margin:15vh auto;text-align:center;color:var(--muted);max-width:400px}.message{display:flex;margin:0 0 14px}.message.mine{justify-content:flex-end}.bubble{max-width:min(76%,650px);background:var(--panel);border:1px solid var(--line);border-radius:3px 14px 14px 14px;padding:11px 14px;box-shadow:0 2px 9px #18342d0b}.mine .bubble{background:var(--mine);border-radius:14px 3px 14px 14px}.sender{font:700 12px ui-monospace,monospace;color:var(--accent);margin-bottom:4px}.stamp{float:right;color:#789087;font:11px ui-monospace,monospace;margin:4px 0 0 18px}.body{white-space:pre-wrap;overflow-wrap:anywhere}.attachment{margin-top:10px}.attachment img,.attachment video{display:block;max-width:100%;max-height:430px;border-radius:3px}.attachment audio{width:min(100%,360px)}.transcribe{display:block;margin-top:7px;border:0;background:var(--accent);color:white;border-radius:3px;padding:6px 9px;cursor:pointer;font:600 11px ui-monospace,monospace}.transcript{margin-top:6px;color:var(--muted);font-size:13px;white-space:pre-wrap}.transcript.empty,.transcript.error{color:#9c5b4e}.attachment a,.external{display:inline-flex;gap:8px;align-items:center;color:var(--ink);font:600 13px ui-monospace,monospace;text-decoration:none;border-bottom:1px solid var(--accent);padding:5px 0}.missing{color:#9c5b4e;font-size:12px}.link{display:block;margin-top:7px;color:#256e66;overflow-wrap:anywhere}
@media(max-width:760px){.app{display:block}.topbar{position:sticky;top:0;z-index:2;padding:15px 16px}.brand{font-size:20px}.sidebar{padding:18px 16px;border-right:0;border-bottom:1px solid var(--line)}.stats{margin-top:18px;display:flex;gap:18px}.stats .stat{gap:6px;display:grid}.chat{padding:22px 12px 40px}.bubble{max-width:90%}}
</style></head><body><div class="app"><header class="topbar"><div class="brand">WhatsApp Archive<small>local media viewer</small></div><button class="choose" onclick="chooseFolder()">Scegli cartella</button></header><aside class="sidebar"><div class="eyebrow">Archivio aperto</div><h1 id="chatTitle">Nessuna chat</h1><div id="folder" class="meta">Scegli una cartella con un export WhatsApp.</div><div class="stats"><div class="stat"><span>Messaggi</span><b id="count">0</b></div><div class="stat"><span>Allegati</span><b id="mediaCount">0</b></div></div></aside><main id="chat" class="chat"><div class="empty">Scegli una cartella per visualizzare la conversazione.</div></main></div>
<script>
// Escape del testo proveniente dalla chat prima di inserirlo nell'HTML.
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Aggiunge il comando per trascrivere tutti i vocali nella barra superiore.
function ensureBatchControls(){const topbar=document.querySelector('.topbar');if(!topbar||document.getElementById('transcribeAll'))return;const actions=document.createElement('div');actions.className='actions';actions.innerHTML='<span id="status" class="status"></span><button id="transcribeAll" class="bulk">Trascrivi tutto</button><button id="saveChat" class="choose">Salva chat</button>';topbar.appendChild(actions);document.getElementById('transcribeAll').addEventListener('click',transcribeAll);document.getElementById('saveChat').addEventListener('click',saveChat)}
// Aggiorna il messaggio di stato mostrato durante le operazioni lunghe.
function setStatus(text){const element=document.getElementById('status');if(element)element.textContent=text}
// Salva la chat completa nella cartella dell'export selezionata.
async function saveChat(){const button=document.getElementById('saveChat');button.disabled=true;setStatus('Salvataggio in corso...');try{const response=await fetch('/api/save');const data=await response.json();setStatus(data.ok?'Salvata: '+data.filename:'Errore: '+data.error)}catch(error){setStatus('Errore durante il salvataggio')}finally{button.disabled=false}}
// Richiede la trascrizione batch al server e aggiorna ogni vocale visualizzato.
async function transcribeAll(){const button=document.getElementById('transcribeAll');button.disabled=true;setStatus('Trascrizione in corso...');try{const response=await fetch('/api/transcribe-all');const data=await response.json();let ok=0,empty=0,error=0;Object.entries(data.results).forEach(([name,result])=>{document.querySelectorAll('.attachment audio').forEach(audio=>{if(decodeURIComponent(audio.src.split('/').pop())===name){const target=audio.parentElement.querySelector('.transcript');if(target){target.textContent=result.text;target.className='transcript '+result.status}}});if(result.status==='ok')ok++;else if(result.status==='empty')empty++;else error++});setStatus('Completati: '+ok+' · vuoti: '+empty+' · errori: '+error)}catch(error){setStatus('Errore durante la trascrizione')}finally{button.disabled=false}}
// Chiede al server di aprire il selettore della cartella di importazione.
async function chooseFolder(){const r=await fetch('/api/choose');const data=await r.json();render(data)}
// Costruisce l'URL usato per servire un allegato locale.
function mediaUrl(name){return '/media/'+encodeURIComponent(name)}
// Richiede la trascrizione di un singolo vocale e la mostra nel relativo messaggio.
async function requestTranscript(name, target){target.textContent='Trascrizione in corso...';try{const response=await fetch('/api/transcript/'+encodeURIComponent(name));const result=await response.json();target.textContent=result.text;target.className='transcript '+result.status}catch(error){target.textContent='Errore nella trascrizione.';target.className='transcript error'}}
// Aggiorna intestazione, statistiche e lista dei messaggi ricevuti dal server.
function render(data){document.getElementById('chatTitle').textContent=data.chat_file||'Nessuna chat';document.getElementById('folder').textContent=data.folder||'Nessuna cartella selezionata';document.getElementById('count').textContent=data.messages.length;const attachments=data.messages.flatMap(m=>m.attachments);document.getElementById('mediaCount').textContent=attachments.length;const chat=document.getElementById('chat');if(data.error){chat.innerHTML='<div class="empty">'+esc(data.error)+'</div>';return}if(!data.messages.length){chat.innerHTML='<div class="empty">La chat non contiene messaggi riconoscibili.</div>';return}chat.innerHTML=data.messages.map((m,i)=>{const mine=i%2===1;const files=m.attachments.map(a=>{if(!a.exists)return '<div class="attachment missing">Allegato non trovato: '+esc(a.name)+'</div>';const url=mediaUrl(a.name);if(a.type==='image')return '<div class="attachment"><img loading="lazy" src="'+url+'" alt="'+esc(a.name)+'"></div>';if(a.type==='video')return '<div class="attachment"><video controls preload="metadata" src="'+url+'"></video></div>';if(a.type==='audio')return '<div class="attachment"><audio controls preload="metadata" src="'+url+'"></audio><button class="transcribe" data-name="'+esc(a.name)+'" onclick="requestTranscript(this.dataset.name,this.nextElementSibling)">Trascrivi vocale</button><div class="transcript"></div></div>';return '<div class="attachment"><a class="external" href="/open/'+encodeURIComponent(a.name)+'">↗ '+esc(a.name)+'</a></div>'}).join('');const links=m.links.map(u=>'<a class="link" href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(u)+'</a>').join('');return '<article class="message '+(mine?'mine':'')+'"><div class="bubble"><div class="sender">'+esc(m.sender)+'<span class="stamp">'+esc(m.timestamp)+'</span></div><div class="body">'+esc(m.text)+'</div>'+files+links+'</div></article>'}).join('')}
// Carica lo stato iniziale e apre automaticamente la selezione se manca una cartella.
ensureBatchControls();fetch('/api/state').then(r=>r.json()).then(data=>{render(data);if(!data.folder)chooseFolder()});
</script></body></html>'''


# Implementazione storica mantenuta nel file per compatibilità; l'avvio usa
# create_handler di viewer_server.py, che contiene il routing attivo.
class Handler(BaseHTTPRequestHandler):
    folder = Path.cwd()

    def log_message(self, fmt, *args):
        """Nasconde i log standard del server storico."""
        return

    def write_response(self, data):
        """Invia dati binari ignorando le disconnessioni del browser."""
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, payload, status=200):
        """Invia una risposta JSON dal gestore storico."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Gestisce le route della vecchia implementazione locale."""
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.write_response(body); return
        if path == "/api/state":
            self.send_json(load_chat(self.folder)); return
        if path == "/api/choose":
            selected = choose_folder(self.folder)
            if selected:
                self.folder = selected
            self.send_json(load_chat(self.folder)); return
        if path.startswith("/api/transcript/"):
            name = path.rsplit("/", 1)[1]
            self.send_json(transcribe_audio(self.folder, name)); return
        if path == "/api/transcribe-all":
            self.send_json(transcribe_all_audio(self.folder)); return
        if path.startswith("/media/") or path.startswith("/open/"):
            name = path.split("/", 2)[2]
            target = (self.folder / name).resolve()
            if target.parent != self.folder.resolve() or not target.is_file():
                self.send_error(404); return
            if path.startswith("/open/"):
                open_external(str(target)); self.send_json({"ok": True}); return
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
                self.send_error(404); return
            self.send_response(status); self.send_header("Content-Type", "audio/ogg" if target.suffix.lower() == ".opus" else mimetypes.guess_type(target.name)[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(data))); self.send_header("Accept-Ranges", "bytes"); self.send_header("Content-Disposition", "inline");
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers(); self.write_response(data); return
        self.send_error(404)


def choose_folder(current):
    """Apre il vecchio selettore Tkinter usato dall'implementazione storica."""
    result = []
    def dialog():
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        selected = filedialog.askdirectory(initialdir=str(current), title="Scegli la cartella dell'import WhatsApp")
        root.destroy()
        if selected: result.append(Path(selected).resolve())
    thread = threading.Thread(target=dialog)
    thread.start(); thread.join()
    return result[0] if result else None


def main():
    """Avvia il server HTTP locale e apre il viewer nel browser."""
    parser = argparse.ArgumentParser(description="Visualizzatore locale di chat WhatsApp")
    parser.add_argument("folder", nargs="?", default=None, help="Cartella iniziale dell'export WhatsApp")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    viewer_handler = create_handler(PAGE)
    viewer_handler.folder = None
    server = ThreadingHTTPServer(("127.0.0.1", args.port), viewer_handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"WhatsApp Viewer: {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiusura viewer.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
