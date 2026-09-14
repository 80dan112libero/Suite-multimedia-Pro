import os
import json
import time
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
import subprocess
from urllib.parse import unquote, urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry
    from tqdm import tqdm
    import urllib3
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
                               QHBoxLayout, QLineEdit, QPushButton, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QMenu, QCheckBox)
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
    from PyQt6.QtGui import QFont
except ImportError as e:
    print(f"\n[ERRORE] Libreria mancante: {e}")
    print("Esegui: pip install PyQt6 requests tqdm urllib3 yt-dlp")
    input("\nPremi Invio per uscire...")
    sys.exit(1)

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

class DownloadSignals(QObject):
    progress = pyqtSignal(str, object, object, float) # Usa object per evitare overflow 32-bit (>2GB)
    finished = pyqtSignal(str, str)      # url, path
    error = pyqtSignal(str, str)         # url, message

class DownloadManager(QObject):
    def __init__(self, num_connections=8, state_file="download_state.json", verify_ssl=False):
        super().__init__()
        self.signals = DownloadSignals()
        self.num_connections = num_connections

        # Imposta un percorso assoluto per il file di stato per evitare errori di permessi
        if not os.path.isabs(state_file):
            base_path = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
            self.state_file = os.path.join(base_path, state_file)
        else:
            self.state_file = state_file

        self.chunk_size = 1024 * 1024  # 1MB per chunk
        self.verify_ssl = verify_ssl
        self.stop_event = threading.Event()
        self.stop_events = {} # Mappa url -> Event per pause individuali
        self.lock = threading.Lock()
        self.start_times = {} # Per tracciare l'inizio della sessione di download
        
        # Impostazioni predefinite
        self.settings = {"dest_folder": os.path.join(os.path.expanduser("~"), "Downloads")}
        
        self.state = self._load_state()

        # Setup a robust session with retries and a browser-like User-Agent
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        retry_strategy = Retry(
            total=10,  # Aumentato il numero di tentativi
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        self.session.trust_env = False  # Evita ritardi dovuti a proxy di sistema

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                # Gestione nuova struttura (settings + downloads)
                if isinstance(data, dict) and "downloads" in data:
                    self.settings.update(data.get("settings", {}))
                    return data["downloads"]
                # Compatibilità con vecchio formato (solo lista download)
                return data
        return {}

    def _save_state(self):
        with self.lock:
            try:
                combined_data = {
                    "settings": self.settings,
                    "downloads": self.state
                }
                with open(self.state_file, 'w') as f:
                    json.dump(combined_data, f, indent=4)
            except PermissionError:
                print(f"Avviso: Accesso negato al file di stato {self.state_file}. Assicurati che non sia aperto in un altro programma.")

    def _download_segment(self, url, start, end, filename, progress_bar):
        current_pos = start
        max_retries = 5
        attempt = 0

        while current_pos <= end and attempt < max_retries:
            if self.stop_event.is_set() or self.stop_events.get(url, threading.Event()).is_set(): return
            
            headers = {'Range': f'bytes={current_pos}-{end}'}
            try:
                with self.session.get(url, headers=headers, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    
                    # Verifica e aggiorna la dimensione totale se era 0 o se è stata rilevata una dimensione maggiore
                    with self.lock:
                        h = response.headers
                        cr = h.get('Content-Range')
                        cl = h.get('Content-Length')
                        
                        current_total_in_state = self.state[url].get('total', 0)

                        if cr and '/' in cr: # Esempio: bytes 0-0/4500000000
                            try: 
                                detected_total = int(cr.split('/')[-1].strip())
                                if detected_total > current_total_in_state: # Aggiorna solo se maggiore
                                    self.state[url]['total'] = detected_total
                            except: pass
                        elif cl and response.status_code == 200: # Se è 200 OK, Content-Length è il totale
                            detected_total = int(cl)
                            if detected_total > current_total_in_state: # Aggiorna solo se maggiore
                                self.state[url]['total'] = detected_total

                    with open(filename, "r+b") as f:
                        f.seek(current_pos)
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if self.stop_event.is_set() or self.stop_events.get(url, threading.Event()).is_set(): break
                            if chunk:
                                f.write(chunk)
                                chunk_len = len(chunk)
                                current_pos += chunk_len
                                with self.lock:
                                    self.state[url]['downloaded'] += chunk_len
                                    # Calcolo velocità basato sui byte scaricati nella sessione corrente
                                    start_time = self.start_times.get(url, time.time())
                                    elapsed = time.time() - start_time
                                    initial_at_start = self.state[url].get('initial_at_start', 0)
                                    downloaded_in_session = self.state[url]['downloaded'] - initial_at_start
                                    speed = downloaded_in_session / elapsed if elapsed > 0 else 0
                                    
                                    total_size = self.state[url].get('total', 0)
                                    self.signals.progress.emit(url, self.state[url]['downloaded'], total_size, speed)
                break # Successo
            except (requests.exceptions.RequestException, Exception) as e:
                attempt += 1
                if attempt >= max_retries:
                    self.signals.error.emit(url, f"Connessione persa: {str(e)}")
                    break
                time.sleep(attempt * 1) # Backoff esponenziale

    def download(self, url, dest_folder=None, download_playlist=False):
        self.stop_event.clear()
        with self.lock:
            if url not in self.stop_events:
                self.stop_events[url] = threading.Event()
            self.stop_events[url].clear()
        if dest_folder is None:
            dest_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            
        # Supporto Torrent (Magnet o file .torrent)
        if url.startswith('magnet:') or url.lower().endswith('.torrent'):
            self.download_torrent(url, dest_folder)
            return

        # Supporto YouTube
        if "youtube.com" in url or "youtu.be" in url:
            if yt_dlp is None:
                self.signals.error.emit(url, "yt-dlp non installata. Esegui: pip install yt-dlp")
                return
            self._youtube_download(url, dest_folder, download_playlist)
            return

        try:
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder, exist_ok=True)
        except PermissionError as e:
            self.signals.error.emit(url, "Accesso negato alla cartella.")
            return
            
        # Referer dinamico
        try:
            parsed_url = urlparse(url)
            self.session.headers.update({"Referer": f"{parsed_url.scheme}://{parsed_url.netloc}/"})
        except: 
            self.session.headers.update({"Referer": "https://www.google.com/"})

        # Forza download singolo se il link contiene token (spesso incompatibili con multi-thread)
        is_dynamic_link = "token=" in url.lower() or "key=" in url.lower() or "expires=" in url.lower()
        
        file_size = 0
        accept_ranges = False
        headers = {}

        # Se non è un link dinamico, prova a recuperare le info in anticipo
        if not is_dynamic_link:
            try:
                # 1. Prova HEAD per ottenere info basilari
                with self.session.head(url, allow_redirects=True, timeout=10) as resp:
                    if resp.status_code < 400:
                        headers = resp.headers
                        file_size = int(headers.get('Content-Length', 0))
                        accept_ranges = headers.get('Accept-Ranges', '').lower() == 'bytes'

                # 2. Prova un probe Range 0-0 (Fondamentale per correggere overflow 32-bit su file > 4GB)
                probe_headers = {"Range": "bytes=0-0"}
                with self.session.get(url, headers=probe_headers, allow_redirects=True, timeout=10, stream=True) as resp:
                    if resp.status_code == 206:
                        headers = resp.headers
                        cr = headers.get('Content-Range', '')
                        if '/' in cr:
                            try:
                                total_part = cr.split('/')[-1].strip() # Estrae il totale reale dopo lo slash
                                if total_part and total_part != '*':
                                    detected_size = int(total_part)
                                    # Se detected_size > file_size, abbiamo corretto l'overflow del server
                                    if detected_size > file_size:
                                        file_size = detected_size
                            except: pass
                        accept_ranges = True
                    elif resp.status_code == 200 and file_size <= 0:
                        headers = resp.headers
                        file_size = int(headers.get('Content-Length', 0))
                        accept_ranges = headers.get('Accept-Ranges', '').lower() == 'bytes'
            except Exception:
                pass # Ignora errori qui, proveremo nel download effettivo

        # Estrazione nome file robusta
        clean_name = "downloaded_file"
        # Assicurati che 'headers' sia un dizionario valido prima di accedervi
        if headers and 'Content-Disposition' in headers:
            match = re.search(r'filename\*?=(?:UTF-8\'\')?\"?([^";]+)\"?', headers['Content-Disposition'])
            if match:
                clean_name = unquote(match.group(1))
        
        # Se il nome è ancora generico, prova dall'URL
        if clean_name == "downloaded_file":
            clean_name = url.split("/")[-1].split("?")[0] or "downloaded_file"
        
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name)
        filename = os.path.join(dest_folder, clean_name)

        if file_size < 2000 and "text/html" in headers.get('Content-Type', ''):
            self.signals.error.emit(url, "Il server ha restituito una pagina HTML invece del file.")
            return

        # Gestione Resume
        initial_on_disk = os.path.getsize(filename) if os.path.exists(filename) else 0

        self.start_times[url] = time.time()
        with self.lock:
            if url not in self.state:
                self.state[url] = {'downloaded': initial_on_disk, 'total': file_size, 'path': filename, 'type': 'http'}
            else:
                self.state[url]['downloaded'] = initial_on_disk
                # Aggiorna il totale solo se il nuovo file_size è maggiore o se il totale attuale è 0
                current_total_in_state = self.state[url].get('total', 0)
                if file_size > 0 and (current_total_in_state == 0 or file_size > current_total_in_state):
                    self.state[url]['total'] = file_size
            # Salva il punto di partenza per il calcolo della velocità sessione
            self.state[url]['initial_at_start'] = initial_on_disk

        # Se file_size è piccolo, o i range non sono supportati, o è un link dinamico, o file_size è 0 (sconosciuto), usa il download semplice
        if file_size < 1024 * 50 or not accept_ranges or is_dynamic_link or file_size == 0:
            self._simple_download(url, filename, total_size=file_size if file_size > 0 else None, initial_downloaded=initial_on_disk)
            if not (self.stop_event.is_set() or self.stop_events.get(url, threading.Event()).is_set()):
                self.signals.finished.emit(url, filename)
            return

        # Per il download multi-thread, azzeriamo il progresso perché i segmenti 
        # sovrascrivono il file dalle posizioni iniziali predefinite.
        with self.lock:
            self.state[url]['downloaded'] = 0
            self.state[url]['initial_at_start'] = 0

        with open(filename, "wb") as f:
            f.truncate(file_size)

        segment_size = file_size // self.num_connections
        
        with tqdm(total=file_size, unit='B', unit_scale=True, desc=filename, disable=True) as pbar:
            pbar.update(self.state[url]['downloaded'])
            with ThreadPoolExecutor(max_workers=self.num_connections) as executor:
                for i in range(self.num_connections):
                    start = i * segment_size
                    end = (i + 1) * segment_size - 1 if i < self.num_connections - 1 else file_size - 1
                    
                    # Logica di resume: se abbiamo già scaricato parti, qui andrebbe raffinata 
                    # con un check dei chunk mancanti. Per ora gestiamo il riavvio dei segmenti.
                    executor.submit(self._download_segment, url, start, end, filename, pbar)
            
            self._save_state()
            self.signals.finished.emit(url, filename)


    def download_torrent(self, magnet_or_file, dest_folder=None):
        if dest_folder is None:
            dest_folder = self.settings.get("dest_folder", os.path.join(os.path.expanduser("~"), "Downloads"))

        try:
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder, exist_ok=True)

            # Inizializza lo stato per la persistenza e la UI
            with self.lock:
                if magnet_or_file not in self.state:
                    self.state[magnet_or_file] = {
                        'downloaded': 0, 'total': 0, 'path': dest_folder, 'type': 'torrent'
                    }

            # Percorso di aria2c.exe (assumiamo sia nella stessa cartella dello script)
            aria_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aria2c.exe")
            if not os.path.exists(aria_path):
                self.signals.error.emit(magnet_or_file, "aria2c.exe non trovato nella cartella del programma.")
                return

            # Comando per aria2c: scarica torrent/magnet, aggiorna console ogni secondo
            cmd = [
                aria_path, 
                "--dir=" + dest_folder, 
                "--seed-time=0", # Chiudi dopo il download
                "--summary-interval=1",
                magnet_or_file
            ]

            # Feedback iniziale alla UI
            self.signals.progress.emit(magnet_or_file, 0, 100, 0.0)

            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8',
                errors='replace'
            )

            self.start_times[magnet_or_file] = time.time()
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if not line: continue

                if self.stop_event.is_set() or self.stop_events.get(magnet_or_file, threading.Event()).is_set():
                    process.terminate()
                    break
                
                # Parsing robusto con regex dell'output di aria2
                # Esempio: [#672f04 1.2MiB/5.0MiB(24%) CN:1 DL:120KiB]
                match = re.search(r'\((\d+)%\).*?DL:([0-9.]+)([a-zA-Z]*)', line)
                if match:
                    percent = int(match.group(1))
                    speed_num = float(match.group(2))
                    unit = match.group(3).lower()
                    
                    # Converti in byte/s
                    speed_val = speed_num
                    if "mib" in unit: speed_val *= 1024 * 1024
                    elif "kib" in unit: speed_val *= 1024
                    
                    self.signals.progress.emit(magnet_or_file, percent, 100, speed_val)
                    with self.lock:
                        self.state[magnet_or_file]['downloaded'] = percent
                        self.state[magnet_or_file]['total'] = 100

            process.wait()
            if process.returncode == 0:
                self.signals.finished.emit(magnet_or_file, dest_folder)
            elif not (self.stop_event.is_set() or self.stop_events.get(magnet_or_file, threading.Event()).is_set()):
                self.signals.error.emit(magnet_or_file, f"Aria2 errore (Codice: {process.returncode})")

            self._save_state()

        except Exception as e:
            self.signals.error.emit(magnet_or_file, f"Errore Torrent: {str(e)}")

    def pause(self, url=None):
        if url:
            with self.lock:
                if url in self.stop_events:
                    self.stop_events[url].set()
        else:
            self.stop_event.set()
            for event in self.stop_events.values():
                event.set()
        self._save_state()

    def _youtube_download(self, url, dest_folder, download_playlist=False):
        def progress_hook(d):
            if self.stop_event.is_set() or self.stop_events.get(url, threading.Event()).is_set():
                raise Exception("Download interrotto")
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                self.signals.progress.emit(url, downloaded, total or 0, speed or 0.0)

        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(dest_folder, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': not download_playlist,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                filesize = info.get('filesize') or info.get('filesize_approx', 0)
                
                with self.lock:
                    self.state[url] = {
                        'downloaded': filesize,
                        'total': filesize,
                        'path': filename,
                        'type': 'youtube'
                    }
                self._save_state()
                self.signals.finished.emit(url, filename)
        except Exception as e:
            if str(e) == "Download interrotto":
                return
            self.signals.error.emit(url, f"Errore YouTube: {str(e)}")

    def _simple_download(self, url, filename, total_size=None, initial_downloaded=0):
        current_pos = initial_downloaded
        max_retries = 5
        attempt = 0
        mode = "ab" if initial_downloaded > 0 else "wb"

        while (total_size is None or current_pos < total_size) and attempt < max_retries:
            if self.stop_event.is_set() or self.stop_events.get(url, threading.Event()).is_set(): break
            headers = {'Range': f'bytes={current_pos}-'} if current_pos > 0 else {}
            
            try:
                with self.session.get(url, headers=headers, stream=True, timeout=30) as response:
                    # Se abbiamo chiesto un range ma il server ignora e manda tutto (200 invece di 206)
                    if current_pos > 0 and response.status_code == 200:
                        current_pos = 0
                        mode = "wb"
                    
                    response.raise_for_status()
                    
                    # Recupero intelligente della dimensione totale
                    h = response.headers
                    cl = h.get('Content-Length', '0') # Default a '0' per evitare errori di int()
                    cr = h.get('Content-Range', '') # Default a ''
                    
                    new_total = None
                    current_total_in_state = self.state[url].get('total', 0)

                    if '/' in cr: # Esempio: bytes 0-0/4500000000
                        try:
                            total_part = cr.split('/')[-1].strip()
                            if total_part and total_part != '*':
                                new_total = int(total_part)
                        except: pass
                    
                    if not new_total and cl: # Se Content-Range non ha dato risultati, prova Content-Length
                        new_total = int(cl) + (current_pos if response.status_code == 206 else 0) # Se 206, CL è solo la parte rimanente

                    if new_total and new_total > current_total_in_state: # Aggiorna solo se il nuovo totale è maggiore
                        total_size = new_total
                        with self.lock:
                            self.state[url]['total'] = total_size
                    
                    with open(filename, mode) as f:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if self.stop_event.is_set() or self.stop_events.get(url, threading.Event()).is_set(): break
                            if chunk:
                                f.write(chunk)
                                current_pos += len(chunk)
                                with self.lock:
                                    self.state[url]['downloaded'] = current_pos
                                    elapsed = time.time() - self.start_times.get(url, time.time())
                                    speed = (current_pos - initial_downloaded) / elapsed if elapsed > 0 else 0
                                    self.signals.progress.emit(url, current_pos, total_size or 0, speed)
                break
            except Exception as e:
                attempt += 1
                mode = "ab" # Passa in modalità 'append' per i tentativi successivi
                time.sleep(attempt * 2)
                if attempt >= max_retries:
                    self.signals.error.emit(url, f"Errore persistente: {str(e)}")

class JDownloaderClone(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Daniele Barile Downloader")
        self.resize(800, 500)
        self.manager = DownloadManager()
        self.apply_modern_style()
        self.init_ui()
        self.load_saved_downloads()

        # Connetti segnali
        self.manager.signals.progress.connect(self.update_progress)
        self.manager.signals.finished.connect(self.on_finished)
        self.manager.signals.error.connect(self.on_error)

    def apply_modern_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
            }
            QWidget {
                font-family: "Segoe UI", "Roboto", sans-serif;
                font-size: 13px; color: white;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #dcdcdc;
                border-radius: 6px;
                background-color: #1e1e1e;
                color: white;
            }
            QLineEdit:focus {
                border: 2px solid #D4AF37;
            }
            QPushButton {
                background-color: #D4AF37;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                border: none;
            }
            QPushButton:hover {
                background-color: #B8961D;
            }
            QPushButton:pressed {
                background-color: #9A7D18;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #a0a0a0;
            }
            QTableWidget {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                gridline-color: transparent;
                selection-background-color: #D4AF37;
                selection-color: #333;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #D4AF37;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #dcdcdc;
                font-weight: bold;
            }
            QCheckBox {
                spacing: 8px;
            }
        """)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Top bar: URL input
        top_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Incolla qui l'URL (HTTP o Magnet)...")
        self.folder_btn = QPushButton("📁")
        self.folder_btn.setFixedWidth(50)
        self.folder_btn.clicked.connect(self.select_folder)
        self.torrent_btn = QPushButton("📂 Torrent")
        self.torrent_btn.clicked.connect(self.open_torrent_file)
        self.playlist_cb = QCheckBox("Youtube play list")
        self.playlist_cb.setToolTip("Se attivo, scarica l'intera playlist/mix di YouTube")
        self.remove_btn = QPushButton("Rimuovi Selezionato")
        self.remove_btn.clicked.connect(self.remove_selected_download)
        self.remove_btn.setEnabled(False) # Disabilitato finché non c'è una selezione
        self.add_btn = QPushButton("Aggiungi Download")
        self.add_btn.clicked.connect(self.start_new_download)
        top_layout.addWidget(self.url_input)
        top_layout.addWidget(self.folder_btn)
        top_layout.addWidget(self.torrent_btn)
        top_layout.addWidget(self.playlist_cb)
        top_layout.addWidget(self.add_btn)
        layout.addLayout(top_layout)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setShowGrid(False)
        self.table.setHorizontalHeaderLabels(["File / URL", "Velocità", "MB Scaricati", "Stato"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows) # Seleziona intere righe
        self.table.itemSelectionChanged.connect(self.toggle_remove_button)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)
        layout.addWidget(self.remove_btn) # Aggiungi il pulsante Rimuovi sotto la tabella

        # Footer Brand
        self.footer_label = QLabel("Powered by Daniele Barile")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: #d4af37; font-family: 'Helvetica'; font-size: 18px; font-weight: bold; margin-top: 2px; margin-bottom: 2px;")
        layout.addWidget(self.footer_label)
        
        self.dest_folder = self.manager.settings.get("dest_folder")

    def load_saved_downloads(self):
        """Carica i download salvati nel file JSON all'interno della tabella GUI all'avvio."""
        for url, data in self.manager.state.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            url_item = QTableWidgetItem(url)
            url_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, url_item)
            
            total = data.get('total', 0)
            downloaded = data.get('downloaded', 0)
            
            speed_item = QTableWidgetItem("0 B/s")
            speed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, speed_item)
            
            mb_item = QTableWidgetItem(f"{downloaded/(1024*1024):.1f} MB")
            mb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, mb_item)

            status = "Completato" if (downloaded >= total and total > 0) else "In sospeso"
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status == "Completato":
                status_item.setBackground(Qt.GlobalColor.green)
            self.table.setItem(row, 3, status_item)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella di download", self.dest_folder)
        if folder:
            self.dest_folder = folder
            self.manager.settings["dest_folder"] = folder
            self.manager._save_state()

    def show_context_menu(self, pos):
        """Mostra il menu contestuale al click destro sulla tabella."""
        item = self.table.itemAt(pos)
        if item:
            if not item.isSelected():
                self.table.clearSelection()
                self.table.selectRow(item.row())
            menu = QMenu(self)
            resume_action = menu.addAction("Avvia/Riprendi")
            resume_action.triggered.connect(self.resume_selected_download)
            pause_action = menu.addAction("Pausa")
            pause_action.triggered.connect(self.pause_selected_download)
            remove_action = menu.addAction("Rimuovi")
            remove_action.triggered.connect(self.remove_selected_download)
            menu.exec(self.table.viewport().mapToGlobal(pos))

    def resume_selected_download(self):
        """Riprende il download per le righe selezionate nella tabella."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        for row in selected_rows:
            url = self.table.item(row, 0).text()
            status_item = QTableWidgetItem("In coda...")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, status_item)
            # Avvia il download in un thread separato
            download_playlist = self.playlist_cb.isChecked()
            threading.Thread(target=self.manager.download, args=(url, self.dest_folder, download_playlist), daemon=True).start()

    def pause_selected_download(self):
        """Mette in pausa i download selezionati."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        for row in selected_rows:
            url = self.table.item(row, 0).text()
            self.manager.pause(url)
            status_item = QTableWidgetItem("In Pausa")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, status_item)

    def toggle_remove_button(self):
        """Abilita/Disabilita il pulsante Rimuovi in base alla selezione della tabella."""
        self.remove_btn.setEnabled(len(self.table.selectedItems()) > 0)

    def remove_selected_download(self):
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())), reverse=True)
        if not selected_rows:
            return

        for row in selected_rows:
            url_item = self.table.item(row, 0)
            if not url_item: continue
            url = url_item.text()

            # Chiedi all'utente se vuole eliminare anche il file fisico
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Rimuovi Download")
            msg_box.setText(f"Vuoi eliminare il download per '{url}'?")
            msg_box.setInformativeText("Vuoi anche eliminare il file scaricato dal disco?")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            ret = msg_box.exec()

            if ret == QMessageBox.StandardButton.Cancel:
                continue # Annulla l'operazione per questa riga e le successive

            if url in self.manager.state:
                file_path = self.manager.state[url]['path']
                del self.manager.state[url]
                self.manager._save_state()
                if ret == QMessageBox.StandardButton.Yes and os.path.exists(file_path):
                    os.remove(file_path)
                    QMessageBox.information(self, "File Eliminato", f"Il file '{os.path.basename(file_path)}' è stato eliminato.")
            
            self.table.removeRow(row)

    def open_torrent_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleziona file Torrent", "", "File Torrent (*.torrent);;Tutti i file (*)")
        if file_path:
            self._initiate_download(file_path)

    def start_new_download(self):
        url = self.url_input.text().strip()
        if url:
            self.url_input.clear()
            self._initiate_download(url)

    def _initiate_download(self, source):
        row = self.table.rowCount()
        self.table.insertRow(row)
        url_item = QTableWidgetItem(source)
        url_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, url_item)
        
        speed_item = QTableWidgetItem("0 B/s")
        speed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 1, speed_item)
        
        mb_item = QTableWidgetItem("0.0 MB")
        mb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, mb_item)
        
        status_item = QTableWidgetItem("Avvio...")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 3, status_item)
        
        def run_with_error_handling():
            try:
                download_playlist = self.playlist_cb.isChecked()
                self.manager.download(source, self.dest_folder, download_playlist)
            except Exception as e:
                self.on_error(source, str(e))

        threading.Thread(target=run_with_error_handling, daemon=True).start()

    def update_progress(self, url, downloaded, total, speed):
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).text() == url:
                
                # Formattazione velocità
                if speed > 1024 * 1024:
                    speed_str = f"{speed / (1024*1024):.2f} MB/s"
                elif speed > 1024:
                    speed_str = f"{speed / 1024:.2f} KB/s"
                else:
                    speed_str = f"{speed:.0f} B/s"
                
                speed_item = QTableWidgetItem(speed_str)
                speed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 1, speed_item)

                mb_item = QTableWidgetItem(f"{downloaded/(1024*1024):.1f} MB")
                mb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 2, mb_item)
                
                status_item = QTableWidgetItem("Scaricamento...")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 3, status_item)

    def on_finished(self, url, path):
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).text() == url:
                speed_item = QTableWidgetItem("0 KB/s")
                speed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 1, speed_item)
                
                status_item = QTableWidgetItem("Completato!")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setBackground(Qt.GlobalColor.green)
                self.table.setItem(i, 3, status_item)

    def on_error(self, url, message):
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).text() == url:
                status_item = QTableWidgetItem(f"Errore: {message[:20]}...")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setBackground(Qt.GlobalColor.red)
                self.table.setItem(i, 3, status_item)
        QMessageBox.critical(self, "Errore Download", f"Fallito per {url}\n\n{message}")

    def closeEvent(self, event):
        """Assicura che lo stato venga salvato e i thread interrotti alla chiusura."""
        self.manager.stop_event.set()
        self.manager._save_state()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JDownloaderClone()
    window.show()
    sys.exit(app.exec())
