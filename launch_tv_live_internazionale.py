import os
import sys
import re
import json
import subprocess
import webbrowser
import requests
import locale
import xml.etree.ElementTree as ET
import datetime

os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

# --- LOGICA MPV ---
# Assicurati di avere mpv-1.dll nella cartella dello script
# E installa la libreria con: pip install python-mpv
if sys.platform == "win32":
    try:
        # MPV richiede il locale numerico 'C' per evitare crash con le virgole decimali
        locale.setlocale(locale.LC_NUMERIC, 'C')
        # Aggiunge la cartella dello script al percorso di ricerca delle DLL
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.environ['PATH'] = script_dir + os.pathsep + os.environ['PATH']
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(script_dir)
    except:
        pass

try:
    import mpv
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QPushButton, QLineEdit, QLabel, QStyle, 
                                 QMessageBox, QSlider, QListWidget, QListWidgetItem, 
                                 QSplitter, QSizePolicy, QFileDialog, QGridLayout, QStackedWidget, QToolButton, QTextEdit, QDialog, QTextBrowser)
    from PyQt6.QtCore import QUrl, Qt, QTimer, QEvent, QSize, QTime, QVariantAnimation
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QShortcut, QKeySequence
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
    except:
        QWebEngineView = None
except ImportError as e:
    print(f"Errore libreria: {e}. Esegui: pip install PyQt6 python-mpv")
    sys.exit(1)

TV_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_settings.json")

class AnimatedAppButton(QToolButton):
    def __init__(self, icon, base_size, text="", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setIcon(icon)
        if text:
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        else:
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.base_size = base_size
        self.setIconSize(base_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QToolButton { background: transparent; border: none; color: white; padding: 0px; text-align: center; font-weight: bold; } QToolButton:hover { background: rgba(212, 175, 55, 40); border-radius: 12px; }")
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(180)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(1.18) # Zoom del 18%
        self.anim.valueChanged.connect(self._update_icon_size)

    def _update_icon_size(self, scale):
        self.setIconSize(self.base_size * scale)

    def enterEvent(self, event):
        self.anim.setDirection(QVariantAnimation.Direction.Forward)
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.setDirection(QVariantAnimation.Direction.Backward)
        self.anim.start()
        super().leaveEvent(event)

class TVLiveInternazionale(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TV Live Internazionale - Suite Multimediale Pro")
        self.setMinimumSize(1100, 750)
        
        self.settings = self.load_settings()
        
        self.channels = []
        self.info_timer = QTimer(self)
        self.info_timer.setSingleShot(True)
        self.info_timer.timeout.connect(self.hide_info_overlay)
        
        self.mpv_player = None
        self.multi_players = []
        
        self.multi_frames = []
        self.current_multi_index = 0
        self.is_multiview = False
        self._autoplay_started = False
        
        self.is_recording = False
        self.record_path = None
        self.pip_window = None

        self.setup_ui()
        self.load_icons()    # Inizializza icons_cache prima di caricare i canali
        self.load_channels() # Ora può accedere a icons_cache senza errori
        self.fetch_missing_icons()
        self.populate_app_bar()
        self.populate_suite_app_bar()
        
        self.init_mpv()      # Inizializza MPV sui widget creati
        self.apply_theme()

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_ui_status)

        default_url = self.settings.get("last_url", "")
        self.url_input.setText(default_url)
        
        self.timer.start()

        # Timer centralizzato per lo zapping: evita crash su pressioni multiple di Invio/OK
        self.zap_timer = QTimer(self)
        self.zap_timer.setSingleShot(True)
        self.zap_timer.timeout.connect(self.play_stream)

        # Imposta il focus sulla lista per il telecomando
        self.channel_list.setFocus()

        # Gestione selezione: itemClicked per mouse, Enter gestito manualmente in keyPressEvent
        # rimosso itemActivated per prevenire il crash critico su pressione di Enter
        self.channel_list.itemDoubleClicked.connect(self.on_channel_clicked)

        # Scorciatoia ESC globale (garantisce il funzionamento anche con focus su Browser o Video)
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.activated.connect(self.on_esc_pressed)

    def load_settings(self):
        if os.path.exists(TV_SETTINGS_FILE):
            try:
                with open(TV_SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except: pass
        return {"volume": 70, "last_url": "", "history": []}

    def save_settings(self):
        self.settings["volume"] = self.volume_slider.value()
        self.settings["last_url"] = self.url_input.text()
        try:
            with open(TV_SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=4)
            if hasattr(self, 'status_label'):
                self.status_label.setText("Impostazioni salvate.")
        except: pass

    def init_mpv(self):
        """Inizializza MPV collegandolo al widget video della Suite."""
        try:
            common_args = {
                'ytdl': False,                    # Gli stream IPTV sono gia' URL diretti
                'cache': 'yes',
                'demuxer_max_bytes': '15M',       # Ridotto drasticamente per avvio istantaneo
                'demuxer_readahead_secs': 1,      # Solo 1 secondo di pre-caricamento per flussi live
                'network_timeout': 10,            # Non bloccare la UI se il link è offline
                'stream_buffer_size': '512k',     # Buffer di rete piccolo per play immediato
                'cache_pause': 'no',              # Non mettere in pausa se la cache si svuota (evita stuttering infinito)
                'hr_seek': 'no',                  # Seeking veloce
                'profile': 'low-latency'          # Profilo ottimizzato per IPTV
            }
            self._mpv_common_args = common_args
            # Collega MPV al widget tramite l'ID finestra (winId)
            self.mpv_player = mpv.MPV(wid=str(int(self.video_output.winId())), **common_args)
            self.mpv_player.volume = self.settings.get("volume", 70)

        except Exception as e:
            QMessageBox.critical(self, "Errore MPV", f"Impossibile avviare MPV. Assicurati che mpv-1.dll sia nella cartella.\n\n{e}")

    def init_multiview_players(self):
        """Crea i player secondari solo quando il multiview viene usato."""
        if self.multi_players:
            return
        try:
            for i in range(4):
                player = mpv.MPV(
                    wid=str(int(self.multi_frames[i].winId())),
                    **self._mpv_common_args
                )
                player.volume = self.settings.get("volume", 70)
                self.multi_players.append(player)
        except Exception as e:
            for player in self.multi_players:
                player.terminate()
            self.multi_players.clear()
            QMessageBox.critical(self, "Errore MPV", f"Impossibile avviare il multiview.\n\n{e}")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._autoplay_started:
            self._autoplay_started = True
            QTimer.singleShot(250, self.autoplay_rai1)

    def parse_m3u(self, file_path):
        """Parser M3U robusto riga per riga."""
        chans = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    current_chan = {}
                    for line in f:
                        line = line.strip()
                        if line.startswith("#EXTINF:"):
                            # Estrazione nome
                            name_match = re.search(r',([^,]*)$', line)
                            current_chan["name"] = name_match.group(1).strip() if name_match else "Senza nome"
                            # Estrazione logo
                            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                            current_chan["logo"] = logo_match.group(1) if logo_match else None
                            # Estrazione ID per EPG
                            id_match = re.search(r'tvg-id="([^"]*)"', line)
                            current_chan["tvg-id"] = id_match.group(1) if id_match else None
                        elif line.startswith("http"):
                            current_chan["url"] = line
                            current_chan["type"] = "live"
                            chans.append(current_chan)
                            current_chan = {}
            except Exception as e: print(f"Errore parsing M3U: {e}")
        return chans

    def load_channels_from_m3u(self, load_file=True):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        m3u_path1 = self.settings.get("playlist_path", os.path.join(script_dir, "tv.m3u"))
        m3u_path2 = os.path.join(script_dir, "iptvita.v03-2024.m3u")
        
        channels = []
        if load_file:
            # Carica prima playlist (quella predefinita o da impostazioni)
            ch1 = self.parse_m3u(m3u_path1)
            channels.extend(ch1)
            if ch1: print(f"DEBUG: Caricati {len(ch1)} canali da {m3u_path1}")
            
            # Carica seconda playlist aggiuntiva (iptvita.v03-2024.m3u)
            ch2 = self.parse_m3u(m3u_path2)
            channels.extend(ch2)
            if ch2: print(f"DEBUG: Caricati {len(ch2)} canali da {m3u_path2}")

        # App Smart TV (sempre presenti come browser tabs)
        smart_apps = [
            {"name": "🌐 YouTube", "url": "https://www.youtube.com", "type": "smarttv"},
            {"name": "🌐 Netflix", "url": "https://www.netflix.com", "type": "smarttv"},
            {"name": "🌐 Disney+", "url": "https://www.disneyplus.com", "type": "smarttv"},
            {"name": "🌐 Prime Video", "url": "https://www.primevideo.com", "type": "smarttv"},
            {"name": "🌐 National Geographic", "url": "https://www.nationalgeographic.it", "type": "smarttv"},
            {"name": "🌐 DAZN", "url": "https://www.dazn.com", "type": "smarttv"},
            {"name": "🌐 RaiPlay", "url": "https://www.raiplay.it", "type": "smarttv"},
            {"name": "🌐 Mediaset Infinity", "url": "https://www.mediasetinfinity.it", "type": "smarttv"},
            {"name": "🌐 Paramount+", "url": "https://www.paramountplus.com", "type": "smarttv"},
            {"name": "🌐 Rakuten TV", "url": "https://www.rakuten.tv", "type": "smarttv"}
        ]
        
        return channels + smart_apps

    def fetch_missing_icons(self):
        """Scarica le icone dai link 'tvg-logo' se non presenti localmente."""
        import threading
        # Usa un percorso relativo per la cartella delle icone
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_path = os.path.join(script_dir, "image canali")
        if not os.path.exists(icons_path): return

        def worker():
            changed = False
            for chan in self.channels:
                if chan.get("logo") and chan["name"] not in self.icons_cache:
                    # Nome file sicuro per Windows
                    safe_name = "".join([c for c in chan["name"] if c.isalnum() or c in (' ', '.', '_')]).strip()
                    save_path = os.path.join(icons_path, f"{safe_name}.png")
                    
                    if not os.path.exists(save_path):
                        try:
                            r = requests.get(chan["logo"], timeout=5)
                            if r.status_code == 200:
                                with open(save_path, 'wb') as f:
                                    f.write(r.content)
                                changed = True
                        except: continue
            if changed:
                QTimer.singleShot(0, lambda: [self.load_icons(), self.load_channels(), self.populate_app_bar()])

        threading.Thread(target=worker, daemon=True).start()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        # Barra di controllo superiore
        self.top_control_bar = QWidget()
        top_bar = QHBoxLayout(self.top_control_bar)
        self.url_input = QLineEdit()
        self.url_input.returnPressed.connect(self.handle_enter_key_action)
        self.url_input.setPlaceholderText("Incolla qui l'URL del flusso TV (m3u8, mp4, etc.)...")

        self.btn_play = QPushButton("RIPRODUCI ORA")
        self.btn_play.clicked.connect(self.play_stream)
        self.btn_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.btn_load_playlist = QPushButton("CARICA")
        self.btn_load_playlist.setFixedWidth(80)
        self.btn_load_playlist.setToolTip("Carica una nuova playlist M3U")
        self.btn_load_playlist.setStyleSheet("""
            QPushButton { background-color: #1e1e1e; color: #D4AF37; border: 1px solid #D4AF37; padding: 5px; }
            QPushButton:hover { background-color: #333; }
        """)
        self.btn_load_playlist.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_load_playlist.clicked.connect(self.import_playlist)

        self.btn_save_playlist = QPushButton("SALVA")
        self.btn_save_playlist.setFixedWidth(80)
        self.btn_save_playlist.setToolTip("Salva il percorso della playlist attuale")
        self.btn_save_playlist.setStyleSheet("""
            QPushButton { background-color: #1e1e1e; color: #D4AF37; border: 1px solid #D4AF37; padding: 5px; }
            QPushButton:hover { background-color: #333; }
        """)
        self.btn_save_playlist.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_save_playlist.clicked.connect(self.save_settings)

        self.btn_file = QPushButton("APRI FILE")
        self.btn_file.clicked.connect(self.open_local_file)
        self.btn_file.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        top_bar.addWidget(self.btn_file)
        top_bar.addWidget(self.url_input)
        top_bar.addWidget(self.btn_load_playlist)
        top_bar.addWidget(self.btn_save_playlist)
        top_bar.addWidget(self.btn_play)
        layout.addWidget(self.top_control_bar)

        # Status Label
        self.status_label = QLabel("Pronto.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMaximumHeight(18)
        layout.addWidget(self.status_label)
        
        # Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, 1) # Assegna tutto lo spazio verticale disponibile allo splitter

        # --- SIDEBAR CANALI ---
        left_panel_layout = QVBoxLayout()
        left_panel_layout.setSpacing(5)
        
        # Campo di ricerca per filtrare velocemente i canali
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔎 Cerca canale...")
        self.search_bar.textChanged.connect(self.filter_channels)
        self.search_bar.setStyleSheet("background-color: #1e1e1e; border: 1px solid #D4AF37; color: white; padding: 8px; font-size: 13px; border-radius: 4px;")
        left_panel_layout.addWidget(self.search_bar)
        
        self.channel_list = QListWidget()
        self.channel_list.setMinimumWidth(280)
        self.channel_list.setIconSize(QSize(75, 75))
        self.channel_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.channel_list.itemClicked.connect(self.on_channel_clicked)
        left_panel_layout.addWidget(self.channel_list, 3) # La lista occupa più spazio

        left_panel_widget = QWidget()
        left_panel_widget.setLayout(left_panel_layout)
        self.splitter.addWidget(left_panel_widget)

        # --- AREA VIDEO ---
        self.view_stack = QStackedWidget()
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.suite_app_container = QWidget()
        self.suite_app_bar_layout = QHBoxLayout(self.suite_app_container)
        self.suite_app_bar_layout.setContentsMargins(5, 5, 5, 2)
        self.suite_app_bar_layout.setSpacing(5)
        right_layout.addWidget(self.suite_app_container)
        
        self.smart_app_container = QWidget()
        self.app_bar_layout = QHBoxLayout(self.smart_app_container)
        self.app_bar_layout.setContentsMargins(5, 5, 5, 2)
        self.app_bar_layout.setSpacing(5)
        right_layout.addWidget(self.smart_app_container)

        # 1. Single View (Dummy)
        self.video_frame = QWidget()
        self.video_frame.setStyleSheet("background-color: black;")
        self.view_stack.addWidget(self.video_frame)

        # 2. Browser integrato per Smart TV
        self.web_view = QWebEngineView() if QWebEngineView else QLabel("Modulo Mancante")
        if QWebEngineView:
            # Maschera il browser come Chrome
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            self.web_view.page().profile().setHttpUserAgent(ua)
            self.view_stack.addWidget(self.web_view)
        else:
            self.web_view = QLabel("Errore: PyQt6-WebEngine non installato.\nEsegui: pip install PyQt6-WebEngine")
            self.view_stack.addWidget(self.web_view)

        # 3. Multi View
        self.multi_view_widget = QWidget()
        self.multi_view_widget.setStyleSheet("background-color: #121212;")
        self.multi_grid_layout = QGridLayout(self.multi_view_widget)
        self.multi_grid_layout.setSpacing(2)
        self.multi_grid_layout.setContentsMargins(0, 0, 0, 0)
        
        for i in range(4):
            frame = QWidget()
            frame.setStyleSheet("background-color: black; border: 1px solid #333;")
            frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
            self.multi_grid_layout.addWidget(frame, i//2, i%2)
            self.multi_frames.append(frame)
        
        self.view_stack.addWidget(self.multi_view_widget)
        right_layout.addWidget(self.view_stack, 1)
        self.splitter.addWidget(right_panel)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        
        # Contenitore per Video + Overlay (risolve problemi di z-order con MPV)
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: black; border: none;")
        video_container_layout = QVBoxLayout(self.video_container)
        video_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_output = QWidget(self.video_container)
        self.video_output.setStyleSheet("background-color: black; border: none;")
        self.video_output.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        video_container_layout.addWidget(self.video_output)

        # Info Overlay (Current Program)
        self.info_overlay = QWidget(self.video_container)
        self.info_overlay.setStyleSheet("background-color: rgba(26, 26, 26, 220); border: 2px solid #D4AF37; border-radius: 12px; color: white;")
        self.info_overlay.setFixedSize(450, 110)
        self.info_overlay.hide()
        overlay_layout = QVBoxLayout(self.info_overlay)
        self.info_chan_name = QLabel("Canale")
        self.info_chan_name.setStyleSheet("color: #D4AF37; font-weight: bold; font-size: 14px; border: none;")
        self.info_prog_title = QLabel("Caricamento programma...")
        self.info_prog_title.setStyleSheet("font-size: 18px; font-weight: bold; border: none;")
        self.info_prog_time = QLabel("00:00 - 00:00")
        self.info_prog_time.setStyleSheet("color: #aaa; font-size: 12px; border: none;")
        overlay_layout.addWidget(self.info_chan_name)
        overlay_layout.addWidget(self.info_prog_title)
        overlay_layout.addWidget(self.info_prog_time)
        
        self.view_stack.insertWidget(0, self.video_container)
        self.video_container.installEventFilter(self)

        # --- BARRA CONTROLLO INFERIORE ---
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000) # 0-1000 for percentage
        self.position_slider.sliderMoved.connect(self.set_position)
        layout.addWidget(self.position_slider)

        self.bottom_control_bar = QWidget()
        bottom_bar = QHBoxLayout(self.bottom_control_bar)
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.clicked.connect(self.stop_stream)
        self.btn_stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_pause = QPushButton("PAUSA/PLAY")
        self.btn_pause.clicked.connect(self.pause_stream)
        self.btn_pause.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.btn_record = QPushButton("REGISTRA")
        self.btn_record.clicked.connect(self.toggle_recording)
        self.btn_record.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_multiview = QPushButton("MULTIVIEW: OFF")
        self.btn_multiview.clicked.connect(self.toggle_multiview)
        self.btn_multiview.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_pip = QPushButton("PiP")
        self.btn_pip.clicked.connect(self.toggle_pip_mode)
        self.btn_pip.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_guide = QPushButton("INFO / GUIDA TV")
        self.btn_guide.setStyleSheet("background-color: #1e1e1e; color: #D4AF37; border: 1px solid #D4AF37;")
        self.btn_guide.clicked.connect(self.handle_guide_click)
        self.btn_guide.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_fullscreen = QPushButton("SCHERMO INTERO")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self.btn_fullscreen.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.volume_label = QLabel("Volume:")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.settings.get("volume", 70))
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        bottom_bar.addWidget(self.btn_stop)
        bottom_bar.addWidget(self.btn_pause)
        bottom_bar.addWidget(self.btn_record)
        bottom_bar.addWidget(self.btn_pip) # Add PiP button
        bottom_bar.addWidget(self.btn_guide)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.volume_label)
        bottom_bar.addWidget(self.volume_slider)
        bottom_bar.addWidget(self.btn_fullscreen)
        layout.addWidget(self.bottom_control_bar)

        # Footer Brand
        self.footer_label = QLabel("Powered by Daniele Barile")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: #d4af37; font-family: 'Helvetica'; font-size: 18px; font-weight: bold; margin-top: 2px; margin-bottom: 2px;")
        layout.addWidget(self.footer_label)

    def eventFilter(self, source, event):
        if source == self.video_container and event.type() == QEvent.Type.Resize:
            if self.info_overlay.isVisible():
                # Centra o posiziona correttamente l'overlay al resize
                y_pos = self.video_container.height() - self.info_overlay.height() - 40
                self.info_overlay.move(30, max(20, y_pos))
        return super().eventFilter(source, event)

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #121212; color: #ffffff; font-family: 'Segoe UI'; }
            QLineEdit { background-color: #1e1e1e; border: 1px solid #D4AF37; color: white; padding: 5px; border-radius: 4px; font-size: 13px; }
            QPushButton { background-color: #D4AF37; color: black; border-radius: 6px; padding: 12px 20px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #f1c40f; }
            QLabel { color: #D4AF37; font-weight: bold; }
            QListWidget { background-color: #800020; border: 1px solid #333333; color: white; outline: none; font-size: 12px; }
            QListWidget::item { padding: 15px; border-bottom: 1px solid #333333; }
            QListWidget::item:selected { background-color: #D4AF37; }
            QSlider::groove:horizontal { border: 1px solid #D4AF37; height: 4px; background: #1e1e1e; margin: 2px 0; border-radius: 2px; }
            QSlider::handle:horizontal { background: #D4AF37; border: 1px solid #D4AF37; width: 18px; margin: -7px 0; border-radius: 9px; }
        """)
        self.status_label.setObjectName("status_label")

    def load_icons(self):
        """Inizializza la cache e indicizza i file delle icone (Lazy Loading)."""
        self.icons_cache = {} 
        self.icons_paths = {} 
        # Usa un percorso relativo per la cartella delle icone
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_path = os.path.join(script_dir, "image canali")
        if not os.path.exists(icons_path):
            return

        # Scansiona tutti i file nella cartella loghi
        # Scansiona velocemente solo i nomi dei file senza caricarli
        for filename in os.listdir(icons_path):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                # Nome file senza estensione e in minuscolo per il matching
                name_key = os.path.splitext(filename)[0].lower().strip()
                file_path = os.path.join(icons_path, filename)
                self.icons_paths[name_key] = file_path
                self.icons_paths[re.sub(r'[^a-z0-9]', '', name_key)] = file_path

    def get_cached_icon(self, name, use_fallback=True):
        """Carica l'icona dal disco solo alla prima richiesta per risparmiare RAM e tempo."""
        if not name:
            return self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon) if use_fallback else None
            
        name_lower = name.lower().strip()
        clean_name = re.sub(r'[^a-z0-9]', '', name_lower)
        
        # 1. Controlla in cache
        if clean_name in self.icons_cache: return self.icons_cache[clean_name]
        if name_lower in self.icons_cache: return self.icons_cache[name_lower]
            
        # 2. Se non in cache, cerca il percorso
        path = self.icons_paths.get(clean_name) or self.icons_paths.get(name_lower)
        
        if path:
            try:
                pix = QPixmap(path).scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if not pix.isNull():
                    icon = QIcon(pix)
                    self.icons_cache[clean_name] = icon
                    return icon
            except: pass
        return self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon) if use_fallback else None

    def load_channels(self):
        self.channels = self.load_channels_from_m3u()
        self.channel_list.clear()
        live_channels = [c for c in self.channels if c["type"] == "live"]
        self._add_to_list(live_channels)

    def populate_app_bar(self):
        while self.app_bar_layout.count():
            item = self.app_bar_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        smart_apps = [c for c in self.channels if c["type"] == "smarttv"]
        self.app_bar_layout.addStretch()
        for app in smart_apps:
            icon = self.get_cached_icon(app["name"])
            btn = AnimatedAppButton(icon, QSize(250, 140), "")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda checked, a=app: self.switch_to_smart_app(a))
            self.app_bar_layout.addWidget(btn)
        self.app_bar_layout.addStretch()

    def _add_to_list(self, chan_list):
        for chan in chan_list:
            raw_name = chan["name"]
            # Pulisce il nome per il match: "[1] Rai 1" -> "rai 1"
            clean_name = re.sub(r'^\[\d+\]\s*', '', raw_name).lower().strip()
            found_icon = self.get_cached_icon(clean_name)
            item = QListWidgetItem(raw_name)
            item.setIcon(found_icon)
            item.setData(Qt.ItemDataRole.UserRole, chan)
            item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.channel_list.addItem(item)

    def populate_suite_app_bar(self):
        suite_apps = [
            {"name": "Media Player", "script": "mediaplayer.py", "icon": QStyle.StandardPixmap.SP_MediaPlay},
            {"name": "Video Editor", "script": "editor.py", "icon": QStyle.StandardPixmap.SP_FileDialogDetailedView},
            {"name": "Video Converter", "script": "converter.py", "icon": QStyle.StandardPixmap.SP_FileDialogToParent},
            {"name": "Screen Recorder", "script": "recorder.py", "icon": QStyle.StandardPixmap.SP_DialogNoButton},
            {"name": "VM Manager", "script": "virtualizzatore.py", "icon": QStyle.StandardPixmap.SP_DriveDVDIcon},
            {"name": "File Downloader", "script": "downloader.py", "icon": QStyle.StandardPixmap.SP_ArrowDown},
            {"name": "Universal Emulator", "script": "UniversalEmulatorbyDB.py", "icon": QStyle.StandardPixmap.SP_DesktopIcon},
            {"name": "Web Browser", "script": "browser.py", "icon": QStyle.StandardPixmap.SP_BrowserReload},
        ]
        
        self.suite_app_bar_layout.addStretch()
        recolor_targets = ["Media Player", "Video Converter", "File Downloader"]
        bordeaux_color = QColor("#800020")

        for app in suite_apps:
            # Cerca logo personalizzato tramite il sistema di lazy loading senza fallback immediato
            icon = self.get_cached_icon(app["name"], use_fallback=False)
            # Se get_cached_icon ha restituito l'icona di default, proviamo a colorarla
            if not icon:
                icon = self.style().standardIcon(app["icon"])
                if app["name"] in recolor_targets:
                    # Applica ricolorazione solo alle icone di sistema
                    pixmap = icon.pixmap(QSize(160, 160))
                    painter = QPainter(pixmap)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), bordeaux_color)
                    painter.end()
                    icon = QIcon(pixmap)
                
            btn = AnimatedAppButton(icon, QSize(160, 160), app["name"])
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFont(QFont("Segoe UI Variable Text", 11, QFont.Weight.Bold))
            btn.clicked.connect(lambda checked, s=app["script"]: self.launch_suite_app(s))
            self.suite_app_bar_layout.addWidget(btn)
        self.suite_app_bar_layout.addStretch()

    def autoplay_rai1(self):
        """Cerca Rai 1 nella lista canali e avvia la riproduzione all'avvio."""
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            # Cerca il canale che contiene "rai 1" nel nome
            if "rai 1" in item.text().lower():
                self.channel_list.setCurrentItem(item)
                self.on_channel_clicked(item)
                break

    def filter_channels(self, text):
        """Filtra la lista dei canali in base al testo di ricerca."""
        self.channel_list.clear()
        search_text = text.lower()
        # Filtra solo i canali di tipo 'live' dalle playlist per mantenere pulita la sidebar
        filtered = [c for c in self.channels if c["type"] == "live" and search_text in c["name"].lower()]
        self._add_to_list(filtered)

    def filter_by_type(self, ctype):
        """Filtra la lista per tipo (es. smarttv o live)."""
        self.channel_list.clear()
        if not hasattr(self, '_filtered_smart') or not self._filtered_smart:
            filtered = [c for c in self.channels if c["type"] == ctype]
            self._add_to_list(filtered)
            self._filtered_smart = True
            self.btn_smart_tv.setText("MOSTRA TUTTI")
        else:
            self._add_to_list(self.channels)
            self._filtered_smart = False
            self.btn_smart_tv.setText("SMART TV / APPS")

    def on_channel_clicked(self, item):
        """Gestisce la selezione di un canale o servizio dalla scaletta."""
        if not item: return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or "url" not in data: return
        url = data["url"]
        self.url_input.setText(url)
        
        if data.get("type") == "smarttv":
            self.switch_to_smart_app(data)
        else:
            self.view_stack.setCurrentIndex(0)
            # Avviamo il caricamento tramite il timer centralizzato per gestire lo zapping in sicurezza
            self.zap_timer.start(150)

    def handle_enter_key_action(self):
        """
        Gestisce l'azione da eseguire quando si preme Invio (o OK) sulla barra degli indirizzi.
        Se un canale è selezionato, lo riproduce. Altrimenti, riproduce l'URL nella barra.
        """
        current_item = self.channel_list.currentItem()
        if current_item:
            self.on_channel_clicked(current_item)
        else:
            QTimer.singleShot(50, self.play_stream)
            self.zap_timer.start(250)

    def fetch_real_epg(self, channel_name):
        """Simula il recupero di una vera guida programmi aggiornata."""
        now = datetime.datetime.now()
        n = channel_name.lower()
        guide = [
            {"time": (now - datetime.timedelta(minutes=30)).strftime("%H:%M"), "title": "Programma Precedente"},
            {"time": now.strftime("%H:%M"), "title": "In Onda Adesso"},
            {"time": (now + datetime.timedelta(hours=1)).strftime("%H:%M"), "title": "Prossimo Programma"},
            {"time": (now + datetime.timedelta(hours=2)).strftime("%H:%M"), "title": "Film in Serata"},
            {"time": (now + datetime.timedelta(hours=4)).strftime("%H:%M"), "title": "Notiziario Notturno"}
        ]
        if "rai 1" in n: guide[1]["title"] = "TG1 Edizione Pomeridiana"
        elif "rai 2" in n: guide[1]["title"] = "I Fatti Vostri"
        elif "rai 3" in n: guide[1]["title"] = "Geo & Geo"
        elif "canale 5" in n: guide[1]["title"] = "Pomeriggio Cinque"
        elif "italia 1" in n: guide[1]["title"] = "I Simpson"
        elif "rete 4" in n: guide[1]["title"] = "Lo Sportello di Forum"
        elif "la7" in n: guide[1]["title"] = "Tagadà"
        return guide

    def show_info_overlay(self, chan_data):
        """Mostra l'overlay con le info del programma corrente per 30 secondi."""
        guide = self.fetch_real_epg(chan_data["name"])
        current = guide[1]
        next_p = guide[2]
        self.info_chan_name.setText(chan_data["name"].upper())
        self.info_prog_title.setText(current["title"])
        self.info_prog_time.setText(f"{current['time']} - segue: {next_p['title']} ({next_p['time']})")
        
        # Forza il calcolo della posizione basato sull'altezza attuale del contenitore
        self.info_overlay.adjustSize()
        v_height = self.video_container.height() if self.video_container.height() > 100 else 500
        y_pos = v_height - self.info_overlay.height() - 40
        self.info_overlay.move(30, max(20, y_pos))
        
        self.info_overlay.show()
        self.info_overlay.raise_()
        self.info_timer.start(30000)

    def hide_info_overlay(self):
        self.info_overlay.hide()

    def handle_guide_click(self):
        """Primo click: Info Overlay. Secondo click (mentre info è visibile): Guida Completa."""
        if self.info_overlay.isVisible():
            self.hide_info_overlay()
            self.show_full_guide()
        else:
            item = self.channel_list.currentItem()
            if item:
                self.show_info_overlay(item.data(Qt.ItemDataRole.UserRole))

    def show_full_guide(self):
        """Mostra il palinsesto completo in una finestra di dialogo."""
        item = self.channel_list.currentItem()
        if not item: return
        chan_data = item.data(Qt.ItemDataRole.UserRole)
        guide = self.fetch_real_epg(chan_data["name"])
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Guida Programmi - {chan_data['name']}")
        dialog.setMinimumSize(500, 400)
        dialog.setStyleSheet("background-color: #121212; color: white;")
        layout = QVBoxLayout(dialog)
        header = QLabel(f"PALINSESTO DI OGGI: {chan_data['name']}")
        header.setStyleSheet("color: #D4AF37; font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        browser = QTextBrowser()
        browser.setStyleSheet("background-color: #1e1e1e; border: none; font-size: 14px;")
        html = "<table width='100%' cellpadding='10'>"
        for p in guide:
            color = "#D4AF37" if p == guide[1] else "white"
            weight = "bold" if p == guide[1] else "normal"
            marker = "▶ " if p == guide[1] else ""
            html += f"<tr style='color:{color}; font-weight:{weight};'>"
            html += f"<td width='80'>{p['time']}</td>"
            html += f"<td>{marker}{p['title']}</td></tr>"
        html += "</table>"
        browser.setHtml(html)
        layout.addWidget(browser)
        close_btn = QPushButton("CHIUDI")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        dialog.exec()

    def switch_to_smart_app(self, data):
        """Passa alla visualizzazione browser per i servizi web."""
        self.stop_stream()
        self.view_stack.setCurrentIndex(2)
        if QWebEngineView:
            self.web_view.setUrl(QUrl(data["url"]))
            self.status_label.setText(f"Navigazione interna: {data['name']}")
        else:
            QMessageBox.warning(self, "Modulo Mancante", "PyQt6-WebEngine necessario.")

    def launch_suite_app(self, script_name):
        """Avvia un'applicazione della suite come processo separato."""
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
        if os.path.exists(script_path):
            try:
                # Usa subprocess.Popen per lanciare lo script come processo separato
                subprocess.Popen([sys.executable, script_path], creationflags=subprocess.DETACHED_PROCESS)
            except Exception as e:
                QMessageBox.critical(self, "Errore Avvio App", f"Impossibile avviare {script_name}:\n{e}")
        else:
            QMessageBox.warning(self, "Modulo Mancante", "PyQt6-WebEngine necessario.")

    def import_playlist(self):
        """Seleziona un file M3U, lo imposta come predefinito e ricarica i canali."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleziona Playlist M3U", "", "Playlist (*.m3u *.m3u8);;Tutti i file (*)")
        if file_path:
            self.settings["playlist_path"] = file_path
            self.save_settings()
            self.search_bar.clear() # Reset della ricerca al caricamento di una nuova playlist
            self.channels = self.load_channels_from_m3u()
            self.load_channels()
            self.status_label.setText(f"Playlist ricaricata: {os.path.basename(file_path)}")

    def on_esc_pressed(self):
        """Gestore specifico per il tasto ESC attivato tramite QShortcut."""
        if self.isFullScreen():
            self.toggle_fullscreen()
        elif self.view_stack.currentIndex() != 0:
            # Se non siamo a schermo intero ma siamo in una sottosezione (Browser/Apps), torna alla Home
            self.view_stack.setCurrentIndex(0)

    def keyPressEvent(self, event):
        """Gestione dei tasti per telecomandi Bluetooth e tastiere."""
        try:
            if not self.channel_list or not self.mpv_player:
                super().keyPressEvent(event)
                return
            key = event.key()

            # --- OK / Selezione / Invio ---
            if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Select]:
                if self.channel_list.hasFocus():
                    item = self.channel_list.currentItem()
                    if item:
                        QTimer.singleShot(20, lambda: self.on_channel_clicked(item))
                else:
                    self.play_stream()
                event.accept()
                return

            # --- Play / Pausa ---
            elif key in [Qt.Key.Key_MediaPlay, Qt.Key.Key_Play, Qt.Key.Key_MediaPause, Qt.Key.Key_Pause, Qt.Key.Key_MediaTogglePlayPause, Qt.Key.Key_P, Qt.Key.Key_Space]:
                self.pause_stream()
                event.accept()
                return

            # --- Stop ---
            elif key in [Qt.Key.Key_MediaStop, Qt.Key.Key_Stop, Qt.Key.Key_S]:
                QTimer.singleShot(50, self.stop_stream)
                event.accept()
                return

            # --- Registrazione ---
            elif key in [Qt.Key.Key_MediaRecord, Qt.Key.Key_Record, Qt.Key.Key_R]:
                self.toggle_recording()
                event.accept()
                return
            
            # --- Volume ---
            elif key in [Qt.Key.Key_VolumeUp, Qt.Key.Key_Plus, Qt.Key.Key_Right]:
                if self.view_stack.currentIndex() == 2:
                    super().keyPressEvent(event); return
                self.volume_slider.setValue(min(100, self.volume_slider.value() + 5))
                event.accept()
                return
            elif key in [Qt.Key.Key_VolumeDown, Qt.Key.Key_Minus, Qt.Key.Key_Left]:
                if self.view_stack.currentIndex() == 2:
                    super().keyPressEvent(event); return
                self.volume_slider.setValue(max(0, self.volume_slider.value() - 5))
                event.accept()
                return
            elif key == Qt.Key.Key_VolumeMute:
                self.mpv_player.mute = not getattr(self.mpv_player, 'mute', False)
                event.accept()
                return

            # --- Zapping Canali ---
            elif key in [Qt.Key.Key_Up, Qt.Key.Key_ChannelUp, Qt.Key.Key_PageUp, Qt.Key.Key_MediaPrevious]:
                if self.channel_list.count() == 0: return
                curr = self.channel_list.currentRow()
                new_row = curr - 1 if curr > 0 else self.channel_list.count() - 1
                self.channel_list.setCurrentRow(new_row)
                item = self.channel_list.item(new_row)
                if item:
                    self.channel_list.scrollToItem(item)
                    self.on_channel_clicked(item)
                event.accept()
                return
            elif key in [Qt.Key.Key_Down, Qt.Key.Key_ChannelDown, Qt.Key.Key_PageDown, Qt.Key.Key_MediaNext]:
                if self.channel_list.count() == 0: return
                curr = self.channel_list.currentRow()
                new_row = curr + 1 if curr < self.channel_list.count() - 1 else 0
                self.channel_list.setCurrentRow(new_row)
                item = self.channel_list.item(new_row)
                if item:
                    self.channel_list.scrollToItem(item)
                    self.on_channel_clicked(item)
                event.accept()
                return

            # --- Info / Guida / Back ---
            elif key in [Qt.Key.Key_Info, Qt.Key.Key_I, Qt.Key.Key_Guide, Qt.Key.Key_G]:
                self.handle_guide_click()
                event.accept()
                return
            elif key in [Qt.Key.Key_Back, Qt.Key.Key_BrowserBack]:
                # ESC è ora gestito da on_esc_pressed per maggiore affidabilità
                if self.isFullScreen():
                    self.toggle_fullscreen()
                elif self.view_stack.currentIndex() != 0: self.view_stack.setCurrentIndex(0)
                event.accept()
                return

            # --- Canali Numerici (1-9) ---
            elif Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
                idx = key - Qt.Key.Key_1
                if idx < self.channel_list.count():
                    self.channel_list.setCurrentRow(idx)
                    self.on_channel_clicked(self.channel_list.item(idx))
                event.accept()
                return
        except Exception as e:
            print(f"Errore gestione tasti: {e}")
            
        super().keyPressEvent(event)

    def toggle_multiview(self):
        self.is_multiview = not self.is_multiview
        if self.is_multiview:
            self.init_multiview_players()
            if not self.multi_players:
                self.is_multiview = False
                return
            self.btn_multiview.setText("MULTIVIEW: ON")
            if self.mpv_player: self.mpv_player.stop()
            self.view_stack.setCurrentIndex(3)
            self.status_label.setText("Modalità Multi-View attiva. Clicca sui canali per riempire la griglia.")
        else:
            self.btn_multiview.setText("MULTIVIEW: OFF")
            for p in self.multi_players: p.stop()
            self.view_stack.setCurrentIndex(0)
            self.play_stream()

    def _play_in_multiview(self, url):
        # Seleziona il player corrente nella griglia
        player = self.multi_players[self.current_multi_index]
        final_url = self.apply_mpv_headers(player, url)
        player.loadfile(final_url, mode='replace')
        
        # Passa al quadrante successivo
        self.current_multi_index = (self.current_multi_index + 1) % 4

    def play_stream(self):
        url_text = self.url_input.text().strip()
        if not url_text: return

        if self.is_multiview:
            self.view_stack.setCurrentIndex(3)
            self._play_in_multiview(url_text)
            return

        # Torna alla visualizzazione Video se eravamo nel browser
        self.view_stack.setCurrentIndex(0)
        
        if not self.mpv_player: return
        
        try:
            # Recupera i dati del canale selezionato per mostrare l'overlay info
            item = self.channel_list.currentItem()
            if item:
                chan_data = item.data(Qt.ItemDataRole.UserRole)
                # Mostra l'overlay con un leggero ritardo per assicurarci che il player sia partito
                QTimer.singleShot(400, lambda: self.show_info_overlay(chan_data))

            # Applichiamo gli header e otteniamo l'URL finale (fondamentale per Rai)
            final_url = self.apply_mpv_headers(self.mpv_player, url_text)
            self.status_label.setText(f"Caricamento: {final_url}")
            # 'replace' cambia stream senza distruggere il contesto video, evitando crash
            self.mpv_player.loadfile(final_url, mode='replace')
        except Exception as e:
            self.status_label.setText(f"Errore: {e}")

        self.timer.start()

    def apply_mpv_headers(self, player, url):
        """Configura User-Agent e Referrer per flussi ostici (Rai/Mediaset)."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        player['user-agent'] = ua
        
        headers = []
        if "rai" in url.lower():
            # Forza HTTPS per i flussi Rai
            url = url.replace("http://", "https://")
            player['referrer'] = "https://www.raiplay.it"
            headers.append("Origin: https://www.raiplay.it")
            headers.append("X-Requested-With: it.rai.it.raiplay")
            # Rimuove parametri che forzano UserAgent esterni
            url = re.sub(r'&forceUserAgent=[^&]*', '', url)
        elif "mediaset" in url.lower():
            player['referrer'] = "https://www.mediasetinfinity.it"
            headers.append("Origin: https://www.mediasetinfinity.it")
        else:
            player['referrer'] = ""
            
        if headers:
            # MPV preferisce i nuovi righi (\n) per separare i campi degli header
            player['http-header-fields'] = "\n".join(headers)
        else:
            player['http-header-fields'] = ""
        return url

    def open_local_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Apri Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)")
        if file_path:
            self.url_input.setText(file_path)
            self.play_stream()

    def stop_stream(self):
        try:
            # Chiudi la registrazione in modo sicuro se attiva
            if self.is_recording:
                self._stop_recording_deferred()
                
            # Reset proprietà di registrazione per evitare crash al riavvio
            if self.mpv_player:
                self.mpv_player['stream-record'] = None
                
            if self.mpv_player: self.mpv_player.stop()
            for p in self.multi_players: p.stop()
        except Exception:
            pass
        self.timer.stop()
        self.status_label.setText("Fermato.")
        self.position_slider.setValue(0)

    def pause_stream(self):
        if not self.mpv_player: return
        try:
            self.mpv_player.pause = not self.mpv_player.pause
            if self.mpv_player.pause:
                self.status_label.setText("In pausa.")
                self.timer.stop()
            else:
                self.status_label.setText("In riproduzione.")
                self.timer.start()
        except Exception:
            pass

    def set_position(self, position):
        if self.mpv_player and self.mpv_player.seekable:
            self.mpv_player['percent-pos'] = position / 10.0

    def set_volume(self, volume):
        """Applica il volume in modo asincrono per evitare crash da flood del telecomando."""
        if not hasattr(self, '_vol_debounce_timer'):
            self._vol_debounce_timer = QTimer(self)
            self._vol_debounce_timer.setSingleShot(True)
            self._vol_debounce_timer.timeout.connect(self._apply_volume_now)
        
        self._pending_volume = volume
        self._vol_debounce_timer.start(30) # Aspetta 30ms di inattività prima di inviare a MPV

    def _apply_volume_now(self):
        try:
            vol = getattr(self, '_pending_volume', 70)
            if self.mpv_player: self.mpv_player.volume = vol
            for p in self.multi_players:
                try: p.volume = vol
                except: pass
        except: pass

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.top_control_bar.show()
            self.status_label.show()
            self.splitter.widget(0).show() # Mostra scaletta
            self.suite_app_container.show()
            self.smart_app_container.show()
            self.position_slider.show()
            self.bottom_control_bar.show()
            self.footer_label.show()
            self.btn_fullscreen.setText("SCHERMO INTERO")
        else:
            self.showFullScreen()
            self.top_control_bar.hide()
            self.status_label.hide()
            self.splitter.widget(0).hide() # Nasconde scaletta
            self.suite_app_container.hide()
            self.smart_app_container.hide()
            self.position_slider.hide()
            self.bottom_control_bar.hide()
            self.footer_label.hide()
            self.btn_fullscreen.setText("ESCI FULLSCREEN")
            
            # Mostra messaggio informativo via OSD di MPV
            if self.mpv_player:
                self.mpv_player.show_text("Premi ESC per uscire da schermo intero", 3000)

    def toggle_recording(self):
        url_text = self.url_input.text().strip()
        if not url_text: return

        if not self.is_recording:
            file_path, _ = QFileDialog.getSaveFileName(self, "Salva Registrazione", 
                                                       os.path.expanduser("~/Videos/tv_rec.ts"), 
                                                       "Video TS (*.ts);;Video MP4 (*.mp4)")
            if file_path:
                self.record_path = file_path.replace("\\", "/")
                self.btn_record.setEnabled(False)
                self.stop_stream()
                # Ritardo per pulire i buffer video
                QTimer.singleShot(1200, lambda: self._start_recording_deferred(url_text, self.record_path))
                self.status_label.setText("Inizializzazione registrazione...")
        else:
            try:
                if self.mpv_player: 
                    self._stop_recording_deferred()
            except Exception:
                pass

    def _start_recording_deferred(self, url_text, record_path):
        try:
            self.is_recording = True
            self.btn_record.setEnabled(True)
            self.btn_record.setText("STOP REGISTRAZIONE")
            self.status_label.setText("REGISTRAZIONE ATTIVA")

            # Configura MPV per il dump del flusso su file
            self.apply_mpv_headers(self.mpv_player, url_text)
            self.mpv_player['stream-record'] = record_path
            
            # Ricarichiamo il flusso: MPV inizierà a scrivere sul file appena il flusso parte
            self.mpv_player.loadfile(url_text, mode='replace')
            self.timer.start()
        except Exception as e:
            self.is_recording = False
            self.btn_record.setEnabled(True)
            self.btn_record.setText("REGISTRA")
            QMessageBox.critical(self, "Errore", f"Impossibile avviare registrazione: {e}")

    def _stop_recording_deferred(self):
        """Ferma la registrazione e pulisce MPV senza chiudere l'app."""
        if self.mpv_player:
            self.mpv_player['stream-record'] = None
            # Ricarica il canale corrente per chiudere correttamente il file video
            url = self.url_input.text()
            self.mpv_player.loadfile(url, mode='replace')
        
        self.is_recording = False
        self.btn_record.setText("REGISTRA")
        self.btn_record.setEnabled(True)
        self.status_label.setText("Registrazione salvata.")
        QMessageBox.information(self, "Registrazione", f"Salvata con successo in:\n{self.record_path}")

    def toggle_pip_mode(self):
        if self.pip_window is None:
            self.pip_window = QWidget()
            self.pip_window.setWindowTitle("PiP")
            self.pip_window.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
            self.pip_window.setGeometry(100, 100, 320, 180) # Default size for PiP
            self.pip_window.setStyleSheet("background-color: black;")

            pip_layout = QVBoxLayout(self.pip_window)
            pip_layout.setContentsMargins(0, 0, 0, 0)

            pip_video = QWidget()
            pip_video.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
            pip_layout.addWidget(pip_video)

            # MPV permette di cambiare il contenitore video al volo!
            self.mpv_player.wid = str(int(pip_video.winId()))

            self.pip_window.show()
            self.btn_pip.setText("ESCI PiP")
        else:
            self.mpv_player.wid = str(int(self.video_output.winId()))
            self.pip_window.close(); self.pip_window = None
            self.btn_pip.setText("PiP")


    def update_ui_status(self):
        if not self.mpv_player: return
        
        try:
            # Percentuale posizione
            perc = self.mpv_player.percent_pos
            if perc: self.position_slider.setValue(int(perc * 10))
            
            # Tempo e Durata
            t = self.mpv_player.time_pos
            d = self.mpv_player.duration
            if t and d:
                t_str = QTime(0,0).addSecs(int(t)).toString("mm:ss")
                d_str = QTime(0,0).addSecs(int(d)).toString("mm:ss")
                self.status_label.setText(f"In riproduzione: {t_str} / {d_str}")
            elif t:
                t_str = QTime(0,0).addSecs(int(t)).toString("mm:ss")
                self.status_label.setText(f"Live: {t_str}")
        except:
            pass

    def closeEvent(self, event):
        if self.mpv_player: self.mpv_player.terminate()
        for p in self.multi_players: p.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = TVLiveInternazionale()
    player.showMaximized()
    sys.exit(app.exec())