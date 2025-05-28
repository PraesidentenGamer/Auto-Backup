import os
import shutil
import time
import threading
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

SETTINGS_FILE = "settings.json"

# Tooltip-Klasse für Info-Hinweise bei Hover
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") or (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # Kein Rahmen
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify='left',
            background="#ffffe0", relief='solid', borderwidth=1,
            font=("Segoe UI", 9))
        label.pack(ipadx=5, ipady=3)

    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class BackupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🔄 Automatischer Datei-Backup")
        self.geometry("800x720")
        self.minsize(700, 600)
        self.resizable(True, True)
        self.configure(bg="#2e2e2e")  # dunkler Hintergrund

        # Variablen
        self.source_dir = tk.StringVar()
        self.backup_dir = tk.StringVar()
        self.filter_types = tk.StringVar()
        self.interval = tk.IntVar(value=60)
        self.is_running = False
        self.thread = None
        self.live_event = tk.BooleanVar(value=False)
        self.seconds_until_backup = self.interval.get()
        self.last_backup_time = None
        self.last_backup_count = 0

        self.load_settings()
        self.create_styles()
        self.create_widgets()
        self.validate_all()

    def create_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')

    # Labels weiß
        style.configure("TLabel", background="#2e2e2e", foreground="#ddd", font=("Segoe UI", 11))
        style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#88c0d0")
        style.configure("TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Start.TButton", background="#5cb85c", foreground="white")
        style.map("Start.TButton",
              background=[("active", "#4cae4c")])
        style.configure("Stop.TButton", background="#d9534f", foreground="white")
        style.map("Stop.TButton",
              background=[("active", "#c9302c")])

        style.configure("TEntry", padding=5, foreground="#ddd", fieldbackground="#2e2e2e")
        style.configure("TCheckbutton", background="#2e2e2e", foreground="#ddd", font=("Segoe UI", 11))
        style.configure("BlackSpin.TSpinbox", fieldbackground="#1e1e1e", foreground="#ddd")

    def create_widgets(self):
        pad_x, pad_y = 15, 10

        # Überschrift
        ttk.Label(self, text="Automatischer Datei-Backup", style="Header.TLabel").pack(pady=(10, 15))

        frame = ttk.Frame(self, style="TFrame")
        frame.pack(padx=pad_x, pady=pad_y, fill="x")

        # Quellordner
        ttk.Label(frame, text="Quellordner:").grid(row=0, column=0, sticky="w")
        self.source_entry = ttk.Entry(frame, textvariable=self.source_dir, width=60)
        self.source_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.source_browse = ttk.Button(frame, text="📁 Durchsuchen", command=self.browse_source)
        self.source_browse.grid(row=0, column=2)
        ToolTip(self.source_entry, "Ordner, aus dem Dateien gesichert werden sollen.")

        # Backup-Ordner
        ttk.Label(frame, text="Backup-Ordner:").grid(row=1, column=0, sticky="w", pady=pad_y)
        self.backup_entry = ttk.Entry(frame, textvariable=self.backup_dir, width=60)
        self.backup_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=pad_y)
        self.backup_browse = ttk.Button(frame, text="📁 Durchsuchen", command=self.browse_backup)
        self.backup_browse.grid(row=1, column=2, pady=pad_y)
        ToolTip(self.backup_entry, "Ordner, in den die Dateien gesichert werden sollen.")

        # Dateitypen Filter
        ttk.Label(frame, text="Dateitypen (z.B. .txt,.pdf):").grid(row=2, column=0, sticky="w")
        self.filter_entry = ttk.Entry(frame, textvariable=self.filter_types, width=60)
        self.filter_entry.grid(row=2, column=1, sticky="ew", padx=(0, 8))
        ToolTip(self.filter_entry, "Nur diese Dateitypen werden gesichert (leer = alle).")
        
        # Intervall
        ttk.Label(frame, text="Backup-Intervall (Sekunden):").grid(row=3, column=0, sticky="w", pady=pad_y)
        self.interval_spin = ttk.Spinbox(frame, from_=10, to=3600, textvariable=self.interval, width=10, command=self.reset_countdown)
        self.interval_spin.grid(row=3, column=1, sticky="w", padx=(0, 8), pady=pad_y)
        ToolTip(self.interval_spin, "Intervall in Sekunden zwischen Backups.")

        # Live Event Checkbox + Countdown
        self.live_check = ttk.Checkbutton(frame, text="Live-Countdown anzeigen", variable=self.live_event, command=self.toggle_live_event)
        self.live_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 20))

        self.countdown_label = ttk.Label(frame, text="", font=("Segoe UI", 12, "bold"), foreground="#88c0d0")
        self.countdown_label.grid(row=4, column=2, sticky="e")

        frame.columnconfigure(1, weight=1)

        # Start/Stop Buttons in eigenem Frame
        btn_frame = ttk.Frame(self, style="TFrame")
        btn_frame.pack(pady=(0, 10))

        self.start_btn = ttk.Button(btn_frame, text="▶ Backup starten", style="Start.TButton", command=self.start_backup)
        self.start_btn.grid(row=0, column=0, padx=10, ipadx=10)

        self.stop_btn = ttk.Button(btn_frame, text="■ Backup stoppen", style="Stop.TButton", command=self.stop_backup, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=10, ipadx=10)

        # Log Fenster mit Überschrift
        ttk.Label(self, text="Backup-Log:", style="Header.TLabel").pack(anchor="w", padx=pad_x)

        self.log_area = ScrolledText(self, width=90, height=22, font=("Consolas", 11), bg="#1e1e1e", fg="#ddd", insertbackground="#ddd", wrap="word")
        self.log_area.pack(padx=pad_x, pady=(5, 15), fill="both", expand=True)
        self.log_area.config(state="disabled")

        # Statusleiste unten
        self.status_var = tk.StringVar(value="Bereit")
        status_frame = ttk.Frame(self, style="TFrame")
        status_frame.pack(fill="x", side="bottom")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w", background="#222222", foreground="#ddd", font=("Segoe UI", 10))
        self.status_label.pack(fill="x")

        # Bind Validierung
        self.source_dir.trace_add("write", lambda *args: self.validate_entry(self.source_entry, self.source_dir.get()))
        self.backup_dir.trace_add("write", lambda *args: self.validate_entry(self.backup_entry, self.backup_dir.get()))
        self.interval.trace_add("write", lambda *args: self.validate_interval())

    def browse_source(self):
        folder = filedialog.askdirectory(title="Quellordner auswählen")
        if folder:
            self.source_dir.set(folder)
            self.save_settings()

    def browse_backup(self):
        folder = filedialog.askdirectory(title="Backup-Ordner auswählen")
        if folder:
            self.backup_dir.set(folder)
            self.save_settings()

    def validate_entry(self, entry_widget, path):
        if os.path.isdir(path):
            entry_widget.configure(foreground="white")
            return True
        else:
            entry_widget.configure(foreground="red")
            return False

    def validate_interval(self):
        try:
            val = int(self.interval.get())
            if val < 10 or val > 3600:
                raise ValueError
            self.interval_spin.configure(foreground="black")
            return True
        except:
            self.interval_spin.configure(foreground="red")
            return False

    def validate_all(self):
        valid_source = self.validate_entry(self.source_entry, self.source_dir.get())
        valid_backup = self.validate_entry(self.backup_entry, self.backup_dir.get())
        valid_interval = self.validate_interval()
        valid = valid_source and valid_backup and valid_interval
        self.start_btn.config(state="normal" if valid else "disabled")

    def toggle_live_event(self):
        if self.live_event.get():
            self.update_countdown()
        else:
            self.countdown_label.config(text="")

    def reset_countdown(self):
        self.seconds_until_backup = self.interval.get()

    def update_countdown(self):
        if not self.live_event.get():
            self.countdown_label.config(text="")
            return
        if self.is_running:
            self.seconds_until_backup -= 1
            if self.seconds_until_backup < 0:
                self.seconds_until_backup = self.interval.get()
            self.countdown_label.config(text=f"Nächstes Backup in {self.seconds_until_backup} Sek.")
            self.after(1000, self.update_countdown)
        else:
            self.countdown_label.config(text="")

    def start_backup(self):
        self.validate_all()
        if self.is_running:
            return

        self.is_running = True
        self.seconds_until_backup = self.interval.get()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Backup läuft...")
        self.log("🔄 Backup gestartet.")
        self.thread = threading.Thread(target=self.run_backup_loop, daemon=True)
        self.thread.start()
        if self.live_event.get():
            self.update_countdown()

    def stop_backup(self):
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Backup gestoppt.")
        self.countdown_label.config(text="")
        self.log("⛔ Backup gestoppt.")

    def run_backup_loop(self):
        while self.is_running:
            self.perform_backup()
            self.last_backup_time = time.strftime("%d.%m.%Y %H:%M:%S")
            self.seconds_until_backup = self.interval.get()
            for _ in range(self.interval.get()):
                if not self.is_running:
                    break
                time.sleep(1)

    def perform_backup(self):
        src = self.source_dir.get()
        dst = self.backup_dir.get()
        filetypes = [ftype.strip().lower() for ftype in self.filter_types.get().split(",") if ftype.strip()]
        count = 0

        for root, _, files in os.walk(src):
            for file in files:
                if filetypes and not any(file.lower().endswith(ft) for ft in filetypes):
                    continue
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, src)
                dst_file = os.path.join(dst, rel_path)

                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                try:
                    shutil.copy2(src_file, dst_file)
                    count += 1
                except Exception as e:
                    self.log(f"⚠ Fehler beim Kopieren von {src_file}: {e}")

        self.last_backup_count = count
        self.log(f"✅ Backup abgeschlossen. {count} Dateien kopiert.")
        self.status_var.set(f"Letztes Backup: {self.last_backup_time} ({count} Dateien)")

    def log(self, message):
        timestamp = time.strftime("[%H:%M:%S]")
        self.log_area.config(state="normal")
        self.log_area.insert("end", f"{timestamp} {message}\n")
        self.log_area.see("end")
        self.log_area.config(state="disabled")

    def save_settings(self):
        settings = {
            "source_dir": self.source_dir.get(),
            "backup_dir": self.backup_dir.get(),
            "filter_types": self.filter_types.get(),
            "interval": self.interval.get(),
            "live_event": self.live_event.get()
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f)
        except Exception as e:
            self.log(f"⚠ Fehler beim Speichern der Einstellungen: {e}")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    settings = json.load(f)
                    self.source_dir.set(settings.get("source_dir", ""))
                    self.backup_dir.set(settings.get("backup_dir", ""))
                    self.filter_types.set(settings.get("filter_types", ""))
                    self.interval.set(settings.get("interval", 60))
                    self.live_event.set(settings.get("live_event", False))
            except Exception as e:
                self.log(f"⚠ Fehler beim Laden der Einstellungen: {e}")

if __name__ == "__main__":
    app = BackupApp()
    app.mainloop()
