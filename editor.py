import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import sys
import time
import numpy as np
import sounddevice as sd
try:
    from PIL import Image, ImageTk
    try:
        # Compatibilità MoviePy v1.x
        from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, ColorClip, ImageClip
    except ImportError:
        # Compatibilità MoviePy v2.x
        from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip, ColorClip, ImageClip
except ImportError as e:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Errore Librerie", 
                         f"Mancano delle librerie necessarie per il Video Editor:\n{e}\n\n"
                         "Esegui il file 'installa_librerie.bat' oppure digita:\n"
                         "pip install moviepy Pillow opencv-python pyautogui numpy sounddevice")
    root.destroy()
    sys.exit()

class RoundedButton(tk.Canvas):
    """Pulsante personalizzato con angoli arrotondati per emulare lo stile PyQt del Media Player."""
    def __init__(self, parent, text="", command=None, image=None, compound='left', 
                 bg="#D4AF37", fg="black", active_bg="#e5c05b", 
                 font=("Segoe UI", 9, "bold"), width=100, height=35, radius=8):
        super().__init__(parent, width=width, height=height, bg=parent['bg'], 
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.bg = bg
        self.active_bg = active_bg
        self.fg = fg
        self.radius = radius
        self.font = font
        self.image = image
        self.text = text
        self.compound = compound
        self.state = tk.NORMAL
        
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: self.draw(self.active_bg) if self.state == tk.NORMAL else None)
        self.bind("<Leave>", lambda e: self.draw(self.bg) if self.state == tk.NORMAL else None)
        
        self.draw(self.bg)

    def _on_press(self, event):
        if self.state == tk.NORMAL:
            self.draw(self.active_bg)

    def _on_release(self, event):
        if self.state == tk.NORMAL:
            self.draw(self.bg)
            if self.command: self.command()

    def config(self, **kwargs):
        if 'state' in kwargs:
            self.state = kwargs['state']
            self.draw(self.bg if self.state == tk.NORMAL else "#d1d1d1")
        if 'text' in kwargs:
            self.text = kwargs['text']
            self.draw(self.bg)

    def draw(self, color):
        self.delete("all")
        w, h, r = int(self['width']), int(self['height']), self.radius
        # Disegno rettangolo arrotondato
        self.create_arc((0, 0, r*2, r*2), start=90, extent=90, fill=color, outline=color)
        self.create_arc((w-r*2, 0, w, r*2), start=0, extent=90, fill=color, outline=color)
        self.create_arc((0, h-r*2, r*2, h), start=180, extent=90, fill=color, outline=color)
        self.create_arc((w-r*2, h-r*2, w, h), start=270, extent=90, fill=color, outline=color)
        self.create_rectangle((r, 0, w-r, h), fill=color, outline=color)
        self.create_rectangle((0, r, w, h-r), fill=color, outline=color)
        
        # Posizionamento testo e icona
        if self.image and self.text:
            self.create_image(w*0.25, h/2, image=self.image)
            self.create_text(w*0.62, h/2, text=self.text, fill=self.fg, font=self.font)
        elif self.image:
            self.create_image(w/2, h/2, image=self.image)
        else:
            self.create_text(w/2, h/2, text=self.text, fill=self.fg, font=self.font)

class VideoEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Editor - Suite Multimediale di Daniele Barile")
        self.root.geometry("1200x800")
        self.root.state('zoomed')
        self.root.configure(bg="#121212")
        self.root.attributes("-alpha", 0.0)

        self.clips_metadata = [] # Lista di dizionari: {'path':, 'start':, 'end':, 'type':}
        self.active_clip = None
        self.is_playing = False
        self.current_time = 0
        self.last_update_time = 0
        self.is_updating_slider = False
        self.timeline_thumbnails = []
        self.preview_dim = (800, 450)
        
        self.playhead_story = None
        self.playhead_spec = None
        self.clip_x_offsets = [] # Memorizza le posizioni X iniziali delle clip nella timeline

        print("DEBUG: Sounddevice devices available:")
        print(sd.query_devices())

        # Variabili per sincronizzazione audio
        self.audio_stream_active = False

        self.icons = {}
        self.load_icons()
        self.setup_ui()
        self.animate_fade_in()

    def animate_fade_in(self):
        alpha = self.root.attributes("-alpha")
        if alpha < 1.0:
            alpha += 0.05
            self.root.attributes("-alpha", alpha)
            self.root.after(20, self.animate_fade_in)

    def load_icons(self):
        icon_names = {
            'Nuovo': 'new.png', 'Apri': 'open.png', 'Salva': 'save.png',
            'Taglia': 'cut.png', 'Copia': 'copy.png', 'Incolla': 'paste.png',
            'Play': 'print.png', 'Clip': 'image.png',
            'Stop': 'cut.png', 'Indietro': 'undo.png', 'Avanti': 'redo.png',
            'Pausa': 'copy.png', 'Effetti': 'find_replace.png', 'Transizioni': 'table.png',
            'Titolo': 'bold.png', 'ZoomIn': 'zoom.png', 'ZoomOut': 'zoom.png'
        }
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_path = os.path.join(script_dir, 'icons')

        for key, filename in icon_names.items():
            path = os.path.join(icons_path, filename)
            # Cerca ricorsivamente come nel WordProcessor per sicurezza
            found_path = None
            if os.path.exists(icons_path):
                for r, d, f in os.walk(icons_path):
                    if filename in f:
                        found_path = os.path.join(r, filename)
                        break
            
            if found_path:
                try:
                    img = Image.open(found_path).resize((20, 20), Image.LANCZOS)
                    self.icons[key] = ImageTk.PhotoImage(img)
                except: self.icons[key] = None
            else:
                self.icons[key] = None

    def setup_ui(self):
        # Menu
        menubar = tk.Menu(self.root)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Nuovo Progetto", image=self.icons.get('Nuovo'), compound='left', command=self.nuovo_progetto)
        file_menu.add_command(label="Apri Progetto...", image=self.icons.get('Apri'), compound='left')
        file_menu.add_command(label="Salva Progetto", image=self.icons.get('Salva'), compound='left')
        file_menu.add_command(label="Salva Progetto con nome...")
        file_menu.add_separator()
        import_menu = tk.Menu(file_menu, tearoff=0)
        import_menu.add_command(label="Video/Audio...", command=self.importa_clip)
        import_menu.add_command(label="Immagini...", command=self.importa_clip)
        file_menu.add_cascade(label="Importa nella raccolta", menu=import_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Esporta Filmato...", command=self.esporta_video)
        file_menu.add_command(label="Esci", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Annulla", image=self.icons.get('Indietro'), compound='left')
        edit_menu.add_command(label="Ripristina", image=self.icons.get('Avanti'), compound='left')
        edit_menu.add_separator()
        edit_menu.add_command(label="Taglia", image=self.icons.get('Taglia'), compound='left')
        edit_menu.add_command(label="Copia", image=self.icons.get('Copia'), compound='left')
        edit_menu.add_command(label="Incolla", image=self.icons.get('Incolla'), compound='left')
        edit_menu.add_command(label="Elimina")
        edit_menu.add_separator()
        edit_menu.add_command(label="Seleziona tutto")
        menubar.add_cascade(label="Modifica", menu=edit_menu)

        # View Menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Timeline")
        view_menu.add_command(label="Storyboard")
        view_menu.add_separator()
        view_menu.add_command(label="Zoom avanti", image=self.icons.get('ZoomIn'), compound='left')
        view_menu.add_command(label="Zoom indietro", image=self.icons.get('ZoomOut'), compound='left')
        menubar.add_cascade(label="Visualizza", menu=view_menu)

        # Tools Menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Effetti video", image=self.icons.get('Effetti'), compound='left', command=self.mostra_effetti)
        tools_menu.add_command(label="Transizioni video", image=self.icons.get('Transizioni'), compound='left', command=self.mostra_transizioni)
        tools_menu.add_command(label="Titoli e riconoscimenti", image=self.icons.get('Titolo'), compound='left', command=self.aggiungi_titoli)
        menubar.add_cascade(label="Strumenti", menu=tools_menu)

        self.root.config(menu=menubar)

        # Toolbar
        toolbar = tk.Frame(self.root, bd=0, bg="#1e1e1e")
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Pulsanti Toolbar
        RoundedButton(toolbar, text=" Importa Media", image=self.icons.get('Clip'), command=self.importa_clip, width=150).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Pulsanti secondari (stile bianco/testo per non appesantire, come in un browser/player moderno)
        RoundedButton(toolbar, text=" Effetti", image=self.icons.get('Effetti'), command=self.mostra_effetti, bg="#ffffff", width=110).pack(side=tk.LEFT, padx=2)
        RoundedButton(toolbar, text=" Transizioni", image=self.icons.get('Transizioni'), command=self.mostra_transizioni, bg="#ffffff", width=130).pack(side=tk.LEFT, padx=2)
        RoundedButton(toolbar, text=" Titoli", image=self.icons.get('Titolo'), command=self.aggiungi_titoli, bg="#ffffff", width=100).pack(side=tk.LEFT, padx=2)
        
        tk.Frame(toolbar, width=1, bg="#333333").pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=8)
        
        RoundedButton(toolbar, text=" Pubblica Filmato", image=self.icons.get('Salva'), command=self.esporta_video, width=160).pack(side=tk.LEFT, padx=5, pady=5)

        self.main_paned = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashwidth=4, bg="#121212", bd=0)
        self.main_paned.pack(expand=True, fill='both')

        # Footer Brand (Inserito prima del PanedWindow per garantire visibilità costante in basso)
        self.footer_label = tk.Label(self.root, text="Powered by Daniele Barile", bg="#121212", fg="#d4af37", font=("Helvetica", 14, "bold"))
        self.footer_label.pack(side=tk.BOTTOM, pady=2)

        # Area Superiore (Libreria e Anteprima)
        self.top_paned = tk.PanedWindow(self.main_paned, orient=tk.HORIZONTAL, bg="#121212", bd=0)
        self.main_paned.add(self.top_paned)

        # Libreria Progetto (Sinistra)
        self.library_frame = tk.Frame(self.top_paned, width=300, bg="#121212")
        self.top_paned.add(self.library_frame)
        tk.Label(self.library_frame, text="RACCOLTA CLIP", bg="#121212", fg="#D4AF37", font=("Segoe UI", 9, "bold")).pack(pady=10)
        
        self.clip_listbox = tk.Listbox(self.library_frame, bd=1, font=("Segoe UI", 10), bg="#ffffff", fg="#1a1a1a", selectbackground="#D4AF37", relief=tk.SOLID)
        self.clip_listbox.bind('<<ListboxSelect>>', self.on_select_clip)
        self.clip_listbox.pack(expand=True, fill='both', padx=5, pady=5)

        # Anteprima (Destra)
        self.preview_frame = tk.Frame(self.top_paned, bg="black")
        self.top_paned.add(self.preview_frame)

        # Controlli Riproduzione (Sotto l'anteprima)
        self.playback_ctrl = tk.Frame(self.preview_frame, bg="#ffffff", pady=2)
        self.playback_ctrl.pack(side=tk.BOTTOM, fill=tk.X)

        # Pulsanti di riproduzione arrotondati
        RoundedButton(self.playback_ctrl, text="⏮", command=self.skip_backward, width=45, radius=10).pack(side=tk.LEFT, padx=2)
        RoundedButton(self.playback_ctrl, text="▶", command=self.play_video, width=45, radius=10).pack(side=tk.LEFT, padx=2)
        RoundedButton(self.playback_ctrl, text="⏸", command=self.pausa_video, width=45, radius=10).pack(side=tk.LEFT, padx=2)
        RoundedButton(self.playback_ctrl, text="⏹", command=self.stop_video, width=45, radius=10).pack(side=tk.LEFT, padx=2)
        RoundedButton(self.playback_ctrl, text="⏭", command=self.skip_forward, width=45, radius=10).pack(side=tk.LEFT, padx=2)

        self.time_slider = tk.Scale(self.playback_ctrl, from_=0, to=100, orient=tk.HORIZONTAL, 
                                    bg="#ffffff", fg="#D4AF37", highlightthickness=0, 
                                    troughcolor="#e5e5e5", showvalue=False, command=self.on_slider_seek, cursor="hand2")
        self.time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        tk.Label(self.playback_ctrl, text=" 🔊", bg="#ffffff", fg="#D4AF37", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(5, 0))
        self.volume_slider = tk.Scale(self.playback_ctrl, from_=0, to=100, orient=tk.HORIZONTAL, 
                                      bg="#ffffff", fg="#D4AF37", highlightthickness=0, 
                                      troughcolor="#e5e5e5", showvalue=False, length=100,
                                      activebackground="#D4AF37", sliderrelief=tk.FLAT)
        self.volume_slider.set(100)
        self.volume_slider.pack(side=tk.LEFT, padx=2)

        self.preview_label = tk.Label(self.preview_frame, text="Anteprima Video", fg="#333333", bg="black", font=("Segoe UI", 12), anchor=tk.CENTER)
        self.preview_label.pack(expand=True)

        self.preview_frame.bind("<Configure>", self.on_resize)

        # Timeline (Basso)
        self.timeline_frame = tk.Frame(self.main_paned, height=100, bg="#f3f3f3", bd=0)
        self.main_paned.add(self.timeline_frame)
        
        timeline_ctrl = tk.Frame(self.timeline_frame, bg="#f3f3f3")
        timeline_ctrl.pack(fill=tk.X)
        tk.Label(timeline_ctrl, text="STORYBOARD & AUDIO SPECTRUM", font=("Segoe UI", 8, "bold"), bg="#f3f3f3", fg="#D4AF37").pack(side=tk.LEFT, padx=10, pady=5)
        RoundedButton(timeline_ctrl, image=self.icons.get('ZoomIn'), bg="#ffffff", width=35, height=25, radius=5).pack(side=tk.RIGHT, padx=2)
        RoundedButton(timeline_ctrl, image=self.icons.get('ZoomOut'), bg="#ffffff", width=35, height=25, radius=5).pack(side=tk.RIGHT, padx=2)

        # Canvas della storyboard (Sopra)
        self.storyboard_canvas = tk.Canvas(self.timeline_frame, bg="#ffffff", height=60, highlightthickness=1, highlightbackground="#d1d1d1")
        self.storyboard_canvas.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 0))
        
        # Canvas dello spettro audio (Sotto)
        self.spectrum_canvas = tk.Canvas(self.timeline_frame, bg="#ffffff", height=40, highlightthickness=1, highlightbackground="#d1d1d1")
        self.spectrum_canvas.pack(side=tk.TOP, fill=tk.X, padx=10, pady=0)
        
        # Binding per il tasto destro (Menu contestuale)
        self.storyboard_canvas.bind("<Button-3>", self.show_timeline_context_menu)
        self.spectrum_canvas.bind("<Button-3>", self.show_timeline_context_menu)

        self.h_scroll = tk.Scrollbar(self.timeline_frame, orient=tk.HORIZONTAL, command=self.sync_scroll)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
        self.storyboard_canvas.config(xscrollcommand=self.h_scroll.set)
        self.spectrum_canvas.config(xscrollcommand=self.h_scroll.set)

        self.timeline_menu = tk.Menu(self.root, tearoff=0)
        self.timeline_menu.add_command(label="Dividi Clip", command=self.dividi_clip)
        self.timeline_menu.add_command(label="Taglia / Elimina", command=self.elimina_selected_clip)

        # Forza le dimensioni delle aree per massimizzare il riquadro video all'apertura
        self.root.update()
        self.top_paned.sash_place(0, 250, 0)    # Fissa la libreria a 250 pixel di larghezza
        self.main_paned.sash_place(0, 0, 550)   # Ridotto per garantire visibilità del footer dorato su tutti i monitor

    def importa_clip(self):
        files = filedialog.askopenfilenames(filetypes=[
            ("Media files", "*.mp4 *.avi *.mov *.mp3 *.wav *.m4a"), 
            ("Immagini", "*.jpg *.png *.jpeg *.bmp")
        ])
        if files:
            for f in files:
                name = os.path.basename(f)
                # Otteniamo la durata iniziale
                try:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ['.mp3', '.wav', '.m4a']: clip = AudioFileClip(f)
                    elif ext in ['.jpg', '.png', '.jpeg', '.bmp']: clip = ImageClip(f, duration=5)
                    else: clip = VideoFileClip(f)
                    duration = clip.duration
                    clip.close()
                except: duration = 5

                self.clips_metadata.append({'path': f, 'start': 0, 'end': duration, 'name': name})
                self.clip_listbox.insert(tk.END, f" 🎬 {name}")
            
            # Seleziona l'ultima aggiunta e mostra anteprima
            self.clip_listbox.selection_clear(0, tk.END)
            self.clip_listbox.selection_set(tk.END)
            self.on_select_clip(None)
            self.update_timeline()

    def on_select_clip(self, event):
        selection = self.clip_listbox.curselection()
        if selection:
            meta = self.clips_metadata[selection[0]]
            path = meta['path']
            self.stop_video()
            
            # Carica il nuovo clip
            if self.active_clip: self.active_clip.close()
            try:
                ext = os.path.splitext(path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                    # Per le immagini carichiamo come clip di MoviePy per uniformità
                    self.active_clip = ImageClip(path, duration=meta['end'] - meta['start'])
                    self.time_slider.config(to=0, state="disabled")
                elif ext in ['.mp3', '.wav', '.m4a']:
                    full_audio = AudioFileClip(path)
                    if hasattr(full_audio, 'subclip'):
                        self.active_clip = full_audio.subclip(meta['start'], meta['end'])
                    else: self.active_clip = full_audio.subclipped(meta['start'], meta['end'])
                    self.time_slider.config(to=self.active_clip.duration, state="normal")
                else:
                    full_video = VideoFileClip(path)
                    if hasattr(full_video, 'subclip'):
                        self.active_clip = full_video.subclip(meta['start'], meta['end'])
                    else: self.active_clip = full_video.subclipped(meta['start'], meta['end'])
                    self.time_slider.config(to=self.active_clip.duration, state="normal")
                
                self.current_time = 0
                self.is_updating_slider = True
                self.time_slider.set(0)
                self.is_updating_slider = False
                self.mostra_frame(0)
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile caricare la clip: {e}")

    def on_resize(self, event):
        # Aggiorna le dimensioni memorizzate per l'anteprima (Best Fit)
        w = self.preview_frame.winfo_width()
        ctrl_h = self.playback_ctrl.winfo_height()
        h = self.preview_frame.winfo_height() - max(ctrl_h, 40)
        if w > 50 and h > 50:
            self.preview_dim = (w, h)
        # Aggiorna l'anteprima solo se c'è un clip attivo e non stiamo già riproducendo
        if self.active_clip and not self.is_playing:
            self.mostra_frame(self.current_time)

    def sync_scroll(self, *args):
        # Sincronizza lo scorrimento di entrambi i canvas
        self.storyboard_canvas.xview(*args)
        self.spectrum_canvas.xview(*args)

    def on_slider_seek(self, value):
        if self.is_updating_slider:
            return
        if self.active_clip and isinstance(self.active_clip, VideoFileClip):
            self.current_time = float(value)
            self.mostra_frame(self.current_time)
            self._update_playhead_position()

    def mostra_frame(self, t, fast=False):
        if not self.active_clip: return
        try:
            # Limitiamo t alla durata della clip attiva
            t = max(0, min(t, self.active_clip.duration - 0.01))

            if isinstance(self.active_clip, VideoFileClip):
                # Se il tempo supera la durata, ferma tutto
                if t >= self.active_clip.duration:
                    self.stop_video()
                    return
                frame = self.active_clip.get_frame(t)
                img = Image.fromarray(frame)
            elif isinstance(self.active_clip, ImageClip):
                img = Image.fromarray(self.active_clip.get_frame(0))
            else: # AudioFileClip
                # Placeholder visivo per i file solo audio
                selection = self.clip_listbox.curselection()
                name = self.clips_metadata[selection[0]]['name'] if selection else "Audio"
                self.preview_label.config(image='', text=f"🎵 AUDIO TRACK\n{name}", fg="#D4AF37")
                return
            
            # Calcola lo spazio disponibile nel contenitore (preview_frame)
            w, h = self.preview_dim

            # Calcolo del rapporto di scala per adattare il video (Best Fit)
            img_w, img_h = img.size
            ratio = min(w / img_w, h / img_h)
            
            new_w = max(int(img_w * ratio), 1)
            new_h = max(int(img_h * ratio), 1)
            
            # Usa NEAREST durante il play per velocità, BILINEAR quando fermo per qualità
            resample_mode = Image.NEAREST if fast else Image.BILINEAR
            img = img.resize((new_w, new_h), resample_mode)

            self.tk_preview = ImageTk.PhotoImage(img)
            # Applichiamo l'immagine assicurandoci che la label la centri correttamente
            self.preview_label.config(image=self.tk_preview, text="", anchor=tk.CENTER)
        except Exception as e:
            print(f"Errore rendering frame: {e}")

    def stream_video(self):
        if self.is_playing and isinstance(self.active_clip, VideoFileClip):
            start_time = time.perf_counter()
            
            # Calcolo del tempo trascorso reale per mantenere il sync
            now = time.perf_counter()
            elapsed = now - self.last_update_time
            self.current_time += elapsed
            self.last_update_time = now 
            
            # Aggiornamento UI e Frame
            self.root.after(0, self._update_slider_ui)
            self.mostra_frame(self.current_time, fast=True)
            
            # Timing adattivo: calcola il ritardo ideale (30 FPS = 33ms)
            proc_duration = (time.perf_counter() - start_time) * 1000
            delay = max(1, int(33 - proc_duration))

            if self.is_playing:
                self.root.after(delay, self.stream_video)

    def _update_slider_ui(self):
        self.is_updating_slider = True
        self.time_slider.set(self.current_time)
        self.is_updating_slider = False
        self._update_playhead_position()

    def _update_playhead_position(self):
        selection = self.clip_listbox.curselection()
        if not selection or not self.clip_x_offsets: return
        
        idx = selection[0]
        if idx < len(self.clip_x_offsets):
            # Calcoliamo la X basata sull'offset della clip e il tempo corrente (scala 70px/sec)
            x = self.clip_x_offsets[idx] + (self.current_time * 70)
            
            if self.playhead_story:
                self.storyboard_canvas.coords(self.playhead_story, x, 0, x, 60)
            if self.playhead_spec:
                self.spectrum_canvas.coords(self.playhead_spec, x, 0, x, 40)
            
            # Scorrimento automatico della timeline
            self.storyboard_canvas.xview_moveto(max(0, x - 200) / self.storyboard_canvas.bbox("all")[2])

    def play_video(self):
        if self.active_clip and not self.is_playing:
            self.is_playing = True
            self.last_update_time = time.perf_counter()
            
            # Determina la sorgente audio (VideoFileClip o AudioFileClip)
            audio_source = None
            if hasattr(self.active_clip, 'audio') and self.active_clip.audio is not None:
                audio_source = self.active_clip.audio
            elif isinstance(self.active_clip, AudioFileClip):
                audio_source = self.active_clip

            # Avvio Riproduzione Audio
            if audio_source:
                try:
                    # Applica il volume impostato nello slider
                    vol_factor = self.volume_slider.get() / 100.0
                    # Estrae l'audio dalla posizione corrente alla fine
                    if hasattr(audio_source, 'subclip'):
                        audio_segment = audio_source.subclip(self.current_time)
                    else: # MoviePy 2.x compatibility
                        audio_segment = audio_source.subclipped(self.current_time)
                        
                    # Converti in array numpy con sampling rate standard
                    audio_data = audio_segment.to_soundarray(fps=44100)
                    
                    if audio_data.size > 0:
                        # Assicura il formato float32 per sounddevice
                        sd.play((audio_data * vol_factor).astype(np.float32), 44100)
                except Exception as e:
                    print(f"Errore riproduzione audio: {e}")

            if isinstance(self.active_clip, VideoFileClip):
                self.stream_video()

    def pausa_video(self):
        self.is_playing = False
        sd.stop()

    def stop_video(self):
        self.is_playing = False
        self.current_time = 0
        sd.stop()
        self.is_updating_slider = True
        self.time_slider.set(0)
        self.is_updating_slider = False
        self.mostra_frame(0)

    def skip_forward(self):
        if self.active_clip and isinstance(self.active_clip, VideoFileClip):
            was_playing = self.is_playing
            if was_playing: self.pausa_video()
            self.current_time = min(self.current_time + 5, self.active_clip.duration)
            self.is_updating_slider = True
            self.time_slider.set(self.current_time)
            self.is_updating_slider = False
            self.mostra_frame(self.current_time)
            if was_playing: self.play_video()

    def skip_backward(self):
        if self.active_clip and isinstance(self.active_clip, VideoFileClip):
            was_playing = self.is_playing
            if was_playing: self.pausa_video()
            self.current_time = max(self.current_time - 5, 0)
            self.is_updating_slider = True
            self.time_slider.set(self.current_time)
            self.is_updating_slider = False
            self.mostra_frame(self.current_time)
            if was_playing: self.play_video()

    def mostra_effetti(self):
        messagebox.showinfo("Effetti", "Seleziona una clip per applicare effetti come: Seppia, Bianco e Nero, Dissolvenza.")

    def mostra_transizioni(self):
        messagebox.showinfo("Transizioni", "Trascina una transizione tra due clip nella timeline.")

    def aggiungi_titoli(self):
        messagebox.showinfo("Titoli", "Inserisci il testo per i titoli di testa o i riconoscimenti finali.")

    def _draw_waveform(self, clip, x_offset, width):
        """Disegna lo spettro audio sulla timeline"""
        if not clip.audio:
            return
        try:
            # Aumentiamo la densità a 40 campioni al secondo per un dettaglio superiore
            fps_val = 40
            audio_data = clip.audio.to_soundarray(fps=fps_val)
            if len(audio_data) > 0:
                # Converti in mono usando il valore massimo tra i canali per catturare i picchi reali
                if len(audio_data.shape) > 1:
                    data = np.max(np.abs(audio_data), axis=1)
                else:
                    data = np.abs(audio_data)
                
                # Normalizzazione dinamica: calcola il picco massimo della clip
                # per far sì che la forma d'onda riempia bene lo spazio verticale
                max_amp = np.max(data)
                if max_amp == 0: max_amp = 1
                
                points = len(data)
                for j in range(points):
                    # Scala il valore per l'altezza del canvas (40px, centro a 20)
                    # Usiamo 18 come moltiplicatore per lasciare un piccolo margine di 2px
                    val = (data[j] / max_amp) * 18
                    lx = x_offset + (j / points) * width
                    # Disegna la riga dello spettro solo se significativa
                    if val > 0.5:
                        self.spectrum_canvas.create_line(lx, 20 - val, lx, 20 + val, fill="#4CAF50", width=1)
        except Exception as e:
            print(f"Errore spettro: {e}")

    def update_timeline(self):
        self.storyboard_canvas.delete("all")
        self.spectrum_canvas.delete("all")
        self.timeline_thumbnails = []
        self.clip_x_offsets = []
        x_offset = 20

        # Disegno Righello Orizzontale (Grigio chiaro)
        # Calcoliamo la durata totale per il righello
        total_duration = sum([(m['end'] - m['start']) for m in self.clips_metadata])
        max_ruler_width = max(2000, int(total_duration * 70) + 1000)
        
        ruler_step = 70 # 70 pixel = 1 secondo
        for i_r in range(0, max_ruler_width // ruler_step + 1):
            r_x = i_r * ruler_step
            self.storyboard_canvas.create_line(r_x + x_offset, 0, r_x + x_offset, 10, fill="#d1d1d1")
            self.spectrum_canvas.create_line(r_x + x_offset, 0, r_x + x_offset, 5, fill="#d1d1d1")
            if i_r % 5 == 0: # Ogni 5 secondi
                self.storyboard_canvas.create_text(r_x + x_offset, 12, text=f"{i_r}s", font=("Segoe UI", 7), fill="#a0a0a0", anchor="n")

        for i, meta in enumerate(self.clips_metadata):
            path = meta['path']
            name = meta['name']
            self.clip_x_offsets.append(x_offset)
            
            try:
                ext = os.path.splitext(path)[1].lower()
                duration = meta['end'] - meta['start']
                clip_width = max(50, int(duration * 70)) # Scala 70px/sec

                if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                    img = Image.open(path)
                    img.thumbnail((100, 50), Image.LANCZOS)
                    tk_img = ImageTk.PhotoImage(img)
                    self.timeline_thumbnails.append(tk_img)
                    self.storyboard_canvas.create_image(x_offset + (clip_width//2), 30, image=tk_img)
                elif ext in ['.mp3', '.wav', '.m4a']:
                    full_a = AudioFileClip(path)
                    temp_clip = full_a.subclip(meta['start'], meta['end']) if hasattr(full_a, 'subclip') else full_a.subclipped(meta['start'], meta['end'])
                    # Disegna un blocco colorato nello storyboard per l'audio
                    self.storyboard_canvas.create_rectangle(x_offset, 5, x_offset + clip_width, 55, fill="#f0f0f0", outline="#d1d1d1")
                    self._draw_waveform(temp_clip, x_offset, clip_width)
                    temp_clip.close()
                else:
                    full_v = VideoFileClip(path)
                    temp_clip = full_v.subclip(meta['start'], meta['end']) if hasattr(full_v, 'subclip') else full_v.subclipped(meta['start'], meta['end'])
                    num_frames = max(1, int(duration))
                    frame_w = 70 # Larghezza fissa per ogni fotogramma al secondo
                    
                    for idx in range(num_frames):
                        t = max(0, min(idx, duration - 0.1))
                        frame = temp_clip.get_frame(t)
                        img = Image.fromarray(frame)
                        img = img.resize((frame_w, 50), Image.LANCZOS)
                        tk_img = ImageTk.PhotoImage(img)
                        self.timeline_thumbnails.append(tk_img)
                        self.storyboard_canvas.create_image(x_offset + (frame_w // 2) + (idx * frame_w), 30, image=tk_img)
                    
                    self._draw_waveform(temp_clip, x_offset, clip_width)
                    temp_clip.close()

                # Bordi Clip (Colore Gold per coerenza)
                self.storyboard_canvas.create_rectangle(x_offset, 5, x_offset + clip_width, 55, outline="#D4AF37", width=2)
                self.spectrum_canvas.create_rectangle(x_offset, 2, x_offset + clip_width, 38, outline="#4CAF50", width=1)
                self.storyboard_canvas.create_text(x_offset + 5, 48, text=name[:15], font=("Segoe UI", 7, "bold"), fill="#1a1a1a", anchor="w")
                
            except Exception as e:
                print(f"Errore rendering storyboard: {e}")
                clip_width = 100
                self.storyboard_canvas.create_rectangle(x_offset, 5, x_offset + clip_width, 55, fill="#f9f9f9", outline="#d1d1d1")
            
            x_offset += clip_width + 10
        
        # Disegno Testina (Playhead) Rossa iniziale
        self.playhead_story = self.storyboard_canvas.create_line(20, 0, 20, 60, fill="red", width=2, tags="playhead")
        self.playhead_spec = self.spectrum_canvas.create_line(20, 0, 20, 40, fill="red", width=2, tags="playhead")

        # Aggiorniamo la regione di scorrimento per gestire molte clip
        self.storyboard_canvas.config(scrollregion=(0, 0, x_offset, 60))
        self.spectrum_canvas.config(scrollregion=(0, 0, x_offset, 40))

    def show_timeline_context_menu(self, event):
        # Seleziona automaticamente la clip sotto il cursore
        x = self.storyboard_canvas.canvasx(event.x)
        for i, offset in enumerate(self.clip_x_offsets):
            # Approssimazione larghezza (molto semplificata per la selezione)
            if offset <= x <= offset + 500: 
                self.clip_listbox.selection_clear(0, tk.END)
                self.clip_listbox.selection_set(i)
                self.on_select_clip(None)
                break
        self.timeline_menu.post(event.x_root, event.y_root)

    def dividi_clip(self):
        selection = self.clip_listbox.curselection()
        if not selection or self.current_time <= 0: return
        
        idx = selection[0]
        meta = self.clips_metadata[idx]
        
        # Creiamo due nuovi metadati basati sul punto di split
        split_point = meta['start'] + self.current_time
        
        meta2 = meta.copy()
        meta['end'] = split_point
        meta2['start'] = split_point
        
        self.clips_metadata.insert(idx + 1, meta2)
        self.refresh_listbox()
        self.update_timeline()
        messagebox.showinfo("Editor", "Clip divisa correttamente.")

    def elimina_selected_clip(self):
        selection = self.clip_listbox.curselection()
        if not selection: return
        self.clips_metadata.pop(selection[0])
        self.refresh_listbox()
        self.update_timeline()

    def refresh_listbox(self):
        self.clip_listbox.delete(0, tk.END)
        for meta in self.clips_metadata:
            self.clip_listbox.insert(tk.END, f" 🎬 {meta['name']}")

    def nuovo_progetto(self):
        if messagebox.askyesno("Nuovo", "Iniziare un nuovo progetto?"):
            self.clips_metadata = []
            self.clip_listbox.delete(0, tk.END)
            self.update_timeline()

    def esporta_video(self):
        if not self.clips_metadata:
            messagebox.showwarning("Esporta", "Aggiungi almeno una clip alla timeline.")
            return
        
        save_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 Video", "*.mp4")])
        if save_path:
            try:
                clips = []
                for meta in self.clips_metadata:
                    p = meta['path']
                    start, end = meta['start'], meta['end']
                    ext = os.path.splitext(p)[1].lower()
                    
                    if ext in ['.mp3', '.wav', '.m4a']:
                        # Converti l'audio in un video nero per permettere la concatenazione
                        full_a = AudioFileClip(p)
                        a = full_a.subclip(start, end) if hasattr(full_a, 'subclip') else full_a.subclipped(start, end)
                        black_clip = ColorClip(size=(1280, 720), color=(0,0,0), duration=end-start)
                        if hasattr(black_clip, 'with_audio'):
                            clips.append(black_clip.with_audio(a))
                        else:
                            clips.append(black_clip.set_audio(a))
                    elif ext in ['.jpg', '.png', '.jpeg', '.bmp']:
                        img_c = ImageClip(p)
                        dur = end - start
                        clips.append(img_c.set_duration(dur) if hasattr(img_c, 'set_duration') else img_c.with_duration(dur))
                    else:
                        full_v = VideoFileClip(p)
                        clips.append(full_v.subclip(start, end) if hasattr(full_v, 'subclip') else full_v.subclipped(start, end))

                # Concatenazione clip
                if hasattr(concatenate_videoclips(clips[:1]), 'method'): # Check v2
                    final_video = concatenate_videoclips(clips, method="compose")
                else:
                    final_video = concatenate_videoclips(clips, method="compose")
                
                # Applica la regolazione del volume globale
                vol_factor = self.volume_slider.get() / 100.0
                if vol_factor != 1.0 and final_video.audio is not None:
                    if hasattr(final_video, 'volumex'):
                        final_video = final_video.volumex(vol_factor)
                    elif hasattr(final_video, 'multiply_volume'):
                        final_video = final_video.multiply_volume(vol_factor)
                    else:
                        # MoviePy v2.x effects style
                        from moviepy.video.fx.all import volumex
                        final_video = final_video.fx(volumex, vol_factor)
                
                messagebox.showinfo("Esportazione", "L'esportazione sta iniziando. Il programma potrebbe sembrare bloccato per alcuni secondi...")
                
                final_video.write_videofile(save_path, 
                                            codec="libx264", 
                                            audio_codec="aac", 
                                            remove_temp=True,
                                            ffmpeg_params=["-pix_fmt", "yuv420p"],
                                            fps=24)
                
                messagebox.showinfo("Successo", f"Video esportato in:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore durante l'esportazione:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoEditor(root)
    root.mainloop()