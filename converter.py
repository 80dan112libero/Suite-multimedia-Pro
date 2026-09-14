import tkinter as tk
from tkinter import messagebox, filedialog, ttk, font as tkfont
import os
import sys
import threading
import json

try:
    from PIL import Image, ImageTk
    try:
        # Compatibilità MoviePy v1.x
        from moviepy.editor import VideoFileClip
    except ImportError:
        # Compatibilità MoviePy v2.x
        from moviepy import VideoFileClip
except ImportError as e:
    print(f"Errore tecnico dettagliato: {e}")
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Errore Librerie",
                         f"Mancano delle librerie necessarie per il Video Converter:\n{e}\n\n"
                         "Esegui il file 'installa_librerie.bat' oppure digita:\n"
                         "pip install moviepy Pillow opencv-python pyautogui numpy sounddevice")
    root.destroy()
    sys.exit()

CONVERTER_SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "converter_settings.json")

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
        else: calculated_width = max(text_width, img_width)
        canvas_width = calculated_width + 2 * padx_btn + 2 * radius
        canvas_height = self.f_obj.metrics('linespace') + 2 * pady_btn + 2 * radius
        super().__init__(parent, width=canvas_width, height=canvas_height, bg=parent['bg'], 
                         highlightthickness=0, bd=0, cursor="hand2" if state == tk.NORMAL else "arrow")
        self.command, self.bg, self.active_bg, self.fg, self.radius = command, bg, active_bg, fg, radius
        self.font, self.image, self.text, self.compound, self.state = font, image, text, compound, state
        self.padx_btn, self.pady_btn = padx_btn, pady_btn
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
            tw = self.f_obj.measure(self.text); iw = self.image.width()
            ix = (w - (tw + iw + 10)) / 2 + iw / 2
            self.create_image(ix, h/2, image=self.image)
            self.create_text(ix + iw/2 + 10 + tw/2, h/2, text=self.text, fill=self.fg, font=self.font)
        elif self.image: self.create_image(w/2, h/2, image=self.image)
        else: self.create_text(w/2, h/2, text=self.text, fill=self.fg, font=self.font)

class VideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Converter - Suite Multimediale di Daniele Barile")
        self.root.geometry("800x600")
        self.root.state('zoomed')
        self.root.configure(bg="#121212")
        self.root.attributes("-alpha", 0.0)

        self.settings = self.load_settings()
        self.input_files = self.settings.get("last_files", [])
        self.output_dir = self.settings.get("output_dir", os.path.expanduser("~"))
        self.output_format = self.settings.get("output_format", ".mp4")

        self.icons = {}
        self.load_icons()
        self.setup_ui()
        
        for f in self.input_files:
            if os.path.exists(f):
                self.listbox_input.insert(tk.END, os.path.basename(f))

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.animate_fade_in()

    def load_settings(self):
        if os.path.exists(CONVERTER_SETTINGS):
            try:
                with open(CONVERTER_SETTINGS, "r") as f:
                    return json.load(f)
            except: pass
        return {"output_dir": os.path.expanduser("~"), "output_format": ".mp4", "last_files": []}

    def save_settings(self):
        self.settings["output_dir"] = self.output_dir
        self.settings["output_format"] = self.output_format
        self.settings["last_files"] = self.input_files
        try:
            with open(CONVERTER_SETTINGS, "w") as f:
                json.dump(self.settings, f, indent=4)
        except: pass

    def animate_fade_in(self):
        alpha = self.root.attributes("-alpha")
        if alpha < 1.0:
            alpha += 0.05
            self.root.attributes("-alpha", alpha)
            self.root.after(20, self.animate_fade_in)

    def load_icons(self):
        icon_names = {
            'Aggiungi': 'add.png', 'Rimuovi': 'delete.png', 'Sfoglia': 'open.png',
            'Converti': 'save.png'
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
            
            self.icons[key] = None # Default
            if found_path:
                try:
                    img = Image.open(found_path).resize((18, 18), Image.LANCZOS)
                    self.icons[key] = ImageTk.PhotoImage(img)
                except Exception:
                    pass

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", thickness=12, troughcolor='#e5e5e5', background='#D4AF37', bordercolor="#e5e5e5")
        style.configure("TCombobox", fieldbackground="#1e1e1e", background="#D4AF37", foreground="white", bordercolor="#d1d1d1")

        # Frame principale
        main_frame = tk.Frame(self.root, padx=20, pady=20, bg="#121212")
        main_frame.pack(expand=True, fill='both')

        # Sezione Input Files
        input_frame = tk.LabelFrame(main_frame, text="File Video di Input", padx=10, pady=10, bg="#121212", fg="#D4AF37", font=("Segoe UI Variable Text", 10, "bold"))
        input_frame.pack(fill='both', expand=True, pady=5)

        self.listbox_input = tk.Listbox(input_frame, selectmode=tk.EXTENDED, height=10, bd=1, font=("Segoe UI", 10), bg="#1e1e1e", fg="white", selectbackground="#D4AF37", highlightcolor="#D4AF37", relief=tk.FLAT)
        self.listbox_input.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))

        scrollbar = tk.Scrollbar(input_frame, orient="vertical", command=self.listbox_input.yview)
        scrollbar.pack(side=tk.LEFT, fill="y")
        self.listbox_input.config(yscrollcommand=scrollbar.set)

        btn_frame_input = tk.Frame(input_frame, bg="#121212")
        btn_frame_input.pack(side=tk.RIGHT, fill='y')
        
        self.add_file_btn = RoundedButton(btn_frame_input, text="Aggiungi File", image=self.icons.get('Aggiungi'), compound='left',
                  command=self.add_files, bg="#D4AF37", fg="black", padx_btn=10)
        self.add_file_btn.pack(fill='x', pady=2)
        self.remove_file_btn = RoundedButton(btn_frame_input, text="Rimuovi Selezionati", image=self.icons.get('Rimuovi'), compound='left',
                  command=self.remove_selected_files, bg="#1e1e1e", fg="white", padx_btn=10)
        self.remove_file_btn.pack(fill='x', pady=2)

        # Sezione Output Options
        output_frame = tk.LabelFrame(main_frame, text="Opzioni di Output", padx=10, pady=10, bg="#121212", fg="#D4AF37", font=("Segoe UI Variable Text", 10, "bold"))
        output_frame.pack(fill='x', pady=5)

        tk.Label(output_frame, text="Formato Output:", bg="#121212", fg="white", font=("Segoe UI", 9)).grid(row=0, column=0, sticky='w', pady=2)
        self.output_format_combo = ttk.Combobox(output_frame, 
                                                values=[".mp4", ".avi", ".mov", ".mkv", ".gif"], 
                                                state="readonly", font=("Segoe UI", 10))
        self.output_format_combo.set(self.output_format)
        self.output_format_combo.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        self.output_format_combo.bind("<<ComboboxSelected>>", self.on_format_selected)

        tk.Label(output_frame, text="Cartella Output:", bg="#121212", fg="white", font=("Segoe UI", 9)).grid(row=1, column=0, sticky='w', pady=2)
        self.entry_output_dir = tk.Entry(output_frame, textvariable=tk.StringVar(value=self.output_dir), bd=1, font=("Segoe UI", 10), bg="#1e1e1e", fg="white", relief=tk.SOLID)
        self.entry_output_dir.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        self.browse_output_btn = RoundedButton(output_frame, text=" Sfoglia", image=self.icons.get('Sfoglia'), compound='left',
                  command=self.browse_output_dir, bg="#D4AF37", fg="black", padx_btn=10)
        self.browse_output_btn.grid(row=1, column=2, padx=2, pady=2)

        output_frame.grid_columnconfigure(1, weight=1)

        # Sezione Progress
        progress_frame = tk.LabelFrame(main_frame, text="Progresso Conversione", padx=10, pady=10, bg="#121212", fg="#D4AF37", font=("Segoe UI", 10, "bold"))
        progress_frame.pack(fill='x', pady=5)

        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate", style="TProgressbar")
        self.progress_bar.pack(fill='x', pady=5)

        self.status_label = tk.Label(progress_frame, text="Pronto per la conversione.", bg="#121212", fg="#a0a0a0", font=("Segoe UI", 9))
        self.status_label.pack(fill='x')

        # Bottone Converti
        self.convert_button = RoundedButton(main_frame, text=" CONVERTI VIDEO ", image=self.icons.get('Converti'), compound='left',
                                        command=self.start_conversion_thread, bg="#D4AF37", fg="black",
                                        font=("Segoe UI", 11, "bold"), padx_btn=10, pady_btn=10)
        self.convert_button.pack(fill='x', pady=10)

        # Footer Brand
        self.footer_label = tk.Label(self.root, text="Powered by Daniele Barile", bg="#121212", fg="#d4af37", font=("Helvetica", 14, "bold"))
        self.footer_label.pack(side=tk.BOTTOM, pady=2)

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Seleziona file video",
            filetypes=[
                ("File Video", "*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.webm *.ogg *.3gp"),
                ("Tutti i file", "*.*")
            ]
        )
        if files:
            for f in files:
                if f not in self.input_files:
                    self.input_files.append(f)
                    self.listbox_input.insert(tk.END, os.path.basename(f))

    def remove_selected_files(self):
        selected_indices = self.listbox_input.curselection()
        if not selected_indices:
            return
        
        # Rimuovi dalla lista interna in ordine inverso per non sfasare gli indici
        for index in reversed(selected_indices):
            self.input_files.pop(index)
            self.listbox_input.delete(index)

    def on_format_selected(self, event):
        self.output_format = self.output_format_combo.get()

    def browse_output_dir(self):
        directory = filedialog.askdirectory(title="Seleziona cartella di output")
        if directory:
            self.output_dir = directory
            self.entry_output_dir.delete(0, tk.END)
            self.entry_output_dir.insert(0, self.output_dir)

    def update_progress(self, percentage, message=""):
        # Aggiornamento UI sicuro da thread tramite after
        self.root.after(0, lambda: self._update_progress_ui(percentage, message))

    def _update_progress_ui(self, percentage, message):
        self.progress_bar['value'] = percentage
        if message:
            self.status_label.config(text=message)
        self.root.update_idletasks()

    def start_conversion_thread(self):
        if not self.input_files:
            messagebox.showwarning("Nessun file", "Seleziona almeno un file video da convertire.")
            return
        if not self.output_dir:
            messagebox.showwarning("Cartella di output", "Seleziona una cartella di destinazione.")
            return
        
        self.convert_button.config(state=tk.DISABLED)
        self.update_progress(0, "Avvio conversione...")
        
        # Avvia la conversione in un thread separato per non bloccare la GUI
        conversion_thread = threading.Thread(target=self._perform_conversion)
        conversion_thread.start()

    def _perform_conversion(self):
        total_files = len(self.input_files)
        converted_count = 0
        
        for i, input_path in enumerate(self.input_files):
            try:
                # Rimuoviamo eventuali punti finali: Windows non gestisce bene file che finiscono con "."
                # Questo è il motivo principale del "Broken Pipe" con file come "summer mix......"
                base_name = os.path.splitext(os.path.basename(input_path))[0].rstrip('.')
                output_path = os.path.join(self.output_dir, f"{base_name}{self.output_format}")

                # Evita di sovrascrivere il file di input se sono nella stessa cartella e con stesso formato
                if os.path.abspath(input_path) == os.path.abspath(output_path):
                    output_path = os.path.join(self.output_dir, f"{base_name}_converted{self.output_format}")

                self.update_progress(0, f"Conversione {i+1}/{total_files}: {os.path.basename(input_path)}...")
                
                clip = VideoFileClip(input_path)
                
                # Verifica se il file ha effettivamente una traccia audio
                has_audio = clip.audio is not None
                
                # Scrittura del file video
                if self.output_format == ".gif":
                    clip.write_gif(output_path, fps=10, logger=None)
                else:
                    # Specifichiamo pix_fmt="yuv420p" per massima compatibilità e un file audio temporaneo pulito
                    temp_audio = os.path.join(self.output_dir, "temp_audio_encoding.m4a")
                    clip.write_videofile(output_path, 
                                         codec="libx264", 
                                         audio=has_audio,
                                         audio_codec="aac" if has_audio else None, 
                                         temp_audiofile=temp_audio,
                                         remove_temp=True, 
                                         logger=None,
                                         ffmpeg_params=["-nostats", "-loglevel", "quiet", "-pix_fmt", "yuv420p"])
                
                clip.close()
                converted_count += 1
                self.update_progress((converted_count / total_files) * 100, 
                                     f"Completato {converted_count}/{total_files}: {os.path.basename(input_path)}")

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Errore Conversione", 
                                                                f"Errore durante la conversione di {os.path.basename(input_path)}:\n{e}"))
                self.update_progress(0, f"Errore con {os.path.basename(input_path)}. Vedi log.")
                # Non bloccare l'intero processo per un singolo errore
                continue
        
        self.root.after(0, lambda: messagebox.showinfo("Conversione Completata", 
                                                        f"Conversione completata per {converted_count} di {total_files} file."))
        self.update_progress(100, "Tutte le conversioni completate.")
        self.convert_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverter(root)
    root.mainloop()