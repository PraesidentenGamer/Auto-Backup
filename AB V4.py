import os
import shutil
import time
import threading
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

SETTINGS_FILE = "settings.json"

class BackupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Automatischer Datei-Backup")
        self.geometry("750x750")
        self.minsize(700, 600)
        self.resizable(True, True)

        # Variablen
        self.source_dir = tk.StringVar()
        self.backup_dir = tk.StringVar()
        self.filter_types = tk.StringVar()
        self.interval = tk.IntVar(value=60)
        self.is_running = False
        self.thread = None

        self.live_event = tk.BooleanVar(value=False)
        self.seconds_until_backup = self.interval.get()

        self.load_settings()

        self.create_widgets()

        # Style anpassen (optional, wenn ttk Themes verfügbar)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

    def create_widgets(self):
        pad = 12
        label_width = 30

        # Quellordner auswählen
        ttk.Label(self, text="Quellordner:", width=label_width).grid(row=0, column=0, sticky="w", padx=pad, pady=pad)
        ttk.Entry(self, textvariable=self.source_dir, width=60).grid(row=0, column=1, padx=pad, pady=pad)
        ttk.Button(self, text="Durchsuchen", command=self.browse_source).grid(row=0, column=2, padx=pad, pady=pad)

        # Backup-Ordner auswählen
        ttk.Label(self, text="Backup-Ordner:", width=label_width).grid(row=1, column=0, sticky="w", padx=pad, pady=pad)
        ttk.Entry(self, textvariable=self.backup_dir, width=60).grid(row=1, column=1, padx=pad, pady=pad)
        ttk.Button(self, text="Durchsuchen", command=self.browse_backup).grid(row=1, column=2, padx=pad, pady=pad)

        # Dateitypen-Filter
        ttk.Label(self, text="Dateitypen (kommagetrennt, z.B. .txt,.pdf):", width=label_width).grid(row=2, column=0, sticky="w", padx=pad, pady=pad)
        ttk.Entry(self, textvariable=self.filter_types, width=60).grid(row=2, column=1, padx=pad, pady=pad, columnspan=2)

        # Intervall einstellen
        ttk.Label(self, text="Backup-Intervall (Sekunden):", width=label_width).grid(row=3, column=0, sticky="w", padx=pad, pady=pad)
        interval_spin = ttk.Spinbox(self, from_=10, to=3600, textvariable=self.interval, width=10, command=self.reset_countdown)
        interval_spin.grid(row=3, column=1, sticky="w", padx=pad, pady=pad)

        # Live-Event Checkbox
        live_check = ttk.Checkbutton(self, text="Live-Event (Countdown anzeigen)", variable=self.live_event, command=self.toggle_live_event)
        live_check.grid(row=4, column=0, columnspan=2, sticky="w", padx=pad, pady=pad)

        # Countdown Label (nur sichtbar, wenn Live-Event an)
        self.countdown_label = ttk.Label(self, text="", font=("Segoe UI", 10, "bold"))
        self.countdown_label.grid(row=4, column=2, sticky="e", padx=pad, pady=pad)

        # Start / Stop Buttons
        self.start_btn = ttk.Button(self, text="Backup starten", command=self.start_backup)
        self.start_btn.grid(row=5, column=1, sticky="w", padx=pad, pady=pad)

        self.stop_btn = ttk.Button(self, text="Backup stoppen", command=self.stop_backup, state="disabled")
        self.stop_btn.grid(row=5, column=1, sticky="e", padx=pad, pady=pad)

        # Log Fenster
        ttk.Label(self, text="Backup-Log:").grid(row=6, column=0, sticky="nw", padx=pad, pady=pad)
        self.log_area = scrolledtext.ScrolledText(self, width=85, height=20, state='disabled', font=("Consolas", 10))
        self.log_area.grid(row=7, column=0, columnspan=3, padx=pad, pady=pad, sticky="nsew")

        # Grid - Damit Log-Fenster sich ausdehnt beim Fenster vergrößern
        self.grid_rowconfigure(7, weight=1)
        self.grid_columnconfigure(1, weight=1)

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_dir.set(folder)
            self.save_settings()

    def browse_backup(self):
        folder = filedialog.askdirectory()
        if folder:
            self.backup_dir.set(folder)
            self.save_settings()

    def log(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def start_backup(self):
        if not os.path.isdir(self.source_dir.get()):
            messagebox.showerror("Fehler", "Quellordner ist ungültig.")
            return
        if not os.path.isdir(self.backup_dir.get()):
            messagebox.showerror("Fehler", "Backup-Ordner ist ungültig.")
            return
        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.reset_countdown()
        self.log("Backup gestartet.")
        self.thread = threading.Thread(target=self.backup_loop, daemon=True)
        self.thread.start()
        if self.live_event.get():
            self.update_countdown()

        # Einstellungen speichern
        self.save_settings()

    def stop_backup(self):
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.countdown_label.config(text="")
        self.log("Backup gestoppt.")

    def backup_loop(self):
        while self.is_running:
            start_time = time.time()
            self.backup_files()
            elapsed = time.time() - start_time
            wait_time = max(0, self.interval.get() - elapsed)

            # Reset Countdown nach Backup
            self.seconds_until_backup = wait_time

            # Warten mit Countdown-Updates
            while self.seconds_until_backup > 0 and self.is_running:
                time.sleep(1)
                self.seconds_until_backup -= 1

    def backup_files(self):
        source = self.source_dir.get()
        backup = self.backup_dir.get()
        filter_list = [ft.strip().lower() for ft in self.filter_types.get().split(",") if ft.strip()]
        count = 0

        for foldername, subfolders, filenames in os.walk(source):
            backup_folder = foldername.replace(source, backup)
            if not os.path.exists(backup_folder):
                try:
                    os.makedirs(backup_folder)
                except Exception as e:
                    self.log(f"Fehler beim Erstellen von Ordner {backup_folder}: {e}")
                    continue

            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if filter_list and ext not in filter_list:
                    continue  # Datei nicht sichern, wenn Filter gesetzt

                source_file = os.path.join(foldername, filename)
                backup_file = os.path.join(backup_folder, filename)

                try:
                    if (not os.path.exists(backup_file)) or \
                        (os.path.getmtime(source_file) > os.path.getmtime(backup_file)):
                        shutil.copy2(source_file, backup_file)
                        count += 1
                        self.log(f"Datei gesichert: {source_file}")
                except Exception as e:
                    self.log(f"Fehler beim Kopieren von {source_file}: {e}")

        self.log(f"Backup-Durchlauf abgeschlossen. {count} Datei(en) gesichert.")

    def reset_countdown(self):
        self.seconds_until_backup = self.interval.get()
        if self.live_event.get():
            self.update_countdown()

    def toggle_live_event(self):
        if self.live_event.get():
            self.update_countdown()
        else:
            self.countdown_label.config(text="")

    def update_countdown(self):
        if not self.live_event.get() or not self.is_running:
            self.countdown_label.config(text="")
            return

        total_seconds = int(self.seconds_until_backup)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"

        self.countdown_label.config(text=f"Nächste Sicherung in: {time_str}")
        self.after(1000, self.update_countdown)

    def load_settings(self):
        """Lade Einstellungen aus JSON-Datei"""
        if os.path.isfile(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.source_dir.set(data.get("source_dir", ""))
                    self.backup_dir.set(data.get("backup_dir", ""))
                    self.filter_types.set(data.get("filter_types", ""))
                    self.interval.set(data.get("interval", 60))
                    self.live_event.set(data.get("live_event", False))
            except Exception as e:
                print(f"Fehler beim Laden der Einstellungen: {e}")

    def save_settings(self):
        """Speichere Einstellungen in JSON-Datei"""
        data = {
            "source_dir": self.source_dir.get(),
            "backup_dir": self.backup_dir.get(),
            "filter_types": self.filter_types.get(),
            "interval": self.interval.get(),
            "live_event": self.live_event.get(),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Fehler beim Speichern der Einstellungen: {e}")


if __name__ == "__main__":
    app = BackupApp()
    app.mainloop()
