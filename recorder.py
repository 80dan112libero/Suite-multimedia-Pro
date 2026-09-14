import tkinter as tk
from tkinter import messagebox, filedialog, ttk, font as tkfont
import cv2
import numpy as np
import pyautogui
import sounddevice as sd
import soundfile as sf
import threading
import time
import os
import json
import sys
from PIL import Image, ImageTk

# Definizione RoundedButton spostata all'esterno per disponibilità globale
class RoundedButton(tk.Canvas):
    """Pulsante personalizzato con angoli arrotondati."""
    def __init__(self, parent, text="", command=None, image=None, compound='left', 
                 bg="#D4AF37", fg="black", active_bg="#FFD700", 
                 font=("Segoe UI", 9, "bold"), width=150, height=35, radius=8,
                 padx_btn=0, pady_btn=0, state=tk.NORMAL):
        self.f_obj = tkfont.Font(font=font)
        text_width = self.f_obj.measure(text) if text else 0
        img_width = image.width() if image else 0
        
        if compound in ['left', 'right'] and image and text:
            calculated_width = text_width + img_width + 20 
        else:
            calculated_width = max(text_width, img_width)
        
        canvas_width = calculated_width + 2 * padx_btn + 2 * radius
        canvas_height = self.f_obj.metrics('linespace') + 2 * pady_btn + 2 * radius

        super().__init__(parent, width=canvas_width, height=canvas_height, bg=parent['bg'], 
                         highlightthickness=0, bd=0, cursor="hand2" if state == tk.NORMAL else "arrow")
        self.command = command
        self.bg = bg
        self.active_bg = active_bg
        self.fg = fg
        self.radius = radius
        self.font = font
        self.image = image
        self.text = text
        self.compound = compound
        self.state = state
        self.padx_btn = padx_btn
        self.pady_btn = pady_btn
        
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: self.draw(self.active_bg) if self.state == tk.NORMAL else None)
        self.bind("<Leave>", lambda e: self.draw(self.bg) if self.state == tk.NORMAL else None)
        
        self.draw(self.bg)

    def _on_press(self, event):
        if self.state == tk.NORMAL: self.draw(self.active_bg)
    def _on_release(self, event):
        if self.state == tk.NORMAL:
            self.draw(self.bg)
            if self.command: self.command()
    def config(self, **kwargs):
        if 'state' in kwargs: self.state = kwargs['state']; self.draw(self.bg if self.state == tk.NORMAL else "#d1d1d1")
        if 'text' in kwargs: self.text = kwargs['text']; self.draw(self.bg)
        if 'image' in kwargs: self.image = kwargs['image']; self.draw(self.bg)
        if 'command' in kwargs: self.command = kwargs['command']

    def draw(self, color):
        self.delete("all")
        w, h, r = int(self['width']), int(self['height']), self.radius
        self.create_arc((0, 0, r*2, r*2), start=90, extent=90, fill=color, outline=color)
        self.create_arc((w-r*2, 0, w, r*2), start=0, extent=90, fill=color, outline=color)
        self.create_arc((0, h-r*2, r*2, h), start=180, extent=90, fill=color, outline=color)
        self.create_arc((w-r*2, h-r*2, w, h), start=270, extent=90, fill=color, outline=color)
        self.create_rectangle((r, 0, w-r, h), fill=color, outline=color)
        self.create_rectangle((0, r, w, h-r), fill=color, outline=color)
        if self.image and self.text:
            tw = self.f_obj.measure(self.text)
            iw = self.image.width()
            total_w = tw + iw + 10
            ix = (w - total_w) / 2 + iw / 2
            tx = ix + iw / 2 + 10 + tw / 2
            self.create_image(ix, h/2, image=self.image)
            self.create_text(tx, h/2, text=self.text, fill=self.fg, font=self.font)
        elif self.image: self.create_image(w/2, h/2, image=self.image)
        else: self.create_text(w/2, h/2, text=self.text, fill=self.fg, font=self.font)

try:
    from moviepy.editor import VideoFileClip, AudioFileClip
except ImportError:
    from moviepy import VideoFileClip, AudioFileClip

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recorder_settings.json')

class ProfessionalRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("Recorder Pro - Suite Multimediale")
        self.root.geometry("1000x850") # Aumentato leggermente per accomodare meglio l'UI
        self.root.state('zoomed')
        self.root.configure(bg="#1a1a1a")

        # Variabili di stato
        self.is_recording = False
        self.start_time = 0
        self.video_frames = []
        self.mic_audio = []
        self.sys_audio = []
        self.fps = 12.0  # Ottimizzato per Python
        self.current_preview_frame = None # Frame corrente per l'anteprima
        self.preview_photo = None # PhotoImage per Tkinter
        self.sample_rate = 44100
        
        # Livelli Audio per VU Meter
        self.mic_level = 0
        self.sys_level = 0

        # Inizializzazione flussi e cattura
        self.webcam_cap = None
        self.mic_stream = None
        self.sys_stream = None
        self.video_capture_thread_running = False
        self.save_thread = None

        # Device Audio
        self.input_devices = self.get_audio_devices() # Deve essere chiamato prima di load_settings
        
        self.preview_update_id = None # ID per il loop di aggiornamento dell'anteprima
        self.icons = {}
        self.load_icons()
        self.setup_ui()
        self.load_settings() # Carica le impostazioni dopo aver inizializzato l'UI
        
        # Avvia preview e monitoraggio audio all'apertura
        self.start_continuous_preview_and_audio_monitoring()
        self.update_vu_meters() # Inizia il loop di rendering dei VU meters

    def get_audio_devices(self):
        devices = sd.query_devices()
        input_devs = []
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                input_devs.append(f"{i}: {d['name']}")
        return input_devs

    def load_icons(self):
        # Caricamento icone simulate
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_path = os.path.join(script_dir, 'icons')
        icon_map = {'Rec': 'print.png', 'Stop': 'delete.png', 'Settings': 'table.png'}
        
        for key, name in icon_map.items():
            path = os.path.join(icons_path, name)
            # Cerca ricorsivamente come nel WordProcessor per sicurezza
            found_path = None
            if os.path.exists(icons_path):
                for r, d, f in os.walk(icons_path):
                    if name in f:
                        found_path = os.path.join(r, name)
                        break
            
            self.icons[key] = None # Default
            if found_path:
                try:
                    img = Image.open(found_path).resize((20, 20), Image.LANCZOS)
                    self.icons[key] = ImageTk.PhotoImage(img)
                except Exception:
                    pass

    
    def setup_ui(self):
        # Stile UI
        # Modificato per un tema chiaro Windows 11
        style = ttk.Style()
        style.theme_use('vista') # O 'alt', 'default'
        style.configure("TProgressbar", thickness=20, background="#D4AF37", troughcolor="#e0e0e0")

        # Header
        header = tk.Frame(self.root, bg="#ffffff", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="RECORDER PRO - CORE ENGINE", fg="#0078d4", bg="#ffffff", font=("Segoe UI", 12, "bold")).pack(pady=10)

        main_layout = tk.Frame(self.root, bg="#f0f0f0", padx=20, pady=20)
        main_layout.pack(expand=True, fill='both')

        # Area Anteprima (Simulata)
        self.preview_canvas = tk.Canvas(main_layout, bg="#e0e0e0", height=350, highlightthickness=1, highlightbackground="#d1d1d1")
        self.preview_canvas.pack(fill=tk.X, pady=10)
        # Modificato per visualizzare l'immagine di anteprima
        self.preview_label = tk.Label(self.preview_canvas, bg="#e0e0e0", text="PRONTO ALL'ACQUISIZIONE", fg="#5d5d5d", font=("Segoe UI", 14))
        self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Controlli Sorgenti Video
        video_frame = tk.LabelFrame(main_layout, text="Sorgenti Video", bg="#f0f0f0", fg="#1a1a1a", padx=10, pady=10)
        video_frame.pack(fill=tk.X, pady=5)

        self.video_mode = tk.StringVar(value="screen_webcam")
        tk.Radiobutton(video_frame, text="Solo Schermo", variable=self.video_mode, value="screen", bg="#f0f0f0", fg="#1a1a1a", selectcolor="#d1d1d1").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(video_frame, text="Solo Webcam", variable=self.video_mode, value="webcam", bg="#f0f0f0", fg="#1a1a1a", selectcolor="#d1d1d1").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(video_frame, text="Schermo + Webcam (PiP)", variable=self.video_mode, value="screen_webcam", bg="#f0f0f0", fg="#1a1a1a", selectcolor="#d1d1d1").pack(side=tk.LEFT, padx=10)

        # Mixer Audio e VU Meters
        mixer_frame = tk.LabelFrame(main_layout, text="Mixer Audio", bg="#f0f0f0", fg="#1a1a1a", padx=10, pady=10)
        mixer_frame.pack(fill=tk.X, pady=5)

        # Microfono
        mic_box = tk.Frame(mixer_frame, bg="#f0f0f0")
        mic_box.pack(fill=tk.X, pady=2)
        self.use_mic = tk.BooleanVar(value=True)
        tk.Checkbutton(mic_box, text="Microfono:", variable=self.use_mic, bg="#f0f0f0", fg="#1a1a1a", selectcolor="#d1d1d1").pack(side=tk.LEFT)
        self.mic_combo = ttk.Combobox(mic_box, values=self.input_devices, width=40)
        if self.input_devices: self.mic_combo.current(0)
        self.mic_combo.pack(side=tk.LEFT, padx=10)
        
        self.mic_vu = tk.Canvas(mic_box, width=200, height=15, bg="#d1d1d1", highlightthickness=0)
        self.mic_vu.pack(side=tk.RIGHT, padx=5)

        # Audio Sistema (Loopback)
        sys_box = tk.Frame(mixer_frame, bg="#f0f0f0")
        sys_box.pack(fill=tk.X, pady=2)
        self.use_sys = tk.BooleanVar(value=False)
        tk.Checkbutton(sys_box, text="Audio Sistema:", variable=self.use_sys, bg="#f0f0f0", fg="#1a1a1a", selectcolor="#d1d1d1").pack(side=tk.LEFT)
        self.sys_combo = ttk.Combobox(sys_box, values=self.input_devices, width=40)
        if self.input_devices:
            self.sys_combo.current(0) # Seleziona il primo dispositivo di default
        self.sys_combo.pack(side=tk.LEFT, padx=10)
        
        self.sys_vu = tk.Canvas(sys_box, width=200, height=15, bg="#d1d1d1", highlightthickness=0)
        self.sys_vu.pack(side=tk.RIGHT, padx=5)

        # Barra di Progresso Elaborazione
        self.progress_frame = tk.Frame(main_layout, bg="#f0f0f0")
        self.progress_frame.pack(fill=tk.X, pady=10)
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate', style="TProgressbar")
        self.lbl_status = tk.Label(self.progress_frame, text="Sistema Pronto", bg="#f0f0f0", fg="#0078d4")
        
        # Pulsanti Azione
        btn_frame = tk.Frame(main_layout, bg="#f0f0f0")
        btn_frame.pack(pady=20)

        self.btn_rec = RoundedButton(btn_frame, text=" AVVIA REGISTRAZIONE", image=self.icons.get('Rec'), compound="left",
                                 bg="#0078d4", fg="white", font=("Segoe UI", 12, "bold"), padx_btn=30, pady_btn=15, command=self.start_recording)
        self.btn_rec.pack(side=tk.LEFT, padx=10)

        self.btn_stop = RoundedButton(btn_frame, text=" STOP", image=self.icons.get('Stop'), compound="left",
                                  bg="#d1d1d1", fg="#1a1a1a", font=("Segoe UI", 12, "bold"), padx_btn=30, pady_btn=15, state=tk.DISABLED, command=self.stop_recording)
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        self.lbl_timer = tk.Label(main_layout, text="00:00:00", font=("Consolas", 20), bg="#f0f0f0", fg="#1a1a1a")
        self.lbl_timer.pack()

        # Footer Brand
        self.footer_label = tk.Label(self.root, text="Powered by Daniele Barile", bg="#f0f0f0", fg="#d4af37", font=("Helvetica", 14, "bold"))
        self.footer_label.pack(side=tk.BOTTOM, pady=2)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Gestisce la chiusura della finestra

    def start_continuous_preview_and_audio_monitoring(self):
        # Avvia il thread di cattura video per la preview
        self.video_capture_thread_running = True
        threading.Thread(target=self._video_capture_loop, daemon=True).start()
        
        # Avvia il loop di rendering dell'anteprima (Tkinter after loop)
        self.update_preview_display()

        # Avvia i flussi audio per il monitoraggio (VU meters)
        self._start_audio_monitoring_streams()

    def update_vu_meters(self):
        # Disegna il VU meter del microfono
        self.mic_vu.delete("all")
        if self.mic_level > 0.001:
            width = int(self.mic_level * 200)
            color = "#00ff00" if width < 150 else "#ffff00" if width < 180 else "#ff0000"
            self.mic_vu.create_rectangle(0, 0, width, 15, fill=color, outline="")
        
        # Disegna il VU meter del sistema
        self.sys_vu.delete("all")
        if self.sys_level > 0.001:
            width = int(self.sys_level * 200)
            color = "#00ff00" if width < 150 else "#ffff00" if width < 180 else "#ff0000"
            self.sys_vu.create_rectangle(0, 0, width, 15, fill=color, outline="")

        self.root.after(50, self.update_vu_meters)

    def start_recording(self):
        self.is_recording = True
        self.video_frames = []
        self.mic_audio = []
        self.sys_audio = []
        self.start_time = time.time()
        
        self.btn_rec.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.lbl_status.config(text="Registrazione in corso...")
        self.lbl_status.pack()
        
        self.update_timer()
        # Nota: L'anteprima e gli stream audio sono già attivi dal monitoraggio continuo

    def update_preview_display(self):
        if self.current_preview_frame is not None:
            try:
                # Forza l'aggiornamento dei calcoli del layout per ottenere dimensioni reali
                self.root.update_idletasks()
                c_w = self.preview_canvas.winfo_width()
                c_h = self.preview_canvas.winfo_height()
                
                # Se la canvas non è ancora renderizzata, usiamo i valori di default
                if c_w < 10: c_w = 800
                if c_h < 10: c_h = 350

                frame = self.current_preview_frame.copy()
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                img_w, img_h = img.size
                aspect = img_w / img_h

                # Calcolo proporzioni (Best Fit)
                if c_w / c_h > aspect:
                    new_h = c_h
                    new_w = int(new_h * aspect)
                else:
                    new_w = c_w
                    new_h = int(new_w / aspect)

                img = img.resize((max(1, new_w), max(1, new_h)), Image.LANCZOS)
                self.preview_photo = ImageTk.PhotoImage(image=img)
                self.preview_label.config(image=self.preview_photo)
            except Exception as e:
                print(f"Error updating preview: {e}")
        else:
            self.preview_label.config(image='', text="PRONTO ALL'ACQUISIZIONE", fg="#5d5d5d", font=("Segoe UI", 14))
        
        self.preview_update_id = self.root.after(30, self.update_preview_display) # Aggiorna ~30 FPS

    def update_timer(self):
        if self.is_recording:
            elapsed = int(time.time() - self.start_time)
            self.lbl_timer.config(text=time.strftime('%H:%M:%S', time.gmtime(elapsed)))
            self.root.after(1000, self.update_timer)
    
    def _start_audio_monitoring_streams(self):
        self._stop_audio_monitoring_streams() # Stop any existing streams first

        # Microfono
        if self.use_mic.get() and self.mic_combo.get():
            try:
                mic_dev_id = int(self.mic_combo.get().split(":")[0])
                self.mic_stream = sd.InputStream(device=mic_dev_id, channels=1, samplerate=self.sample_rate, callback=self._mic_audio_callback)
                self.mic_stream.start()
            except Exception as e:
                print(f"Errore avvio stream microfono: {e}")
                self.mic_stream = None

        # Audio Sistema
        if self.use_sys.get() and self.sys_combo.get():
            try:
                sys_dev_id = int(self.sys_combo.get().split(":")[0])
                self.sys_stream = sd.InputStream(device=sys_dev_id, channels=1, samplerate=self.sample_rate, callback=self._sys_audio_callback)
                self.sys_stream.start()
            except Exception as e:
                print(f"Errore avvio stream audio sistema: {e}")
                self.sys_stream = None

    def _stop_audio_monitoring_streams(self):
        try:
            if self.mic_stream:
                self.mic_stream.stop()
                self.mic_stream.close()
        except:
            pass
        finally:
            self.mic_stream = None

        try:
            if self.sys_stream:
                self.sys_stream.stop()
                self.sys_stream.close()
        except:
            pass
        finally:
            self.sys_stream = None

    def _video_capture_loop(self):
        # Gestisce l'inizializzazione e il rilascio della webcam dinamicamente
        
        while self.video_capture_thread_running:
            loop_start = time.time()
            
            mode = self.video_mode.get() # Ottieni il modo corrente ad ogni iterazione
            
            # Gestione del ciclo di vita della webcam
            webcam_needed_now = (mode in ["webcam", "screen_webcam"])

            if webcam_needed_now and self.webcam_cap is None:
                self.webcam_cap = cv2.VideoCapture(0)
                if not self.webcam_cap.isOpened():
                    print("Errore: Impossibile aprire la webcam. La preview della webcam non sarà disponibile.")
                    self.webcam_cap = None
            elif not webcam_needed_now and self.webcam_cap is not None:
                self.webcam_cap.release()
                self.webcam_cap = None

            if mode == "screen":
                img = pyautogui.screenshot()
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            elif mode == "webcam": # Solo webcam
                if self.webcam_cap and self.webcam_cap.isOpened():
                    ret, web_frame = self.webcam_cap.read()
                    if ret: frame = web_frame
                else:
                    # Se la webcam non è disponibile, mostra un frame nero o un messaggio
                    frame = np.zeros((720, 1280, 3), dtype=np.uint8) # Default black frame
                    cv2.putText(frame, "Webcam non disponibile", (200, 360), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

            elif mode == "screen_webcam": # Schermo + webcam
                img = pyautogui.screenshot()
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                
                if self.webcam_cap and self.webcam_cap.isOpened():
                    ret, web_frame = self.webcam_cap.read()
                    if ret:
                        wh, ww = frame.shape[:2]
                        small_web = cv2.resize(web_frame, (ww//4, wh//4))
                        sh, sw = small_web.shape[:2]
                        # Assicurati che l'overlay non vada fuori dai bordi
                        y1, y2 = wh-sh-20, wh-20
                        x1, x2 = ww-sw-20, ww-20
                        if y1 >= 0 and x1 >= 0 and y2 <= wh and x2 <= ww: # Controlla che le coordinate siano valide
                            frame[y1:y2, x1:x2] = small_web
                        else:
                            cv2.putText(frame, "Webcam overlay fuori limiti", (frame.shape[1] - 400, frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                else:
                    # Se la webcam non è disponibile, aggiungi un messaggio sul frame dello schermo
                    cv2.putText(frame, "Webcam non disponibile", (frame.shape[1] - 400, frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

            if frame is not None:
                self.current_preview_frame = frame.copy() # Aggiorna il frame per l'anteprima
                if self.is_recording:
                    self.video_frames.append(frame) # Aggiungi frame alla lista per il salvataggio
            
            # Controllo FPS
            elapsed = time.time() - loop_start
            wait = max(0, (1.0/self.fps) - elapsed)
            time.sleep(wait)

        if self.webcam_cap: # Rilascia la webcam quando il thread si ferma
            self.webcam_cap.release()
            self.webcam_cap = None

    def _mic_audio_callback(self, indata, frames, time_info, status):
        if status: print(status)
        level = np.linalg.norm(indata) * 10
        self.mic_level = min(1.0, level)
        if self.is_recording:
            self.mic_audio.append(indata.copy())

    def _sys_audio_callback(self, indata, frames, time_info, status):
        if status: print(status)
        level = np.linalg.norm(indata) * 10
        self.sys_level = min(1.0, level)
        if self.is_recording:
            self.sys_audio.append(indata.copy())

    def stop_recording(self):
        self.is_recording = False
        self.btn_stop.config(state=tk.DISABLED)
        
        # Ferma il loop di aggiornamento dell'anteprima
        # L'anteprima continua a funzionare per mostrare il live feed

        # Reset VU meters
        self.mic_level = 0
        self.sys_level = 0
        
        # Salvataggio asincrono con progresso
        self.save_thread = threading.Thread(target=self.process_and_save, daemon=False)
        self.save_thread.start()

    def process_and_save(self):
        output_file = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("Video MP4", "*.mp4")])
        if not output_file:
            self.reset_ui()
            return

        try:
            self.progress_bar.pack(fill=tk.X, pady=5)
            self.update_status(10, "Generazione file video temporaneo...")
            
            # 1. Scrittura Video raw
            temp_v = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_video.avi")
            video_recorded = False
            if self.video_frames:
                try:
                    h, w = self.video_frames[0].shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    out = cv2.VideoWriter(temp_v, fourcc, self.fps, (w, h))
                    
                    total_f = len(self.video_frames)
                    for i, f in enumerate(self.video_frames):
                        out.write(f)
                        if i % 10 == 0:
                            self.update_status(10 + int((i/total_f)*30), f"Scrittura frame {i}/{total_f}")
                    out.release()
                    video_recorded = True
                except Exception as ve:
                    messagebox.showerror("Errore Video", f"Impossibile scrivere il video temporaneo: {ve}")
                    self.reset_ui()
                    return
            else:
                messagebox.showwarning("Registrazione Vuota", "Nessun frame video catturato. Salvataggio annullato.")
                self.reset_ui()
                return

            # 2. Scrittura Audio raw
            self.update_status(50, "Elaborazione flussi audio...")
            temp_a = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_audio_final.wav")
            
            # Rimuove file residui se esistono
            if os.path.exists(temp_a): os.remove(temp_a)
            
            audio_to_save = None
            audio_file_created = False
            
            # Processa e mixa l'audio SOLO se ci sono dati audio
            if self.mic_audio or self.sys_audio:
                try:
                    mic_data = np.concatenate(self.mic_audio, axis=0).astype(np.float32) if self.mic_audio else None
                    sys_data = np.concatenate(self.sys_audio, axis=0).astype(np.float32) if self.sys_audio else None

                    if mic_data is not None and sys_data is not None:
                        max_len = max(len(mic_data), len(sys_data))
                        mic_padded = np.pad(mic_data, ((0, max_len - len(mic_data)), (0, 0)))
                        sys_padded = np.pad(sys_data, ((0, max_len - len(sys_data)), (0, 0)))
                        audio_to_save = (mic_padded + sys_padded) / 2.0
                    elif mic_data is not None:
                        audio_to_save = mic_data
                    elif sys_data is not None:
                        audio_to_save = sys_data

                    if audio_to_save is not None and len(audio_to_save) > 0:
                        sf.write(temp_a, audio_to_save, self.sample_rate, subtype='PCM_16')
                        audio_file_created = True
                except Exception as ae:
                    messagebox.showerror("Errore Audio", f"Impossibile scrivere l'audio temporaneo: {ae}")
                    # Continua il salvataggio del solo video se l'audio fallisce
                    audio_file_created = False
            
            # 3. Muxing finale con MoviePy
            self.update_status(70, "Mixaggio Audio/Video finale (Muxing)...")
            video_clip = VideoFileClip(temp_v)
            
            if audio_file_created and os.path.exists(temp_a):
                audio_clip = AudioFileClip(temp_a)
                # Sincronizzazione durata
                if hasattr(audio_clip, 'with_duration'):
                    final_audio = audio_clip.with_duration(video_clip.duration)
                else:
                    final_audio = audio_clip.set_duration(video_clip.duration)
                
                if hasattr(video_clip, 'with_audio'):
                    final_clip = video_clip.with_audio(final_audio)
                else:
                    final_clip = video_clip.set_audio(final_audio)

                self.update_status(85, "Rendering MP4...")
                
                # Fix Broken Pipe (Errno 32): usiamo un file audio temporaneo fisico 
                # ed evitiamo la comunicazione tramite pipe per il flusso audio.
                temp_rendering_audio = os.path.join(os.path.dirname(temp_a), "temp_render.m4a")
                
                final_clip.write_videofile(output_file, 
                                          codec="libx264", 
                                          audio_codec="aac", 
                                          fps=self.fps, 
                                          logger=None,
                                          temp_audiofile=temp_rendering_audio,
                                          remove_temp=True,
                                          preset="ultrafast")
                audio_clip.close()
            else:
                # Se non c'è audio o l'audio non è stato creato, salva solo il video
                self.update_status(85, "Rendering MP4 (solo video)...")
                video_clip.write_videofile(output_file, codec="libx264", fps=self.fps, logger=None, preset="ultrafast")
            
            video_clip.close()
            
            # Pulizia
            if os.path.exists(temp_v): os.remove(temp_v)
            if os.path.exists(temp_a): os.remove(temp_a)
            
            self.update_status(100, "Completato!")
            messagebox.showinfo("Successo", f"Registrazione salvata in:\n{output_file}")

        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante il salvataggio: {e}")
        
        self.reset_ui()

    def update_status(self, progress, text):
        self.root.after(0, lambda: self.progress_bar.config(value=progress))
        self.root.after(0, lambda: self.lbl_status.config(text=text))

    def reset_ui(self):
        self.btn_rec.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_timer.config(text="00:00:00")
        # Non resettare current_preview_frame o il loop di update_preview_display
        # perché devono continuare per la preview.
        self.progress_bar.pack_forget()
        self.lbl_status.config(text="Sistema Pronto")
        self.video_frames = []
        self.mic_audio = []
        self.sys_audio = []
        self.save_thread = None

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # Applica le impostazioni video
                self.video_mode.set(settings.get('video_mode', 'screen_webcam'))

                # Applica le impostazioni microfono
                self.use_mic.set(settings.get('use_mic', True))
                mic_dev_id = settings.get('mic_device_id')
                if mic_dev_id is not None:
                    for i, dev_str in enumerate(self.input_devices):
                        if int(dev_str.split(":")[0]) == mic_dev_id:
                            self.mic_combo.current(i)
                            break

                # Applica le impostazioni audio di sistema
                self.use_sys.set(settings.get('use_sys', False))
                sys_dev_id = settings.get('sys_device_id')
                if sys_dev_id is not None:
                    for i, dev_str in enumerate(self.input_devices):
                        if int(dev_str.split(":")[0]) == sys_dev_id:
                            self.sys_combo.current(i)
                            break

            except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                messagebox.showwarning("Caricamento Impostazioni", f"Impossibile caricare le impostazioni: {e}. Verranno usate le impostazioni di default.")
        else:
            # Se il file non esiste, imposta i valori di default per le combobox
            if self.input_devices:
                self.mic_combo.current(0)
                self.sys_combo.current(0)

    def save_settings(self):
        settings = {
            'video_mode': self.video_mode.get(),
            'use_mic': self.use_mic.get(),
            'use_sys': self.use_sys.get(),
        }

        # Salva l'ID del dispositivo audio selezionato
        try:
            mic_selected_str = self.mic_combo.get()
            if mic_selected_str:
                settings['mic_device_id'] = int(mic_selected_str.split(":")[0])
        except ValueError:
            settings['mic_device_id'] = None # Nessun dispositivo valido selezionato

        try:
            sys_selected_str = self.sys_combo.get()
            if sys_selected_str and sys_selected_str != "Seleziona dispositivo audio di sistema": # Evita il placeholder
                settings['sys_device_id'] = int(sys_selected_str.split(":")[0])
        except ValueError:
            settings['sys_device_id'] = None

        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except IOError as e:
            messagebox.showerror("Salvataggio Impostazioni", f"Impossibile salvare le impostazioni: {e}")

    def on_closing(self):
        # Impedisce la chiusura se il salvataggio è in corso per evitare corruzione file
        if self.save_thread and self.save_thread.is_alive():
            messagebox.showwarning("Salvataggio in corso", "Attendi il completamento del salvataggio prima di chiudere l'applicazione.")
            return

        if self.is_recording:
            if not messagebox.askyesno("Registrazione in corso", "Una registrazione è in corso. Vuoi interromperla e chiudere l'applicazione?"):
                return
            self.stop_recording() # Interrompe la registrazione prima di chiudere
            return # Esce dalla funzione per permettere all'utente di gestire il salvataggio

        self.video_capture_thread_running = False # Ferma il thread di cattura video
        self._stop_audio_monitoring_streams() # Ferma gli stream audio
        if self.preview_update_id: self.root.after_cancel(self.preview_update_id) # Cancella il loop di rendering dell'anteprima
        
        self.save_settings()
        self.root.destroy()
        
        # Forza l'uscita del processo per liberare risorse hardware (Webcam/Audio) che potrebbero bloccare il termine del programma
        os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = ProfessionalRecorder(root)
    root.mainloop()