import tkinter as tk
from tkinter import messagebox, filedialog, ttk, font as tkfont, simpledialog
import subprocess
import os
import sys
from shutil import which
import json

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
            ix = (w - (tw + iw + 10)) / 2 + iw / 2
            self.create_image(ix, h/2, image=self.image)
            self.create_text(ix + iw/2 + 10 + tw/2, h/2, text=self.text, fill=self.fg, font=self.font)
        elif self.image: self.create_image(w/2, h/2, image=self.image)
        else: self.create_text(w/2, h/2, text=self.text, fill=self.fg, font=self.font)

try:
    from PIL import Image, ImageTk
except ImportError:
    pass

class QEMUManager:
    def __init__(self, root):
        self.root = root
        self.root.title("QEMU Virtual Machine Manager - Suite Multimediale di Daniele Barile")
        self.root.geometry("800x650")
        self.root.state('zoomed')
        self.root.configure(bg="#f3f3f3")
        self.root.attributes("-alpha", 0.0)

        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vms_config.json")
        self.vms_data = self.load_vms_config()

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
        icon_names = {'Apri': 'open.png', 'Avvia': 'print.png', 'Nuovo': 'new.png'}
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_path = os.path.join(script_dir, 'icons')

        for key, filename in icon_names.items():
            path = os.path.join(icons_path, filename)
            if os.path.exists(path):
                try:
                    img = Image.open(path).resize((18, 18), Image.LANCZOS)
                    self.icons[key] = ImageTk.PhotoImage(img)
                except: self.icons[key] = None

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#ffffff", height=60, bd=0)
        header.pack(side=tk.TOP, fill=tk.X)
        tk.Label(header, text="VIRTUAL MACHINE MANAGER", fg="#D4AF37", bg="#ffffff", font=("Segoe UI Variable Display", 16, "bold")).pack(pady=15)
        
        # Separatore oro
        tk.Frame(self.root, bg="#D4AF37", height=2).pack(fill=tk.X)

        # PanedWindow per dividere Sidebar e Configurazione
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#f3f3f3", sashwidth=4, bd=0)
        self.paned.pack(expand=True, fill='both')

        # --- SIDEBAR (Lista VM) ---
        sidebar = tk.Frame(self.paned, bg="#ffffff", width=250, padx=10, pady=10)
        self.paned.add(sidebar)

        tk.Label(sidebar, text="LE MIE MACCHINE", bg="#ffffff", fg="#1a1a1a", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10))
        
        self.vm_listbox = tk.Listbox(sidebar, bd=0, font=("Segoe UI", 10), bg="#ffffff", fg="#1a1a1a", 
                                     selectbackground="#D4AF37", highlightthickness=1, highlightbackground="#e5e5e5")
        self.vm_listbox.pack(expand=True, fill='both', pady=5)
        self.vm_listbox.bind("<<ListboxSelect>>", self.load_selected_vm)
        
        side_btn_frame = tk.Frame(sidebar, bg="#ffffff")
        side_btn_frame.pack(fill=tk.X, pady=5)
        
        RoundedButton(side_btn_frame, text="Salva Config", command=self.save_current_vm, bg="#D4AF37", width=100).pack(side=tk.LEFT, padx=2)
        RoundedButton(side_btn_frame, text="Elimina", command=self.delete_selected_vm, bg="#ffffff", fg="red", width=100).pack(side=tk.LEFT, padx=2)

        # --- MAIN CONFIG AREA ---
        main_frame = tk.Frame(self.paned, padx=30, pady=20, bg="#f3f3f3")
        self.paned.add(main_frame)

        # Configurazione Hardware
        hw_frame = tk.LabelFrame(main_frame, text="Configurazione Hardware", padx=15, pady=15, bg="#f3f3f3", fg="#1a1a1a", font=("Segoe UI", 10, "bold"))
        hw_frame.pack(fill=tk.X, pady=5)

        lbl_style = {"bg": "#f3f3f3", "fg": "#1a1a1a", "font": ("Segoe UI", 9)}
        ent_style = {"bg": "#ffffff", "fg": "#1a1a1a", "insertbackground": "black", "bd": 1, "relief": tk.SOLID}

        # Nome VM
        tk.Label(hw_frame, text="Nome VM:", **lbl_style).grid(row=0, column=0, sticky="w")
        self.ent_vm_name = tk.Entry(hw_frame, width=30, **ent_style)
        self.ent_vm_name.grid(row=0, column=1, padx=5, pady=5, sticky="w", columnspan=3)
        
        # RAM e CPU
        tk.Label(hw_frame, text="RAM (MB):", **lbl_style).grid(row=1, column=0, sticky="w", pady=(10,0))
        self.ent_ram = tk.Entry(hw_frame, width=10, **ent_style)
        self.ent_ram.insert(0, "2048")
        self.ent_ram.grid(row=1, column=1, padx=5, pady=(10,0), sticky="w")

        tk.Label(hw_frame, text="CPU Cores:", **lbl_style).grid(row=1, column=2, sticky="w", padx=20, pady=(10,0))
        self.ent_cpu = tk.Entry(hw_frame, width=10, **ent_style)
        self.ent_cpu.insert(0, "2")
        self.ent_cpu.grid(row=1, column=3, padx=5, pady=(10,0), sticky="w")

        # Popola la lista iniziale
        self.refresh_vm_list()

        # Archiviazione
        storage_frame = tk.LabelFrame(main_frame, text="Archiviazione e Boot", padx=15, pady=15, bg="#f3f3f3", fg="#1a1a1a", font=("Segoe UI", 10, "bold"))
        storage_frame.pack(fill=tk.X, pady=5)
        storage_frame.grid_columnconfigure(1, weight=1)

        # ISO
        tk.Label(storage_frame, text="Immagine ISO:", **lbl_style).grid(row=0, column=0, sticky="w")
        self.ent_iso = tk.Entry(storage_frame, **ent_style)
        self.ent_iso.grid(row=0, column=1, padx=5, pady=5, sticky="ew", columnspan=1) # Rimuovi columnspan per allineamento
        RoundedButton(storage_frame, text=" Sfoglia", image=self.icons.get('Apri'), compound="left",
                  command=self.browse_iso, bg="#D4AF37", padx_btn=10).grid(row=0, column=2, padx=5)

        # Disk
        tk.Label(storage_frame, text="Disco Virtuale:", **lbl_style).grid(row=1, column=0, sticky="w")
        self.ent_disk = tk.Entry(storage_frame, **ent_style)
        self.ent_disk.grid(row=1, column=1, padx=5, pady=5, sticky="ew", columnspan=1) # Rimuovi columnspan per allineamento
        RoundedButton(storage_frame, text=" Sfoglia", image=self.icons.get('Apri'), compound="left",
                  command=self.browse_disk, bg="#D4AF37", padx_btn=10).grid(row=1, column=2, padx=5)

        # UEFI
        tk.Label(storage_frame, text="Firmware UEFI (OVMF):", **lbl_style).grid(row=2, column=0, sticky="w")
        self.ent_uefi = tk.Entry(storage_frame, **ent_style)
        self.ent_uefi.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        RoundedButton(storage_frame, text=" Sfoglia", image=self.icons.get('Apri'), compound="left",
                  command=self.browse_uefi, bg="#D4AF37", padx_btn=10).grid(row=2, column=2, padx=5)

        # USB Host
        tk.Label(storage_frame, text="USB Host (PhysicalDrive):", **lbl_style).grid(row=3, column=0, sticky="w")
        self.combo_usb = ttk.Combobox(storage_frame)
        self.combo_usb.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        RoundedButton(storage_frame, text=" Aggiorna", command=self.refresh_usb_drives, 
                      bg="#ffffff", width=80, radius=5).grid(row=3, column=2, padx=5)

        # Ordine di Boot
        tk.Label(storage_frame, text="Ordine di Boot:", **lbl_style).grid(row=4, column=0, sticky="w")
        self.combo_boot = ttk.Combobox(storage_frame, values=["Disco (C), CD-ROM (D)", "CD-ROM (D), Disco (C)"], state="readonly")
        self.combo_boot.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        self.combo_boot.set("Disco (C), CD-ROM (D)")

        # Opzioni Extra
        extra_frame = tk.LabelFrame(main_frame, text="Opzioni Avanzate", padx=15, pady=15, bg="#f3f3f3", fg="#1a1a1a", font=("Segoe UI", 10, "bold"))
        extra_frame.pack(fill=tk.X, pady=5)
        
        self.var_accel = tk.BooleanVar(value=True)
        tk.Checkbutton(extra_frame, text="Abilita Accelerazione Hardware (KVM/HAXM)", variable=self.var_accel, bg="#f3f3f3", fg="#1a1a1a", selectcolor="#ffffff", activebackground="#f3f3f3", activeforeground="#D4AF37", font=("Segoe UI", 9)).pack(side=tk.LEFT)

        self.var_macos = tk.BooleanVar(value=False)
        tk.Checkbutton(extra_frame, text="Ottimizza per macOS (AppleSMC/OSK)", variable=self.var_macos, 
                       bg="#f3f3f3", fg="#1a1a1a", selectcolor="#ffffff", activebackground="#f3f3f3", 
                       activeforeground="#D4AF37", font=("Segoe UI", 9), command=self.on_macos_toggle).pack(side=tk.LEFT, padx=20)

        # Console Output
        tk.Label(main_frame, text="Log Console:", bg="#f3f3f3", fg="#D4AF37", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 0))
        self.txt_log = tk.Text(main_frame, height=10, bg="#0a0a0a", fg="#00ff00", font=("Consolas", 10), bd=0)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Carica la lista USB iniziale
        self.refresh_usb_drives()

        # Azioni
        btn_frame = tk.Frame(main_frame, bg="#f3f3f3")
        btn_frame.pack(fill=tk.X, pady=10)

        self.btn_launch = RoundedButton(btn_frame, text=" AVVIA MACCHINA VIRTUALE", image=self.icons.get('Avvia'), 
                                   compound="left", bg="#D4AF37", fg="black", font=("Segoe UI", 10, "bold"),
                                   padx_btn=20, pady_btn=10, command=self.launch_vm)
        self.btn_launch.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        RoundedButton(btn_frame, text=" Nuovo Disco", image=self.icons.get('Nuovo'), 
                  compound="left", bg="#ffffff", fg="#1a1a1a", padx_btn=10, pady_btn=10, command=self.create_disk).pack(side=tk.LEFT, padx=5)

        RoundedButton(btn_frame, text=" Ingrandisci Disco", image=self.icons.get('Apri'), 
                  compound="left", bg="#ffffff", fg="#1a1a1a", padx_btn=10, pady_btn=10, command=self.resize_disk).pack(side=tk.LEFT, padx=5)

        # Footer Brand
        self.footer_label = tk.Label(self.root, text="Powered by Daniele Barile", bg="#f3f3f3", fg="#d4af37", font=("Helvetica", 14, "bold"))
        self.footer_label.pack(side=tk.BOTTOM, pady=2)

    def load_vms_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_vms_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.vms_data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Errore Salvataggio", str(e))

    def refresh_vm_list(self):
        self.vm_listbox.delete(0, tk.END)
        for name in sorted(self.vms_data.keys()):
            self.vm_listbox.insert(tk.END, name)

    def save_current_vm(self):
        name = self.ent_vm_name.get().strip()
        if not name:
            messagebox.showwarning("Attenzione", "Inserisci un nome per la macchina virtuale.")
            return
        
        self.vms_data[name] = {
            "ram": self.ent_ram.get(),
            "cpu": self.ent_cpu.get(),
            "iso": self.ent_iso.get(),
            "disk": self.ent_disk.get(),
            "uefi": self.ent_uefi.get(),
            "usb": self.combo_usb.get(),
            "macos": self.var_macos.get(),
            "accel": self.var_accel.get(),
            "boot_order": self.combo_boot.get()
        }
        self.save_vms_config()
        self.refresh_vm_list()
        messagebox.showinfo("Successo", f"Configurazione '{name}' salvata.")

    def load_selected_vm(self, event):
        selection = self.vm_listbox.curselection()
        if not selection: return
        
        name = self.vm_listbox.get(selection[0])
        data = self.vms_data.get(name)
        if data:
            self.ent_vm_name.delete(0, tk.END)
            self.ent_vm_name.insert(0, name)
            self.ent_ram.delete(0, tk.END)
            self.ent_ram.insert(0, data.get("ram", "2048"))
            self.ent_cpu.delete(0, tk.END)
            self.ent_cpu.insert(0, data.get("cpu", "2"))
            self.ent_iso.delete(0, tk.END)
            self.ent_iso.insert(0, data.get("iso", ""))
            self.ent_disk.delete(0, tk.END)
            self.ent_disk.insert(0, data.get("disk", ""))
            self.ent_uefi.delete(0, tk.END)
            self.ent_uefi.insert(0, data.get("uefi", ""))
            self.combo_usb.delete(0, tk.END)
            self.combo_usb.insert(0, data.get("usb", ""))
            self.var_macos.set(data.get("macos", False))
            self.var_accel.set(data.get("accel", True))
            self.combo_boot.set(data.get("boot_order", "Disco (C), CD-ROM (D)"))

    def delete_selected_vm(self):
        selection = self.vm_listbox.curselection()
        if not selection: return
        
        name = self.vm_listbox.get(selection[0])
        if messagebox.askyesno("Conferma", f"Eliminare la configurazione '{name}'?"):
            del self.vms_data[name]
            self.save_vms_config()
            self.refresh_vm_list()
            self.clear_fields()

    def clear_fields(self):
        self.ent_vm_name.delete(0, tk.END)
        self.ent_ram.delete(0, tk.END); self.ent_ram.insert(0, "2048")
        self.ent_cpu.delete(0, tk.END); self.ent_cpu.insert(0, "2")
        self.ent_iso.delete(0, tk.END)
        self.ent_disk.delete(0, tk.END)
        self.ent_uefi.delete(0, tk.END)
        self.combo_usb.set("")
        self.combo_boot.set("Disco (C), CD-ROM (D)")

    def refresh_usb_drives(self):
        """Recupera la lista dei dischi fisici collegati (Windows)."""
        drives = []
        if sys.platform == "win32":
            try:
                # Esegue wmic per ottenere ID e Modello dei dischi
                output = subprocess.check_output('wmic diskdrive get DeviceID,Model', shell=True).decode('utf-8')
                lines = output.strip().split('\n')[1:] # Salta l'intestazione
                for line in lines:
                    if line.strip():
                        # Separa il DeviceID dal Modello (wmic usa spazi fissi)
                        parts = line.split(None, 1)
                        path = parts[0].strip()
                        model = parts[1].strip() if len(parts) > 1 else "Disco Generico"
                        drives.append(f"{path} ({model})")
            except Exception as e:
                self.txt_log.insert(tk.END, f"Errore scansione USB: {e}\n")
        self.combo_usb['values'] = drives

    def on_macos_toggle(self):
        """Suggerisce impostazioni ottimali (4GB RAM) quando si attiva il supporto macOS."""
        if self.var_macos.get():
            try:
                if int(self.ent_ram.get()) < 4096:
                    self.ent_ram.delete(0, tk.END); self.ent_ram.insert(0, "4096")
            except: self.ent_ram.delete(0, tk.END); self.ent_ram.insert(0, "4096")

    def browse_iso(self):
        f = filedialog.askopenfilename(filetypes=[("ISO/Raw Images", "*.iso *.raw *.img"), ("All Files", "*.*")])
        if f: self.ent_iso.delete(0, tk.END); self.ent_iso.insert(0, f)

    def browse_disk(self):
        f = filedialog.askopenfilename(filetypes=[("Disk Images", "*.qcow2 *.img *.vmdk *.raw"), ("All Files", "*.*")])
        if f: self.ent_disk.delete(0, tk.END); self.ent_disk.insert(0, f)

    def browse_uefi(self):
        f = filedialog.askopenfilename(filetypes=[("UEFI Firmware", "*.fd *.bin"), ("All Files", "*.*")])
        if f: self.ent_uefi.delete(0, tk.END); self.ent_uefi.insert(0, f)

    def get_qemu_bin(self, name):
        """Cerca l'eseguibile QEMU nel PATH o nelle cartelle standard."""
        path = which(name)
        if path:
            return path
        
        # Percorsi comuni su Windows
        common_paths = [
            r"C:\Program Files\qemu",
            r"C:\Program Files (x86)\qemu"
        ]
        for p in common_paths:
            full_path = os.path.join(p, f"{name}.exe")
            if os.path.exists(full_path):
                return full_path
        return name # Ritorna il nome semplice come fallback

    def create_disk(self):
        size = simpledialog.askstring("Grandezza Disco", "Inserisci la dimensione del disco (es. 20G, 50G, 100G):", initialvalue="20G")
        if not size: return

        path = filedialog.asksaveasfilename(defaultextension=".qcow2", filetypes=[("QEMU Disk", "*.qcow2")])
        if path:
            qemu_img = self.get_qemu_bin("qemu-img")
            cmd = [qemu_img, "create", "-f", "qcow2", path, size]
            try:
                subprocess.run(cmd, check=True)
                self.ent_disk.delete(0, tk.END); self.ent_disk.insert(0, path)
                messagebox.showinfo("Successo", f"Disco da {size} creato correttamente.")
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile creare il disco. QEMU è installato?\n{e}")

    def resize_disk(self):
        disk_path = self.ent_disk.get().strip()
        if not disk_path or not os.path.exists(disk_path):
            messagebox.showwarning("Attenzione", "Seleziona prima un disco virtuale esistente nel campo 'Disco Virtuale'.")
            return

        size_to_add = simpledialog.askstring("Ingrandisci Disco", 
                                             "Di quanto vuoi ingrandire il disco? (es. +10G, +50G):", 
                                             initialvalue="+10G")
        if not size_to_add: return

        qemu_img = self.get_qemu_bin("qemu-img")
        cmd = [qemu_img, "resize", disk_path, size_to_add]
        try:
            subprocess.run(cmd, check=True)
            messagebox.showinfo("Successo", f"Disco ingrandito correttamente.\n\nNota: Ora dovrai avviare la VM e usare 'Utility Disco' (macOS) o 'Gestione Disco' (Windows) per estendere la partizione nello spazio non allocato.")
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile ingrandire il disco.\n{e}")

    def launch_vm(self):
        ram = self.ent_ram.get()
        cpu = self.ent_cpu.get()
        iso = self.ent_iso.get()
        disk = self.ent_disk.get()
        uefi = self.ent_uefi.get()
        
        # Ordine di Boot
        is_cd_first = self.combo_boot.get().startswith("CD-ROM")
        
        # Estrae solo la parte \\.\PhysicalDriveN dalla selezione
        usb_host_raw = self.combo_usb.get().strip()
        usb_host = usb_host_raw.split(' (')[0] if usb_host_raw else ""

        disk_format = "qcow2"
        if disk:
            ext = os.path.splitext(disk)[1].lower()
            if ext in [".img", ".raw"]: disk_format = "raw"
            elif ext == ".vmdk": disk_format = "vmdk"

        iso_format = "raw"
        if iso:
            ext_i = os.path.splitext(iso)[1].lower()
            if ext_i in [".raw", ".img", ".iso"]: iso_format = "raw"

        qemu_dir = os.path.dirname(self.get_qemu_bin("qemu-system-x86_64"))
        bios_path = os.path.join(qemu_dir, "share")

        if self.var_macos.get() and not uefi:
            self.txt_log.insert(tk.END, "AVVISO: macOS richiede un firmware UEFI (OVMF) per avviarsi.\n", "warning")
            self.txt_log.tag_config("warning", foreground="orange")
            messagebox.showwarning("Fornire UEFI", "Per emulare macOS correttamente è necessario selezionare un file firmware UEFI (es. OVMF_CODE.fd) nel campo 'Firmware UEFI'.")

        # Cerca l'eseguibile principale
        qemu_bin = self.get_qemu_bin("qemu-system-x86_64")

        cmd = [qemu_bin, "-L", bios_path, "-m", ram]

        if self.var_macos.get():
            # macOS preferisce una topologia core esplicita per evitare kernel panic
            cmd.extend(["-smp", f"{cpu},cores={cpu},threads=1"])
        else:
            cmd.extend(["-smp", cpu])

        if uefi and os.path.exists(uefi):
            # Configurazione firmware UEFI (pflash 0 per CODE, pflash 1 per VARS)
            cmd.extend(["-drive", f"if=pflash,format=raw,readonly=on,file={os.path.normpath(uefi)}"])
            # Tenta di caricare il file delle variabili se segue lo schema standard
            for pattern in ["VARS.fd", "_VARS.fd", "vars.fd"]:
                v_p = uefi.replace("CODE.fd", pattern).replace("_CODE.fd", pattern).replace("code.fd", pattern)
                if os.path.exists(v_p) and v_p != uefi:
                    cmd.extend(["-drive", f"if=pflash,format=raw,file={os.path.normpath(v_p)}"])
                    break

        # Supporto specifico per macOS
        if self.var_macos.get():
            # q35 con kernel-irqchip=off migliora la stabilità di macOS con WHPX su Windows
            cmd.extend(["-machine", "q35,kernel-irqchip=off"])
            # Disabilita hotplug bridge per evitare kernel panic su alcuni kernel macOS
            cmd.extend(["-global", "ICH9-LPC.acpi-pci-hotplug-with-bridge-support=off"])
            # Sequoia richiede AVX2. Passiamo a Haswell-noTSX che è lo standard per macOS moderno su QEMU.
            # Aggiungiamo kvm=on per nascondere lo stato di virtualizzazione al kernel Apple
            cpu_model = "Haswell-noTSX,vendor=GenuineIntel,kvm=on,+invtsc,+sse4.2,+avx,+avx2,+aes,+fma,+bmi1,+bmi2,+smep,+xsave,+xsaveopt,+x2apic"
            cmd.extend(["-cpu", cpu_model])
            # Chiave OSK standard per l'emulazione AppleSMC
            osk = "ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"
            cmd.extend(["-device", f"isa-applesmc,osk={osk}"])
            cmd.extend(["-smbios", "type=2", "-smbios", "type=1,product=iMac19,,1"])
            # Aumentiamo la memoria video (4GB) tramite il comando richiesto
            cmd.extend(["-vga", "none", "-device", "VGA,vgamem_mb=4096"])
            # Aggiunge un controller USB 3.0 (XHCI) e collega correttamente le periferiche
            cmd.extend(["-device", "qemu-xhci,id=xhci"])
            cmd.extend(["-device", "usb-tablet,bus=xhci.0", "-device", "usb-kbd,bus=xhci.0"])
            # Scheda di rete compatibile con i driver nativi Apple
            cmd.extend(["-netdev", "user,id=net0", "-device", "e1000-82545em,netdev=net0"])

        # Aggiunta supporto Audio (Intel HDA)
        # Questo è un parametro generale, non solo per macOS
        cmd.extend(["-device", "intel-hda", "-device", "hda-duplex"])

        if self.var_accel.get():
            if sys.platform == "win32":
                # Fallback sicuro: WHPX -> HAXM -> TCG (emulazione)
                # Rimosso HAXM per evitare conflitti con WHPX
                cmd.extend(["-accel", "whpx", "-accel", "tcg"])
            else:
                cmd.extend(["-accel", "kvm", "-accel", "tcg"])

        # Calcolo bootindex: se c'è una USB, deve avere la priorità (0)
        usb_offset = 1 if usb_host else 0

        if usb_host:
            # Collega un disco fisico dell'host come dispositivo USB
            cmd.extend(["-drive", f"file={usb_host},if=none,id=usb_boot,format=raw,cache=none"])
            usb_dev = "usb-storage,drive=usb_boot,bootindex=0"
            if self.var_macos.get(): usb_dev += ",bus=xhci.0"
            cmd.extend(["-device", usb_dev])

        if self.var_macos.get():
            if disk:
                disk_idx = 1 + usb_offset if is_cd_first else 0 + usb_offset
                cmd.extend(["-drive", f"id=MacHDD,if=none,file={os.path.normpath(disk)},format={disk_format},cache=writethrough"])
                cmd.extend(["-device", f"ide-hd,bus=ide.1,drive=MacHDD,bootindex={disk_idx}"])
            if iso:
                iso_idx = 0 + usb_offset if is_cd_first else 1 + usb_offset
                cmd.extend(["-drive", f"id=MacISO,if=none,file={os.path.normpath(iso)},format={iso_format},media=cdrom"])
                cmd.extend(["-device", f"ide-cd,bus=ide.0,drive=MacISO,bootindex={iso_idx}"])
        else:
            # Configurazione standard con memoria video aumentata (4GB) come richiesto
            cmd.extend(["-vga", "none", "-device", "VGA,vgamem_mb=4096"])
            if disk:
                cmd.extend(["-drive", f"file={os.path.normpath(disk)},format={disk_format}"])
            if iso:
                cmd.extend(["-drive", f"file={os.path.normpath(iso)},format={iso_format},media=cdrom"])

        # Configurazione Boot
        boot_order_str = "dcn" if is_cd_first else "cdn"
        boot_params = "menu=on,strict=on"
        cmd.extend(["-boot", f"order={boot_order_str},{boot_params}"])

        # Debug log con percorsi quotati per la console
        log_cmd = ' '.join([f'"{arg}"' if ' ' in arg else arg for arg in cmd])
        self.txt_log.insert(tk.END, f"Esecuzione: {log_cmd}\n")
        
        try:
            # Lancio asincrono con cattura errori per capire perché non parte
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
            
            def check_startup_error():
                # Se il processo termina entro 2 secondi, c'è stato un errore di parametri
                ret = process.poll()
                if ret is not None:
                    error_out = process.stderr.read()
                    if "Access is denied" in error_out:
                        self.txt_log.insert(tk.END, "\n[!] ERRORE: ACCESSO NEGATO AL DISCO FISICO.\n", "error")
                        self.txt_log.insert(tk.END, "1. Esegui la Suite come AMMINISTRATORE.\n", "error")
                        self.txt_log.insert(tk.END, "2. Metti il disco 'Offline' in Gestione Disco (diskmgmt.msc).\n", "error")
                    self.txt_log.insert(tk.END, f"ERRORE CRITICO QEMU:\n{error_out}\n", "error")
                    self.txt_log.tag_config("error", foreground="red")
                    messagebox.showerror("Errore Avvio", f"QEMU si è chiuso inaspettatamente.\n\nControlla il log della console.")
                else:
                    self.txt_log.insert(tk.END, "VM Avviata correttamente.\n", "success")
            
            self.root.after(2000, check_startup_error)

        except FileNotFoundError:
            messagebox.showerror("Errore", "QEMU non trovato. Assicurati che sia installato e nel PATH di sistema.")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = QEMUManager(root)
    root.mainloop()