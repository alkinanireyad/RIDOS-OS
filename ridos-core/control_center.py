#!/usr/bin/env python3
"""RIDOS OS Control Center - Main GUI Dashboard"""
import tkinter as tk
import tkinter.ttk as ttk
import subprocess, threading, os, json, socket, time

# Colors
BG   = "#0F0A1E"
BG2  = "#1E1B4B"
BG3  = "#2D1B69"
PURPLE = "#7C3AED"
TEXT = "#E9D5FF"
GREEN  = "#10B981"
YELLOW = "#F59E0B"
RED    = "#EF4444"
CYAN   = "#06B6D4"

API_KEY_FILE = os.path.expanduser("~/.ridos/api_key")

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except:
        return ""

def check_internet():
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except:
        return False

def get_api_key():
    if os.path.exists(API_KEY_FILE):
        return open(API_KEY_FILE).read().strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")

class RIDOSControlCenter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RIDOS OS Control Center v1.0")
        self.root.geometry("900x650")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self._build_ui()
        self._refresh()
        self.root.after(15000, self._auto_refresh)

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG2, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="RIDOS OS", font=("Arial", 22, "bold"),
                 bg=BG2, fg=PURPLE).pack(side="left", padx=20)
        tk.Label(hdr, text="Control Center v1.0 Baghdad",
                 font=("Arial", 12), bg=BG2, fg=TEXT).pack(side="left")
        self.status_label = tk.Label(hdr, text="Initializing...",
                 font=("Arial", 11), bg=BG2, fg=YELLOW)
        self.status_label.pack(side="right", padx=20)

        # Stats row
        stats = tk.Frame(self.root, bg=BG, pady=5)
        stats.pack(fill="x", padx=10)
        self.cpu_label  = self._stat_card(stats, "CPU",  "0%",  PURPLE)
        self.ram_label  = self._stat_card(stats, "RAM",  "0%",  CYAN)
        self.disk_label = self._stat_card(stats, "DISK", "0%",  GREEN)
        self.net_label  = self._stat_card(stats, "NET",  "...", YELLOW)

        # AI message
        self.ai_msg = tk.Label(self.root,
            text="[AI] Analyzing system...",
            font=("Arial", 11), bg=BG, fg=PURPLE,
            wraplength=860, justify="left")
        self.ai_msg.pack(fill="x", padx=20, pady=5)

        # Issues panel
        issues_frame = tk.LabelFrame(self.root, text="System Status",
            font=("Arial", 10, "bold"), bg=BG, fg=TEXT,
            labelanchor="nw", padx=5, pady=5)
        issues_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.issues_text = tk.Text(issues_frame,
            bg=BG2, fg=TEXT, font=("Courier", 10),
            relief="flat", state="disabled", height=10)
        self.issues_text.pack(fill="both", expand=True)

        # Buttons
        btn_frame = tk.Frame(self.root, bg=BG, pady=8)
        btn_frame.pack(fill="x", padx=10)

        buttons = [
            ("Refresh",        self._refresh,        PURPLE),
            ("AI Terminal",    self._open_terminal,  BG3),
            ("Network Scan",   self._run_network,    BG3),
            ("System Info",    self._system_info,    BG3),
            ("Set API Key",    self._set_api_key,    BG3),
        ]
        for text, cmd, color in buttons:
            tk.Button(btn_frame, text=text, command=cmd,
                bg=color, fg=TEXT, font=("Arial", 10, "bold"),
                relief="flat", padx=12, pady=6,
                cursor="hand2").pack(side="left", padx=4)

        # Footer
        tk.Label(self.root,
            text="RIDOS OS v1.0 Baghdad  |  AI-Powered Linux  |  GPL v3",
            font=("Arial", 9), bg=BG, fg="#4B5563").pack(pady=4)

    def _stat_card(self, parent, label, value, color):
        f = tk.Frame(parent, bg=BG2, padx=15, pady=8, relief="flat")
        f.pack(side="left", padx=5, pady=5)
        tk.Label(f, text=label, font=("Arial", 9), bg=BG2, fg="#9CA3AF").pack()
        lbl = tk.Label(f, text=value, font=("Arial", 16, "bold"), bg=BG2, fg=color)
        lbl.pack()
        return lbl

    def _update_text(self, text):
        self.issues_text.config(state="normal")
        self.issues_text.delete("1.0", "end")
        self.issues_text.insert("end", text)
        self.issues_text.config(state="disabled")

    def _refresh(self):
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _auto_refresh(self):
        self._refresh()
        self.root.after(15000, self._auto_refresh)

    def _do_refresh(self):
        try:
            import psutil
            cpu  = psutil.cpu_percent(interval=1)
            ram  = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net  = check_internet()

            cpu_color  = GREEN if cpu < 60 else YELLOW if cpu < 80 else RED
            ram_color  = GREEN if ram.percent < 70 else YELLOW if ram.percent < 85 else RED
            disk_color = GREEN if disk.percent < 80 else YELLOW if disk.percent < 90 else RED

            self.cpu_label.config(text=f"{cpu:.0f}%",   fg=cpu_color)
            self.ram_label.config(text=f"{ram.percent:.0f}%",  fg=ram_color)
            self.disk_label.config(text=f"{disk.percent:.0f}%", fg=disk_color)
            self.net_label.config(text="Online" if net else "Offline",
                                  fg=GREEN if net else RED)

            has_key = bool(get_api_key())
            status = "Online + AI Ready" if net and has_key else \
                     "Online (No API Key)" if net else "Offline Mode"
            self.status_label.config(text=status,
                fg=GREEN if net and has_key else YELLOW)

            # Build status text
            issues = []
            if cpu > 80:  issues.append(f"[CRITICAL] CPU usage: {cpu:.0f}%")
            if ram.percent > 85: issues.append(f"[CRITICAL] RAM usage: {ram.percent:.0f}%")
            if disk.percent > 90: issues.append(f"[WARNING] Disk usage: {disk.percent:.0f}%")
            if not net: issues.append("[WARNING] No internet connection")
            if not has_key: issues.append("[INFO] No API key - run 'Set API Key'")

            info = (
                f"System Status Report\n"
                f"{'='*40}\n"
                f"CPU:  {cpu:.1f}%\n"
                f"RAM:  {ram.percent:.1f}% ({ram.used//1024//1024}MB / {ram.total//1024//1024}MB)\n"
                f"Disk: {disk.percent:.1f}% ({disk.used//1024//1024//1024}GB / {disk.total//1024//1024//1024}GB)\n"
                f"Net:  {'Connected' if net else 'Disconnected'}\n"
                f"AI:   {'Ready' if has_key else 'No API Key'}\n"
                f"{'='*40}\n"
            )
            if issues:
                info += "\nIssues Found:\n"
                for i in issues:
                    info += f"  {i}\n"
            else:
                info += "\n[OK] System is healthy - No issues detected\n"

            self._update_text(info)
            self.ai_msg.config(text="[AI] System analysis complete", fg=GREEN)

        except ImportError:
            self._update_text("psutil not installed. Run: pip3 install psutil")
        except Exception as e:
            self._update_text(f"Error: {e}")

    def _open_terminal(self):
        subprocess.Popen([
            "xfce4-terminal", "--title=RIDOS AI Terminal",
            "-e", "python3 /opt/ridos/bin/ai_features.py"
        ])

    def _run_network(self):
        subprocess.Popen([
            "xfce4-terminal", "--title=RIDOS Network Analyzer",
            "-e", "python3 /opt/ridos/bin/ai_features.py network"
        ])

    def _system_info(self):
        info = run_cmd("neofetch --stdout 2>/dev/null || uname -a")
        self._update_text(info)

    def _set_api_key(self):
        win = tk.Toplevel(self.root)
        win.title("Set API Key")
        win.geometry("500x200")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text="Enter Anthropic API Key:",
                 font=("Arial", 11), bg=BG, fg=TEXT).pack(pady=15)
        entry = tk.Entry(win, width=50, font=("Arial", 10),
                         bg=BG2, fg=TEXT, insertbackground=TEXT, show="*")
        entry.pack(pady=5)
        if os.path.exists(API_KEY_FILE):
            entry.insert(0, open(API_KEY_FILE).read().strip())

        def save():
            key = entry.get().strip()
            if key:
                os.makedirs(os.path.dirname(API_KEY_FILE), exist_ok=True)
                with open(API_KEY_FILE, 'w') as f:
                    f.write(key)
                self.ai_msg.config(text="[AI] API key saved!", fg=GREEN)
                win.destroy()

        tk.Button(win, text="Save Key", command=save,
                  bg=PURPLE, fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=20, pady=8).pack(pady=15)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = RIDOSControlCenter()
    app.run()
