import os
import sys
import json
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from PIL import Image, ImageTk
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


# Configurazione predefinita (può essere spostata in un file config.json)
DEFAULT_CONFIG = {
    "platforms": {
        "Xbox": {
            "extensions": [".xbe", ".iso"],
            "folder": "emulators/xbox",
            "executable": "xemu.exe",
            "args": ["-full-screen"]
        },
        "NES": {
            "extensions": [".nes"],
            "folder": "emulators/nes",
            "executable": "fceux64.exe",
            "args": ["-f", "1"]
        },
        "SNES": {
            "extensions": [".smc", ".sfc", ".fig"],
            "folder": "emulators/snes",
            "executable": "snes9x-x64.exe",
            "args": ["-fullscreen"]
        },
        "N64": {
            "extensions": [".n64", ".z64", ".v64"],
            "folder": "emulators/n64",
            "executable": "mupen64plus.exe",
            "args": ["--fullscreen"]
        },
        "GB/GBC/GBA": {
            "extensions": [".gb", ".gbc", ".gba"],
            "folder": "emulators/gba",
            "executable": "mGBA.exe",
            "args": ["-f"]
        },
        "NDS": {
            "extensions": [".nds"],
            "folder": "emulators/nds",
            "executable": "DeSmuME_0_9_13_x64.exe",
            "args": []
        },
        "PS1": {
            "extensions": [".iso", ".bin", ".cue", ".pbp"],
            "folder": "emulators/ps1",
            "executable": "psxfin.exe",
            "args": ["-f"]
        },
        "PSP": {
            "extensions": [".iso", ".cso"],
            "folder": "emulators/psp",
            "executable": "PPSSPPWindows64.exe",
            "args": ["--fullscreen"]
        },
        "PS2": {
            "extensions": [".iso", ".cso", ".chd"],
            "folder": "emulators/ps2", # Modificato per corrispondere al nome della cartella roms/ps2
            "executable": "pcsx2/pcsx2-qt.exe", # Percorso dell'eseguibile relativo alla nuova cartella
            "args": []
        },
        "PS3": {
            "extensions": [".iso", ".pkg", ".bin", ".elf", ".self"],
            "folder": "emulators/ps3",
            "executable": "rpcs3.exe",
            "args": []
        },
        "GENESIS": {
            "extensions": [".md", ".smd", ".gen", ".bin"],
            "folder": "emulators/genesis",
            "executable": "Fusion.exe",
            "args": ["-fullscreen"]
        },
        "Xbox 360": {
            "extensions": [".iso", ".xex", ".rar", ".zip"], # Estensioni comuni per Xbox 360
            "folder": "emulators/xbox360",
            "executable": "xenia.exe",
            "args": ["--fullscreen"]
        },
        "PS4": {
            "extensions": [".bin", ".iso", ".pkg"],
            "folder": "emulators/ps4",
            "executable": "shadPS4QtLauncher.exe",
            "args": []
        },
        "GameCube": {
            "extensions": [".iso", ".gcm", ".gcz", ".rvz", ".elf", ".dol"],
            "folder": "emulators/game_qube",
            "executable": "Dolphin.exe",
            "args": ["-b", "-e"]
        }
    }
}

EMU_SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emulator_settings.json")

class UniversalEmulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Emulator Pro")
        self.root.state('zoomed') # Avvia massimizzato
        self.settings = self.load_settings()
        self.root.attributes('-fullscreen', False) # Impostabile a True se preferisci il fullscreen totale senza barra
        self.root.configure(bg="#121212")
        self.config = DEFAULT_CONFIG
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.roms_dir = os.path.join(self.base_dir, "roms")
        self.selected_game_path = None
        self.game_images = []  # Cache per evitare il garbage collection delle immagini
        self.game_widgets = [] # Riferimenti ai widget per navigazione gamepad
        self.current_selected_idx = -1
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        if PYGAME_AVAILABLE:
            self.init_gamepad()

        # Supporto per Virtual Gamepad via Tastiera (molte app smartphone usano questo)
        self.setup_keyboard_nav()

        self.setup_ui()
        self.refresh_game_list()

    def setup_ui(self):
        # Configurazione colori
        bg_color = "#1e1e1e"      # Scuro profondo
        surface_color = "#2d2d2d" # Grigio scuro per i widget
        gold_color = "#d4af37"    # Oro metallico
        text_white = "#ffffff"

        style = ttk.Style()
        style.theme_use('clam') # 'clam' è più personalizzabile

        # Stili per i Frame e Label
        style.configure("TFrame", background=bg_color)
        style.configure("Dark.TLabel", background=bg_color, foreground=text_white, font=("Helvetica", 10))
        style.configure("Header.TLabel", background=bg_color, foreground=gold_color, font=("Helvetica", 18, "bold"))
        style.configure("Brand.TLabel", background=bg_color, foreground=gold_color, font=("Helvetica", 48, "bold"))
        
        # Stile per la lista (Treeview)
        style.configure("Treeview", 
                        background=surface_color, 
                        foreground=text_white, 
                        fieldbackground=surface_color,
                        borderwidth=0,
                        font=("Helvetica", 11))
        style.map("Treeview", background=[('selected', gold_color)], foreground=[('selected', 'black')])
        
        # Stile per il Bottone Oro
        style.configure("Gold.TButton", 
                        background=gold_color, 
                        foreground="black", 
                        font=("Helvetica", 11, "bold"),
                        borderwidth=0,
                        padding=10)
        style.map("Gold.TButton", background=[('active', '#b8962e')]) # Feedback al passaggio del mouse

        # Titolo pulsante in alto
        self.pulsing_label = tk.Label(self.root, text="THE GREATEST GAMES OF ALL TIME", 
                                     bg=bg_color, fg=gold_color, 
                                     font=("Helvetica", 18, "bold"))
        self.pulsing_label.pack(pady=(5, 0))
        self.animate_pulsing_label()

        self.header = ttk.Label(self.root, text="UNIVERSAL EMULATOR PRO", style="Header.TLabel")
        self.header.pack(pady=10)

        # Pulsante per caricamento manuale spostato in alto
        self.btn_manual = ttk.Button(self.root, text="CARICA ROM ESTERNA", command=self.on_select_game, style="Gold.TButton")
        self.btn_manual.pack(pady=(0, 10))

        # Frame filtri (Ricerca + Console)
        controls_frame = ttk.Frame(self.root, style="TFrame")
        controls_frame.pack(pady=5)
        
        # Ricerca testuale
        ttk.Label(controls_frame, text="CERCA GIOCO:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(10, 2))
        self.search_var = tk.StringVar()
        self.search_var.set(self.settings.get("search", ""))
        self.search_var.trace_add("write", lambda *args: self.refresh_game_list())
        self.search_entry = ttk.Entry(controls_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=10)

        # Filtro Console
        ttk.Label(controls_frame, text="SISTEMA:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(10, 2))
        platforms = ["Tutti i sistemi"] + sorted(list(self.config["platforms"].keys()))
        self.platform_filter = ttk.Combobox(controls_frame, values=platforms, state="readonly", width=15)
        self.platform_filter.set(self.settings.get("platform", "Tutti i sistemi"))
        self.platform_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_game_list())
        self.platform_filter.pack(side=tk.LEFT, padx=10)

        self.container = ttk.Frame(self.root, style="TFrame")
        self.container.pack(fill=tk.BOTH, expand=True, padx=50)

        # Setup Area Scorrevole per le copertine
        self.canvas = tk.Canvas(self.container, bg=bg_color, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="TFrame")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Adatta larghezza frame al canvas
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Scroll con rotella mouse
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.status_var = tk.StringVar(value="Pronto")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, style="Dark.TLabel", foreground=gold_color)
        self.status_label.pack(pady=2)

        self.footer_label = tk.Label(self.root, text="Powered by Daniele Barile", bg="#1e1e1e", fg="#d4af37", font=("Helvetica", 14, "bold"))
        self.footer_label.pack(side=tk.BOTTOM, pady=2)

        if not PYGAME_AVAILABLE:
            self.status_var.set("Gamepad non disponibile: installa pygame (pip install pygame)")

    def init_gamepad(self):
        """Inizializza il modulo joystick di pygame."""
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.status_var.set(f"🎮 Gamepad rilevato: {self.joystick.get_name()}")
            self.root.after(100, self.poll_gamepad)
        else:
            self.joystick = None
            self.status_var.set("In attesa di Gamepad (Bluetooth o Virtuale)...")
            # Riprova a cercare il controller ogni 2 secondi
            self.root.after(2000, self.init_gamepad)

    def poll_gamepad(self):
        """Controlla periodicamente gli input del gamepad."""
        if not self.joystick or pygame.joystick.get_count() == 0:
            self.init_gamepad()
            return
        
        pygame.event.pump()
        
        # Navigazione con il DPAD (Hat)
        try:
            hat = self.joystick.get_hat(0)
            if hat != (0, 0):
                if not getattr(self, '_hat_debounced', False):
                    self.move_selection(hat[0], -hat[1])
                    self._hat_debounced = True
            else:
                self._hat_debounced = False
        except: pass

        # Analogico sinistro come alternativa al DPAD
        axis_x, axis_y = self.joystick.get_axis(0), self.joystick.get_axis(1)
        if abs(axis_x) > 0.4 or abs(axis_y) > 0.4:
            if not getattr(self, '_axis_debounced', False):
                dx = 1 if axis_x > 0.5 else -1 if axis_x < -0.5 else 0
                dy = 1 if axis_y > 0.5 else -1 if axis_y < -0.5 else 0
                self.move_selection(dx, dy)
                self._axis_debounced = True
        else:
            self._axis_debounced = False

        # Tasto di conferma (Pulsante 0, 1, 2, 3 o Start/7)
        # I gamepad virtuali hanno spesso mappature miste, controlliamo i più probabili
        try:
            num_btns = self.joystick.get_numbuttons()
            btn_pressed = any(self.joystick.get_button(i) for i in [0, 1, 2, 3, 7] if i < num_btns)
        except:
            btn_pressed = False

        if btn_pressed:
            if not getattr(self, '_btn_debounced', False):
                self.select_current_game()
                self._btn_debounced = True
        else:
            self._btn_debounced = False
            
        self.root.after(100, self.poll_gamepad)

    def setup_keyboard_nav(self):
        """Mappa i tasti della tastiera per la navigazione."""
        self.root.bind("<Up>", lambda e: self._handle_key_nav(0, -1))
        self.root.bind("<Down>", lambda e: self._handle_key_nav(0, 1))
        self.root.bind("<Left>", lambda e: self._handle_key_nav(-1, 0))
        self.root.bind("<Right>", lambda e: self._handle_key_nav(1, 0))
        self.root.bind("<Return>", lambda e: self._handle_key_confirm())
        self.root.bind("<space>", lambda e: self._handle_key_confirm())

    def _handle_key_nav(self, dx, dy):
        """Gestisce il movimento se non si sta scrivendo nella barra di ricerca."""
        if not isinstance(self.root.focus_get(), (ttk.Entry, tk.Entry)):
            self.move_selection(dx, dy)

    def _handle_key_confirm(self):
        """Gestisce l'avvio se non si sta scrivendo nella barra di ricerca."""
        if not isinstance(self.root.focus_get(), (ttk.Entry, tk.Entry)):
            self.select_current_game()

    def move_selection(self, dx, dy):
        """Sposta l'evidenziazione nella griglia."""
        if not self.game_widgets: return
        
        cols = 10
        num_games = len(self.game_widgets)
        
        if self.current_selected_idx == -1:
            new_idx = 0
        else:
            row = self.current_selected_idx // cols
            col = self.current_selected_idx % cols
            
            new_col = max(0, min(cols - 1, col + dx))
            new_row = row + dy
            new_idx = new_row * cols + new_col
            
            if new_idx < 0: new_idx = 0
            if new_idx >= num_games: new_idx = num_games - 1

        self.highlight_game(new_idx)

    def highlight_game(self, index):
        """Applica l'effetto hover visivo al gioco selezionato via gamepad."""
        # Rimuove evidenziazione precedente
        if self.current_selected_idx != -1 and self.current_selected_idx < len(self.game_widgets):
            f, li, ln, _, _ = self.game_widgets[self.current_selected_idx]
            for w in (f, li, ln):
                w.config(bg="#2d2d2d")
            f.config(highlightthickness=0)

        self.current_selected_idx = index
        f, li, ln, path, plat = self.game_widgets[index]
        
        # Applica nuovo colore (oro per indicare focus gamepad)
        # Resetta lo spessore del bordo per tutti
        for w_data in self.game_widgets: w_data[0].config(highlightthickness=0)
        for w in (f, li, ln): w.config(bg="#3d3d3d")
        f.config(highlightbackground="#d4af37", highlightthickness=3)

        # Scroll automatico per rendere visibile l'elemento
        self.ensure_widget_visible(f)

    def ensure_widget_visible(self, widget):
        """Sposta la scrollbar per mostrare il widget selezionato."""
        self.root.update_idletasks()
        y = widget.winfo_y()
        h = widget.winfo_height()
        canvas_h = self.canvas.winfo_height()
        scroll_region = self.canvas.bbox("all")[3]
        
        if y < self.canvas.canvasy(0):
            self.canvas.yview_moveto(y / scroll_region)
        elif y + h > self.canvas.canvasy(canvas_h):
            self.canvas.yview_moveto((y + h - canvas_h) / scroll_region)

    def select_current_game(self):
        """Avvia il gioco attualmente evidenziato dal gamepad."""
        if self.current_selected_idx != -1 and self.current_selected_idx < len(self.game_widgets):
            _, _, _, path, platform = self.game_widgets[self.current_selected_idx]
            self.process_game(path, platform)

    def load_settings(self):
        if os.path.exists(EMU_SETTINGS):
            try:
                with open(EMU_SETTINGS, "r") as f:
                    return json.load(f)
            except: pass
        return {"search": "", "platform": "Tutti i sistemi"}

    def save_settings(self):
        self.settings["search"] = self.search_var.get()
        self.settings["platform"] = self.platform_filter.get()
        try:
            with open(EMU_SETTINGS, "w") as f:
                json.dump(self.settings, f, indent=4)
        except: pass

    def on_closing(self):
        self.save_settings()
        self.root.destroy()

    def animate_pulsing_label(self, step=0):
        """Crea un effetto di pulsazione del colore per il titolo principale."""
        # Sequenza di colori (tonalità di oro verso il bianco e ritorno)
        colors = ["#d4af37", "#e1c15e", "#eee385", "#ffffff", "#eee385", "#e1c15e"]
        if hasattr(self, 'pulsing_label') and self.pulsing_label.winfo_exists():
            self.pulsing_label.config(fg=colors[step % len(colors)])
            self.root.after(150, lambda: self.animate_pulsing_label(step + 1))

    def find_cover(self, game_name, game_folder):
        """Cerca un file immagine corrispondente al nome del gioco."""
        img_exts = [".png", ".jpg", ".jpeg"]

        def find_matching_file(directory, filename):
            direct_path = os.path.join(directory, filename)
            if os.path.exists(direct_path):
                return direct_path
            try:
                filename_lower = filename.casefold()
                for entry in os.listdir(directory):
                    if entry.casefold() == filename_lower:
                        return os.path.join(directory, entry)
            except OSError:
                pass
            return None
        
        # Cerca nella cartella del gioco e risale fino alla root delle ROM
        current_dir = game_folder
        roms_dir_norm = os.path.normpath(self.roms_dir).lower()
        
        while True:
            for ext in img_exts:
                img_path = find_matching_file(current_dir, f"{game_name}{ext}")
                if img_path:
                    return img_path
            
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir or not current_dir.lower().startswith(roms_dir_norm):
                break
            current_dir = parent_dir

        # Fallback sulla cartella media
        media_dir = os.path.join(self.roms_dir, "media")
        if os.path.exists(media_dir):
            for ext in img_exts:
                img_path = find_matching_file(media_dir, f"{game_name}{ext}")
                if img_path:
                    return img_path
        return None

    def refresh_game_list(self):
        """Scansiona la cartella 'roms' alla ricerca di giochi supportati."""
        if not os.path.exists(self.roms_dir):
            os.makedirs(self.roms_dir)
            return

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.game_images = []
        self.game_widgets = []
        self.current_selected_idx = -1
        # Utilizziamo un dizionario per raggruppare i file ed evitare duplicati (es. .bin e .cue)
        games_found = {}
        # Normalizziamo il percorso principale delle ROM per confronti sicuri
        # Usiamo abspath per gestire correttamente le differenze tra "roms" e "Roms" su Windows
        roms_dir_norm = os.path.normpath(os.path.abspath(self.roms_dir)).lower()

        # Raccoglie tutti i giochi supportati in una lista unica
        for root_dir, dirs, files in os.walk(self.roms_dir):
            # Normalizziamo il percorso della cartella corrente
            root_dir_norm = os.path.normpath(os.path.abspath(root_dir)).lower()
            excluded_ps4_game_dir = os.path.normpath(os.path.abspath(os.path.join(
                self.roms_dir, "ps4", "Fist of the North Star Lost Paradise (EUR)"
            ))).lower()
            if root_dir_norm.startswith(excluded_ps4_game_dir + os.sep):
                continue
            only_eboot_in_excluded_game = root_dir_norm == excluded_ps4_game_dir
            # Identifica le sottocartelle nel percorso relativo
            rel_root = os.path.relpath(root_dir_norm, roms_dir_norm)

            # Definisci le cartelle specifiche da escludere (NFS e PS3_UPDATE)
            specific_excluded_subfolders = [
                os.path.normpath(os.path.join("ps3", "BLES00175-[Need for Speed ProStreet]", "PS3_GAME", "USRDIR", "NFS")).lower(),
                os.path.normpath(os.path.join("ps3", "BLES00175-[Need for Speed ProStreet]", "PS3_UPDATE")).lower()
            ]
            is_specific_folder_excluded = any(rel_root == s_folder or rel_root.startswith(s_folder + os.sep) for s_folder in specific_excluded_subfolders)

            # Esclude cartelle di sistema o specifiche
            excluded_folders = ["icons", "sce_module", "sce_sys"]
            if is_specific_folder_excluded or any(part in rel_root.lower().replace("\\", "/").split('/') for part in excluded_folders) or \
               rel_root.lower().replace("\\", "/").startswith("ps4/cusa01073/asset_archive"):
                continue

            path_parts = rel_root.split(os.sep) if rel_root != "." else []
            for file in files:
                # Esclude i file tecnici che non sono giochi
                if file.lower() in ["dat.bin", "pathid_list_ps4.bin"]:
                    continue
                if only_eboot_in_excluded_game and file.casefold() != "eboot.bin":
                    continue
                ext = os.path.splitext(file)[1].lower()
                if not ext or ext in [".bat", ".dll", ".exe", ".txt", ".plt", ".png", ".jpg", ".jpeg"]:
                    continue

                full_path = os.path.join(root_dir, file)
                game_name = os.path.splitext(file)[0]
                # Se il nome del file è generico (es. default.xex), usa il nome della cartella del gioco
                if game_name.lower() in ["default", "eboot", "boot", "game", "index"]:
                    game_name = os.path.basename(root_dir)

                # Se il nome ottenuto è un ID CUSA, cerchiamo nella cartella un file immagine con un nome
                # descrittivo (es. Ratchet.and.Clank...) per usarlo come titolo della card nella UI.
                if game_name.lower().startswith("cusa"):
                    try:
                        for f in os.listdir(root_dir):
                            if f.lower().endswith((".jpg", ".png", ".jpeg")) and not f.lower().startswith("cusa"):
                                game_name = os.path.splitext(f)[0]
                                break
                    except Exception:
                        pass

                if game_name.lower() in ["pkg_settings"]:
                    continue

                detected_plat = None

                # I giochi PS4 estratti vengono avviati dal file eboot.bin.
                # L'estensione .bin è condivisa con PS1, PS3 e GENESIS, quindi
                # il nome del file deve avere precedenza sul rilevamento generico.
                if file.casefold() == "eboot.bin":
                    detected_plat = "PS4"
                elif ext == ".pkg" and any(part.casefold() == "ps3" for part in path_parts):
                    detected_plat = "PS3"
                
                # 1. Priorità: Cerca se una delle cartelle nel percorso corrisponde al sistema
                if not detected_plat:
                    for plat, config in self.config["platforms"].items():
                        conf_folder = os.path.basename(config["folder"]).lower()
                        # Verifica che il percorso corrisponda E che l'estensione sia tra quelle supportate
                        if (any(p == conf_folder or p == plat.lower() for p in path_parts)) and (ext in config["extensions"]):
                            detected_plat = plat
                            break
                
                # 2. Fallback: Se non trova la cartella, usa l'estensione
                if not detected_plat:
                    for plat, config in self.config["platforms"].items():
                        if ext in config["extensions"]:
                            detected_plat = plat
                            break
                
                if detected_plat:
                    # Priorità delle estensioni: se troviamo un .cue o .iso, preferiamolo al .bin
                    priority = [".cue", ".iso", ".chd", ".pbp", ".nds", ".gba", ".xex", ".zip", ".rar", ".bin", ".pkg"]
                    key = (root_dir, game_name)
                    
                    if key not in games_found:
                        games_found[key] = {
                            "name": game_name,
                            "path": full_path,
                            "platform": detected_plat,
                            "folder": root_dir
                        }
                    else:
                        # Se esiste già, controlla se l'estensione attuale è "migliore"
                        old_ext = os.path.splitext(games_found[key]["path"])[1].lower()
                        if ext in priority:
                            if old_ext not in priority or priority.index(ext) < priority.index(old_ext):
                                games_found[key]["path"] = full_path
                                games_found[key]["platform"] = detected_plat

        # Recupera i pacchetti PS3 presenti direttamente nella cartella standard
        # anche se una scansione del filesystem li ha saltati.
        ps3_dir = next(
            (os.path.join(self.roms_dir, entry) for entry in os.listdir(self.roms_dir)
             if entry.casefold() == "ps3" and os.path.isdir(os.path.join(self.roms_dir, entry))),
            None
        )
        if ps3_dir:
            for file in os.listdir(ps3_dir):
                if not file.casefold().endswith(".pkg"):
                    continue
                full_path = os.path.join(ps3_dir, file)
                game_name = os.path.splitext(file)[0]
                key = (ps3_dir, game_name)
                if key not in games_found:
                    games_found[key] = {
                        "name": game_name,
                        "path": full_path,
                        "platform": "PS3",
                        "folder": ps3_dir
                    }

        all_games = list(games_found.values())
        # In "Tutti i sistemi" mostra subito i giochi PS4, poi gli altri sistemi.
        selected_platform = self.platform_filter.get() if hasattr(self, "platform_filter") else "Tutti i sistemi"
        if selected_platform.casefold() == "tutti i sistemi":
            all_games.sort(key=lambda x: (0 if x["platform"].casefold() == "ps4" else 1,
                                          x["platform"].lower(), x["name"].lower()))
        else:
            all_games.sort(key=lambda x: (x["platform"].lower(), x["name"].lower()))

        # Applica il filtro se selezionato
        if hasattr(self, 'platform_filter'):
            if selected_platform.casefold() != "tutti i sistemi":
                all_games = [g for g in all_games if g["platform"].casefold() == selected_platform.casefold()]
        
        # Applica la ricerca testuale
        search_text = self.search_var.get().lower()
        if search_text:
            all_games = [g for g in all_games if search_text in g["name"].lower()]

        # Aggiorna lo stato con il conteggio
        self.status_var.set(f"Trovati {len(all_games)} giochi")

        # Crea un unico contenitore grid per tutte le card
        grid_frame = ttk.Frame(self.scrollable_frame, style="TFrame")
        grid_frame.pack(fill="x", padx=10, pady=20)
        
        cols = 10 
        for i, game in enumerate(all_games):
            img_path = self.find_cover(game["name"], game["folder"])
            
            shadow_frame = tk.Frame(grid_frame, bg="#0a0a0a", bd=0)
            shadow_frame.grid(row=i//cols, column=i%cols, padx=15, pady=15)

            item_frame = tk.Frame(shadow_frame, bg="#2d2d2d", cursor="hand2", 
                                 relief="raised", borderwidth=3)
            item_frame.pack(padx=(0, 4), pady=(0, 4))
            
            if img_path:
                try:
                    pil_img = Image.open(img_path)
                    pil_img.thumbnail((160, 220), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    self.game_images.append(tk_img)
                    lbl_img = tk.Label(item_frame, image=tk_img, bg="#2d2d2d", bd=0)
                except:
                    lbl_img = tk.Label(item_frame, text=game["name"], wraplength=140, width=15, height=8, bg="#2d2d2d", fg="white")
            else:
                lbl_img = tk.Label(item_frame, text=game["name"], wraplength=140, width=15, height=8, bg="#2d2d2d", fg="white")
            
            lbl_img.pack()
            lbl_name = tk.Label(item_frame, text=game["name"], bg="#2d2d2d", fg="white", font=("Helvetica", 9), wraplength=150)
            lbl_name.pack(pady=2, fill="x")
            
            # Funzioni per l'effetto Hover definite correttamente
            def on_enter(e, f=item_frame, li=lbl_img, ln=lbl_name):
                for w in (f, li, ln): w.config(bg="#3d3d3d")
                
            def on_leave(e, f=item_frame, li=lbl_img, ln=lbl_name):
                # Se è il gioco selezionato dal gamepad, non togliamo l'evidenziazione grigia
                if self.current_selected_idx != -1 and self.game_widgets[self.current_selected_idx][0] == f:
                    return
                for w in (f, li, ln): w.config(bg="#2d2d2d")

            # Bind per avvio gioco al click e per l'effetto hover (posizionati fuori dalle funzioni)
            for w in (item_frame, lbl_img, lbl_name):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", lambda e, p=game["path"], k=game["platform"]: self.process_game(p, k))

            # Salva riferimenti per navigazione gamepad
            self.game_widgets.append((item_frame, lbl_img, lbl_name, game["path"], game["platform"]))

    def on_select_game(self):
        # Genera automaticamente la lista delle estensioni supportate dalla configurazione
        all_exts = []
        for platform in self.config["platforms"].values():
            all_exts.extend(platform["extensions"])
        
        file_path = filedialog.askopenfilename(
            title="Apri ROM",
            filetypes=[("File di Gioco", " ".join([f"*{e}" for e in list(set(all_exts))])), ("Tutti i file", "*.*")]
        )
        if file_path:
            self.process_game(file_path)

    def process_game(self, game_path, platform_key=None):
        if platform_key:
            self.run_emulator_logic(platform_key, game_path)
            return

        ext = os.path.splitext(game_path)[1].lower()

        # Solo i .bin presenti in roms/ps4 e nelle sue sottocartelle usano shadPS4.
        ps4_roms_dir = os.path.normcase(os.path.abspath(os.path.join(self.roms_dir, "ps4")))
        game_dir = os.path.normcase(os.path.abspath(game_path))
        try:
            is_ps4_rom = os.path.commonpath([game_dir, ps4_roms_dir]) == ps4_roms_dir
        except ValueError:
            is_ps4_rom = False
        if ext == ".bin" and is_ps4_rom:
            self.run_emulator_logic("PS4", game_path)
            return
        
        # Prova a rilevare la piattaforma dal percorso della cartella (anche per caricamento manuale)
        path_lower = game_path.lower()
        for plat, config in self.config["platforms"].items():
            folder_name = os.path.basename(config["folder"]).lower()
            # Cerca se il percorso contiene la cartella dell'emulatore tra i separatori di sistema
            if f"{os.sep}{folder_name}{os.sep}" in path_lower or path_lower.startswith(folder_name + os.sep):
                self.run_emulator_logic(plat, game_path)
                return

        # Trova tutte le piattaforme che supportano questa estensione
        matches = [name for name, data in self.config["platforms"].items() if ext in data["extensions"]]

        # Vecchia logica di fallback se non è in una sottocartella specifica
        if not matches:
            messagebox.showerror("Errore", "Estensione file non supportata.")
            return

        if len(matches) > 1:
            # Se l'estensione è ambigua (es. .iso per PS1/PSP/PS2), chiede all'utente
            self.ask_platform_choice(matches, game_path)
        else:
            self.run_emulator_logic(matches[0], game_path)

    def ask_platform_choice(self, platforms, game_path):
        choice_win = tk.Toplevel(self.root)
        choice_win.title("Selezione Console")
        
        # Dimensioni fisse per la finestra di dialogo
        dialog_width = 350
        dialog_height = 320
        
        # Ottieni le dimensioni della finestra principale
        self.root.update_idletasks() # Assicura che le dimensioni siano aggiornate
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        
        # Calcola la posizione per centrare la finestra di dialogo
        x = (root_width // 2) - (dialog_width // 2)
        y = (root_height // 2) - (dialog_height // 2)
        
        choice_win.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        choice_win.configure(bg="#1e1e1e")
        choice_win.transient(self.root)
        choice_win.grab_set()
        ttk.Label(choice_win, text=f"Seleziona Sistema:", style="Header.TLabel", font=("Helvetica", 12, "bold")).pack(pady=10)
        for p_key in platforms:
            btn = ttk.Button(choice_win, text=p_key, 
                             command=lambda k=p_key: [choice_win.destroy(), self.run_emulator_logic(k, game_path)],
                             style="Gold.TButton")
            btn.pack(pady=5, fill="x", padx=40)

    def run_emulator_logic(self, platform_key, game_path):
        config = self.config["platforms"][platform_key]
        emu_folder = os.path.join(self.base_dir, config["folder"])
        emu_exe = os.path.join(emu_folder, config["executable"])
        emu_args = config.get("args", [])

        if not os.path.exists(emu_exe):
            messagebox.showerror("Emulatore mancante", 
                                 f"L'emulatore per {platform_key} non è stato trovato.\n\n"
                                 f"Per favore, inserisci l'eseguibile '{config['executable']}' nella cartella:\n{emu_folder}")
        else:
            self.launch_emulator(emu_exe, game_path, emu_args, platform_key)

    def _resolve_ps3_game_path(self, game_path):
        """Risale la gerarchia delle cartelle per trovare la root di un gioco PS3."""
        current_path = os.path.dirname(game_path)
        roms_dir_lower = os.path.normpath(os.path.abspath(self.roms_dir)).lower()
        
        while current_path and current_path.lower().startswith(roms_dir_lower):
            if os.path.isdir(os.path.join(current_path, "PS3_GAME")) or \
               os.path.isdir(os.path.join(current_path, "PKGDIR")):
                return current_path
            
            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:
                break
            current_path = parent_path
        
        return os.path.dirname(game_path)

    def launch_emulator(self, emu_path, game_path, emu_args, platform_key=None):
        self.status_var.set(f"Avvio gioco...")
        try:
            # Normalizza i percorsi per Windows (evita problemi con / e \)
            emu_path = os.path.normpath(emu_path)
            emu_dir = os.path.dirname(emu_path)
            
            # Correzione specifica per xemu/xqemu
            if platform_key == "Xbox" or any(x in emu_path.lower() for x in ["xqemu", "xemu"]):
                # Percorso relativo per evitare bug "Unknown protocol" con i drive C:\
                try:
                    game_path = os.path.relpath(game_path, emu_dir).replace('\\', '/')
                except ValueError:
                    game_path = os.path.abspath(game_path).replace('\\', '/')
                
                # Usiamo -cdrom invece di -dvd. -cdrom è l'alias universale di QEMU
                # per l'unità ottica e risolve l'errore "invalid option" segnalato
                # da alcune build di xemu, evitando il conflitto con l'Hard Disk (index 0).
                flag = "-cdrom"
                if flag not in emu_args and "-dvd" not in emu_args:
                    emu_args = list(emu_args)
                    emu_args.append(flag)
                game_path_to_pass = game_path
            elif platform_key == "PS3":
                ext_lower = game_path.lower()
                if ext_lower.endswith(".pkg"):
                    self.status_var.set("Installazione pacchetto PS3...")
                    game_path_to_pass = game_path
                    emu_args = list(emu_args) + ["--installpkg"]
                elif ext_lower.endswith((".bin", ".elf", ".self")):
                    # Boot diretto del file binario
                    game_path_to_pass = game_path
                elif ext_lower.endswith((".iso", ".cso", ".chd")):
                    game_path_to_pass = game_path
                else:
                    game_path_to_pass = self._resolve_ps3_game_path(game_path)
            elif platform_key == "PS4":
                # Il Qt Launcher usa il core PS4 selezionato nella sua configurazione.
                game_path_to_pass = os.path.abspath(game_path).replace('\\', '/')
                emu_args = [
                    "--emulator", "default",
                    "--game", game_path_to_pass
                ]
                game_path_to_pass = None
            else:
                game_path_to_pass = game_path

            # Costruisce il comando usando i flag specifici configurati per l'emulatore
            cmd = [emu_path] + emu_args
            if game_path_to_pass is not None:
                cmd.append(game_path_to_pass)
            
            subprocess.Popen(
                cmd, 
                cwd=emu_dir
            )
        except Exception as e:
            messagebox.showerror("Errore Avvio", f"Impossibile avviare l'emulatore: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = UniversalEmulator(root)
    root.mainloop()
