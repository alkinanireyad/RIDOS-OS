#!/usr/bin/env python3
"""
RIDOS OS Control Center
AI-Powered System Dashboard
Fixes: launches correctly from desktop shortcut with sudo
"""
import os, sys, subprocess, threading, json, socket, time

# ── Fix display BEFORE importing GTK ─────────────────────────
if not os.environ.get('DISPLAY'):
    os.environ['DISPLAY'] = ':0'

sudo_user = os.environ.get('SUDO_USER', 'ridos')
if not os.environ.get('XAUTHORITY'):
    for xauth in [
        f'/home/{sudo_user}/.Xauthority',
        '/home/ridos/.Xauthority',
        '/root/.Xauthority',
    ]:
        if os.path.exists(xauth):
            os.environ['XAUTHORITY'] = xauth
            break

# ── Check root - relaunch with sudo -E if needed ─────────────
if os.geteuid() != 0:
    os.execvp('sudo', ['sudo', '-E', 'python3', os.path.abspath(__file__)])
    sys.exit()

# ── Import Tkinter ────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
except ImportError:
    print("ERROR: python3-tk not installed")
    print("Run: sudo apt-get install python3-tk")
    sys.exit(1)

# ── Colors ────────────────────────────────────────────────────
BG     = "#0F0A1E"
BG2    = "#1E1B4B"
BG3    = "#2D1B69"
PURPLE = "#7C3AED"
TEXT   = "#E9D5FF"
GREEN  = "#10B981"
YELLOW = "#F59E0B"
RED    = "#EF4444"
CYAN   = "#06B6D4"

API_KEY_FILE = os.path.expanduser("~/.ridos/api_key")

# ── Safe actions AI can trigger ───────────────────────────────
SAFE_ACTIONS = {
    'clear_cache':       'sync; echo 3 > /proc/sys/vm/drop_caches',
    'system_clean':      'apt-get autoremove -y && apt-get autoclean -y',
    'restart_network':   'systemctl restart NetworkManager',
    'fix_dns':           'echo nameserver 1.1.1.1 > /etc/resolv.conf',
    'enable_firewall':   'ufw enable',
    'kill_zombies':      'kill -9 $(ps aux | awk \'/Z/{print $2}\') 2>/dev/null || true',
}

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except:
        return ""

def check_internet():
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)\
              .connect(("8.8.8.8", 53))
        return True
    except:
        return False

def get_api_key():
    if os.path.exists(API_KEY_FILE):
        return open(API_KEY_FILE).read().strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")

def ask_claude(prompt):
    import urllib.request, urllib.error
    key = get_api_key()
    if not key:
        return None, "No API key"
    try:
        data = json.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 1024,
            "system": (
                "You are RIDOS OS AI. Analyze system data and respond "
                "with JSON only: "
                '{"status":"healthy|warning|critical",'
                '"message":"brief status",'
                '"issues":[{"problem":"desc","action":"safe_action_key"}]}'
                "\naction must be one of: "
                + str(list(SAFE_ACTIONS.keys()))
            ),
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            })
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
            text = resp["content"][0]["text"]
            try:
                return json.loads(text), None
            except:
                return None, text
    except Exception as e:
        return None, str(e)

def local_analysis():
    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=1)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net  = check_internet()
        issues = []
        if cpu > 85:
            issues.append({"problem": "CRITICAL: CPU usage very high",
                           "action": "kill_zombies"})
        elif cpu > 70:
            issues.append({"problem": "WARNING: CPU usage high",
                           "action": None})
        if ram.percent > 85:
            issues.append({"problem": "CRITICAL: RAM usage very high",
                           "action": "clear_cache"})
        elif ram.percent > 70:
            issues.append({"problem": "WARNING: RAM usage high",
                           "action": "clear_cache"})
        if disk.percent > 90:
            issues.append({"problem": "CRITICAL: Disk almost full",
                           "action": "system_clean"})
        if not net:
            issues.append({"problem": "WARNING: No internet connection",
                           "action": "restart_network"})
        msg = "System healthy" if not issues else f"{len(issues)} issue(s) found"
        return {
            "status": "critical" if any("CRITICAL" in i["problem"] for i in issues)
                      else "warning" if issues else "healthy",
            "message": msg,
            "issues": issues,
            "cpu": cpu, "ram": ram.percent,
            "disk": disk.percent, "net": net,
        }
    except ImportError:
        return {"status": "warning", "message": "psutil not installed",
                "issues": [], "cpu": 0, "ram": 0, "disk": 0, "net": False}

class RIDOSControlCenter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RIDOS OS Control Center v1.0")
        self.root.geometry("900x660")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self._build_ui()
        self.root.after(500, self._refresh)
        self.root.after(15000, self._auto_refresh)

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG2, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="RIDOS OS",
                 font=("Arial", 22, "bold"),
                 bg=BG2, fg=PURPLE).pack(side="left", padx=20)
        tk.Label(hdr, text="Control Center v1.0 Baghdad",
                 font=("Arial", 12),
                 bg=BG2, fg=TEXT).pack(side="left")
        self.status_lbl = tk.Label(hdr, text="Starting...",
                 font=("Arial", 11), bg=BG2, fg=YELLOW)
        self.status_lbl.pack(side="right", padx=20)

        # Stats row
        stats = tk.Frame(self.root, bg=BG, pady=6)
        stats.pack(fill="x", padx=10)
        self.cpu_lbl  = self._stat(stats, "CPU",  "0%",  PURPLE)
        self.ram_lbl  = self._stat(stats, "RAM",  "0%",  CYAN)
        self.disk_lbl = self._stat(stats, "DISK", "0%",  GREEN)
        self.net_lbl  = self._stat(stats, "NET",  "...", YELLOW)

        # AI message
        self.ai_msg = tk.Label(self.root,
            text="Analyzing system...",
            font=("Arial", 11), bg=BG, fg=PURPLE,
            wraplength=860, justify="left")
        self.ai_msg.pack(fill="x", padx=20, pady=4)

        # Issues panel
        issues_frame = tk.LabelFrame(self.root,
            text="System Status",
            font=("Arial", 10, "bold"),
            bg=BG, fg=TEXT, labelanchor="nw",
            padx=5, pady=5)
        issues_frame.pack(fill="both", expand=True,
                          padx=10, pady=4)
        self.issues_text = tk.Text(issues_frame,
            bg=BG2, fg=TEXT, font=("Courier", 10),
            relief="flat", state="disabled", height=12)
        self.issues_text.pack(fill="both", expand=True)

        # Buttons
        btn_frame = tk.Frame(self.root, bg=BG, pady=8)
        btn_frame.pack(fill="x", padx=10)
        for txt, cmd, color in [
            ("Refresh",       self._refresh,       PURPLE),
            ("AI Terminal",   self._ai_terminal,   BG3),
            ("Network Scan",  self._network_scan,  BG3),
            ("System Info",   self._system_info,   BG3),
            ("Set API Key",   self._set_api_key,   BG3),
        ]:
            tk.Button(btn_frame, text=txt, command=cmd,
                bg=color, fg=TEXT,
                font=("Arial", 10, "bold"),
                relief="flat", padx=12, pady=6,
                cursor="hand2").pack(side="left", padx=4)

        # Footer
        tk.Label(self.root,
            text="RIDOS OS v1.0 Baghdad  |  AI-Powered Linux "
                 "for IT & Communications  |  GPL v3",
            font=("Arial", 9), bg=BG,
            fg="#4B5563").pack(pady=4)

    def _stat(self, parent, label, value, color):
        f = tk.Frame(parent, bg=BG2, padx=16, pady=8)
        f.pack(side="left", padx=5, pady=5)
        tk.Label(f, text=label, font=("Arial", 9),
                 bg=BG2, fg="#9CA3AF").pack()
        lbl = tk.Label(f, text=value,
                       font=("Arial", 16, "bold"),
                       bg=BG2, fg=color)
        lbl.pack()
        return lbl

    def _update_text(self, text):
        self.issues_text.config(state="normal")
        self.issues_text.delete("1.0", "end")
        self.issues_text.insert("end", text)
        self.issues_text.config(state="disabled")

    def _refresh(self):
        threading.Thread(target=self._do_refresh,
                         daemon=True).start()

    def _auto_refresh(self):
        self._refresh()
        self.root.after(15000, self._auto_refresh)

    def _do_refresh(self):
        try:
            data = local_analysis()
            cpu  = data.get('cpu', 0)
            ram  = data.get('ram', 0)
            disk = data.get('disk', 0)
            net  = data.get('net', False)

            cpu_c  = GREEN if cpu  < 60 else YELLOW if cpu  < 80 else RED
            ram_c  = GREEN if ram  < 70 else YELLOW if ram  < 85 else RED
            disk_c = GREEN if disk < 80 else YELLOW if disk < 90 else RED

            self.root.after(0, self.cpu_lbl.config,
                            {"text": f"{cpu:.0f}%", "fg": cpu_c})
            self.root.after(0, self.ram_lbl.config,
                            {"text": f"{ram:.0f}%", "fg": ram_c})
            self.root.after(0, self.disk_lbl.config,
                            {"text": f"{disk:.0f}%", "fg": disk_c})
            self.root.after(0, self.net_lbl.config,
                            {"text": "Online" if net else "Offline",
                             "fg": GREEN if net else RED})

            key  = get_api_key()
            stat = ("Online + AI Ready" if net and key
                    else "Online - No API Key" if net
                    else "Offline Mode")
            self.root.after(0, self.status_lbl.config,
                            {"text": stat,
                             "fg": GREEN if net and key else YELLOW})

            issues = data.get('issues', [])
            info = (
                f"System Status\n{'='*45}\n"
                f"CPU:    {cpu:.1f}%\n"
                f"RAM:    {ram:.1f}%\n"
                f"Disk:   {disk:.1f}%\n"
                f"Network: {'Connected' if net else 'Disconnected'}\n"
                f"AI:     {'Ready' if key else 'No API key'}\n"
                f"{'='*45}\n"
            )
            if issues:
                info += "\nIssues Found:\n"
                for i in issues:
                    info += f"  {i['problem']}\n"
                    if i.get('action'):
                        info += f"    -> Fix: {i['action']}\n"
            else:
                info += "\n[OK] System is healthy\n"

            self.root.after(0, self._update_text, info)
            self.root.after(0, self.ai_msg.config,
                            {"text": f"Status: {data['message']}",
                             "fg": GREEN if data['status']=='healthy'
                                   else YELLOW if data['status']=='warning'
                                   else RED})

        except Exception as e:
            self.root.after(0, self._update_text, f"Error: {e}")

    def _ai_terminal(self):
        subprocess.Popen([
            'xfce4-terminal', '--title=RIDOS AI Terminal',
            '--hold', '-e',
            'python3 /opt/ridos/bin/ai_features.py'
        ])

    def _network_scan(self):
        subprocess.Popen([
            'xfce4-terminal', '--title=Network Analyzer',
            '--hold', '-e',
            'python3 /opt/ridos/bin/ai_features.py 3'
        ])

    def _system_info(self):
        info = run_cmd("neofetch --stdout 2>/dev/null || uname -a")
        self._update_text(info)

    def _set_api_key(self):
        key = simpledialog.askstring(
            "Set API Key",
            "Enter Anthropic API Key:",
            parent=self.root,
            show='*')
        if key and key.strip():
            os.makedirs(os.path.dirname(API_KEY_FILE),
                        exist_ok=True)
            with open(API_KEY_FILE, 'w') as f:
                f.write(key.strip())
            messagebox.showinfo("Saved",
                "API key saved successfully!")
            self.ai_msg.config(
                text="API key saved!",
                fg=GREEN)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = RIDOSControlCenter()
    app.run()
