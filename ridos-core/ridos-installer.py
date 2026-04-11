#!/usr/bin/env python3
"""
RIDOS OS Installer - Disk Manager + OS Installer
Uses Tkinter (proven to work with sudo in XFCE)
Run: sudo python3 /opt/ridos/bin/ridos-installer.py
"""
# ── Fix DISPLAY before any import ────────────────────────────
import os, sys, subprocess

os.environ.setdefault('DISPLAY', ':0')
_sudo_user = os.environ.get('SUDO_USER', 'ridos')
if not os.environ.get('XAUTHORITY'):
    for _xa in [f'/home/{_sudo_user}/.Xauthority',
                '/home/ridos/.Xauthority',
                '/root/.Xauthority']:
        if os.path.exists(_xa):
            os.environ['XAUTHORITY'] = _xa
            break

# Allow root to connect to X display
subprocess.run('xhost +SI:localuser:root 2>/dev/null || true',
               shell=True, capture_output=True)

# Re-exec with sudo if not root
if os.geteuid() != 0:
    os.execvp('sudo', ['sudo', '-E', 'python3', os.path.abspath(__file__)])
    sys.exit()

# ── Tkinter import ────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
except ImportError:
    print("ERROR: python3-tk not installed")
    print("Run: sudo apt-get install python3-tk")
    sys.exit(1)

import threading, json, time, shutil, random

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
GRAY   = "#6B7280"

# ── Helpers ───────────────────────────────────────────────────
def run_cmd(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "Timed out", 1
    except Exception as e:
        return str(e), 1

def get_disks():
    out, _ = run_cmd("lsblk -d -b -o NAME,SIZE,MODEL,TYPE -n 2>/dev/null")
    disks = []
    for line in out.strip().split('\n'):
        if not line.strip(): continue
        parts = line.split(None, 3)
        if len(parts) < 4: continue
        name, size, model, dtype = parts[0], parts[1], parts[2], parts[3]
        if dtype.strip() != 'disk' or 'loop' in name: continue
        try:
            size_gb = int(size) / 1024**3
        except:
            size_gb = 0
        disks.append({
            'name': name,
            'path': f'/dev/{name}',
            'size': f'{size_gb:.1f} GB',
            'model': model.strip() or 'Unknown',
        })
    return disks

def get_partitions(disk_path):
    out, _ = run_cmd(
        f"lsblk -b -o NAME,SIZE,FSTYPE,MOUNTPOINT -n {disk_path} 2>/dev/null")
    parts = []
    disk_name = os.path.basename(disk_path)
    for line in out.strip().split('\n'):
        if not line.strip(): continue
        cols = line.split(None, 3)
        name = cols[0].lstrip('|-`├└─')
        if name == disk_name: continue
        size = cols[1] if len(cols) > 1 else '0'
        fstype = cols[2] if len(cols) > 2 else ''
        mount  = cols[3].strip() if len(cols) > 3 else ''
        try:
            size_gb = int(size) / 1024**3
        except:
            size_gb = 0
        parts.append({
            'name': name, 'path': f'/dev/{name}',
            'size': f'{size_gb:.1f} GB',
            'fstype': fstype, 'mount': mount,
        })
    return parts

def find_squashfs():
    paths = [
        '/run/live/medium/live/filesystem.squashfs',
        '/lib/live/mount/medium/live/filesystem.squashfs',
        '/cdrom/live/filesystem.squashfs',
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    out, _ = run_cmd(
        "find /run /lib/live /cdrom /media "
        "-name 'filesystem.squashfs' 2>/dev/null | head -1")
    return out.strip() if out.strip() else None


# ════════════════════════════════════════════════════════════════
class RIDOSInstaller:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RIDOS OS — Disk Manager & Installer")
        self.root.geometry("980x660")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self.selected_disk = None
        self.install_data  = {
            'disk': None, 'username': 'ridos',
            'password': 'ridos', 'hostname': 'ridos-os',
            'timezone': 'Asia/Baghdad', 'fullname': 'RIDOS User',
        }

        self._build_ui()

    # ── Layout ─────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG2, pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="RIDOS OS",
                 font=('Arial', 20, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left', padx=16)
        tk.Label(hdr, text="Disk Manager & Installer v1.0",
                 font=('Arial', 11),
                 bg=BG2, fg=TEXT).pack(side='left')

        # Sidebar + Content
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)

        # Sidebar
        sidebar = tk.Frame(body, bg=BG2, width=160)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="MENU", font=('Arial', 9),
                 bg=BG2, fg=GRAY).pack(pady=(16, 4))

        self._nav_btns = {}
        for key, label in [('disks',   '  Disk Manager'),
                            ('install', '  Install OS'),
                            ('about',   '  About')]:
            b = tk.Button(sidebar, text=label,
                          font=('Arial', 11), anchor='w',
                          bg=BG2, fg=TEXT, relief='flat',
                          activebackground=BG3,
                          cursor='hand2',
                          command=lambda k=key: self._nav(k))
            b.pack(fill='x', pady=2, padx=4)
            self._nav_btns[key] = b

        sep = tk.Frame(body, bg='#2D1B69', width=1)
        sep.pack(side='left', fill='y')

        # Content frame
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side='left', fill='both', expand=True)

        self._nav('disks')

    def _nav(self, page):
        for k, b in self._nav_btns.items():
            b.config(bg=BG3 if k == page else BG2,
                     fg=TEXT if k == page else GRAY)
        for w in self.content.winfo_children():
            w.destroy()
        {'disks': self._page_disks,
         'install': self._page_install,
         'about': self._page_about}[page]()

    # ── Helper widgets ─────────────────────────────────────────
    def _btn(self, parent, text, cmd, color=PURPLE, fg=TEXT, **kw):
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg=fg,
                         font=('Arial', 10, 'bold'),
                         relief='flat', padx=10, pady=5,
                         cursor='hand2', **kw)

    def _lbl(self, parent, text, size=10, fg=TEXT, **kw):
        return tk.Label(parent, text=text,
                        font=('Arial', size), bg=BG, fg=fg, **kw)

    def _card(self, parent):
        f = tk.Frame(parent, bg=BG2, padx=10, pady=8)
        return f

    # ═══════════════════════════════════════════════════════════
    # PAGE: Disk Manager
    # ═══════════════════════════════════════════════════════════
    def _page_disks(self):
        # Title bar
        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        tk.Label(top, text="Disk Manager",
                 font=('Arial', 15, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left', padx=14)
        self._btn(top, "Refresh", self._refresh_disks,
                  BG3).pack(side='right', padx=8)

        pane = tk.Frame(self.content, bg=BG)
        pane.pack(fill='both', expand=True, padx=8, pady=8)

        # Left: disk list
        left = tk.Frame(pane, bg=BG)
        left.pack(side='left', fill='y', padx=(0, 6))

        tk.Label(left, text="Storage Devices",
                 font=('Arial', 10, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w')

        self.disk_listbox = tk.Listbox(
            left, bg=BG2, fg=TEXT,
            selectbackground=PURPLE,
            font=('Courier', 10),
            relief='flat', width=32, height=14,
            activestyle='none')
        self.disk_listbox.pack(fill='both', expand=True, pady=4)
        self.disk_listbox.bind('<<ListboxSelect>>', self._on_disk_select)

        # Disk action buttons
        dbtns = tk.Frame(left, bg=BG)
        dbtns.pack(fill='x')
        self._btn(dbtns, "New Part Table",
                  self._new_part_table, BG3).pack(side='left', padx=2)
        self._btn(dbtns, "Format Disk",
                  self._format_disk, RED).pack(side='left', padx=2)

        # Right: partition details
        right = tk.Frame(pane, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        tk.Label(right, text="Partitions",
                 font=('Arial', 10, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w')

        # Partition table
        cols = ('Device', 'Size', 'FS Type', 'Mount')
        self.part_tree = ttk.Treeview(
            right, columns=cols,
            show='headings', height=10)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Treeview',
                        background=BG2, foreground=TEXT,
                        fieldbackground=BG2, rowheight=24)
        style.configure('Treeview.Heading',
                        background=BG3, foreground=CYAN,
                        font=('Arial', 9, 'bold'))
        style.map('Treeview',
                  background=[('selected', PURPLE)])
        for col, w in zip(cols, [120, 80, 90, 140]):
            self.part_tree.heading(col, text=col)
            self.part_tree.column(col, width=w, anchor='w')
        self.part_tree.pack(fill='both', expand=True, pady=4)

        # Partition action buttons
        pbtns = tk.Frame(right, bg=BG)
        pbtns.pack(fill='x')
        self._btn(pbtns, "Create EXT4",
                  self._create_ext4, PURPLE).pack(side='left', padx=2)
        self._btn(pbtns, "Delete Last",
                  self._delete_part, RED).pack(side='left', padx=2)
        self._btn(pbtns, "Mount/Unmount",
                  self._toggle_mount, BG3).pack(side='left', padx=2)

        # Status bar
        self.disk_status = tk.Label(
            self.content, text="Select a disk",
            font=('Arial', 9), bg=BG2, fg=GRAY,
            anchor='w', pady=4)
        self.disk_status.pack(fill='x', padx=8, pady=(0, 4))

        self._refresh_disks()

    def _refresh_disks(self):
        self._disks = get_disks()
        self.disk_listbox.delete(0, 'end')
        if not self._disks:
            self.disk_listbox.insert('end', '  No disks found')
            return
        for d in self._disks:
            self.disk_listbox.insert(
                'end',
                f"  /dev/{d['name']}  {d['size']:>8}  {d['model'][:14]}")

    def _on_disk_select(self, event):
        sel = self.disk_listbox.curselection()
        if not sel: return
        idx = sel[0]
        if idx >= len(self._disks): return
        self.selected_disk = self._disks[idx]
        self.install_data['disk'] = self.selected_disk['path']
        self.disk_status.config(
            text=f"  {self.selected_disk['path']}  "
                 f"{self.selected_disk['size']}  "
                 f"{self.selected_disk['model']}")
        self._refresh_parts()

    def _refresh_parts(self):
        for row in self.part_tree.get_children():
            self.part_tree.delete(row)
        if not self.selected_disk: return
        parts = get_partitions(self.selected_disk['path'])
        if not parts:
            self.part_tree.insert('', 'end',
                values=('No partitions', '', '', ''))
            return
        for p in parts:
            self.part_tree.insert('', 'end', values=(
                f"/dev/{p['name']}", p['size'],
                p['fstype'] or '-', p['mount'] or '-'))

    def _new_part_table(self):
        if not self.selected_disk:
            messagebox.showwarning("", "Select a disk first"); return
        disk = self.selected_disk['path']
        if not messagebox.askyesno("Confirm",
                f"Create new GPT table on {disk}?\n"
                "This erases all partitions!"):
            return
        out, code = run_cmd(f"parted -s {disk} mklabel gpt")
        messagebox.showinfo("Done",
            f"GPT table created on {disk}" if code == 0
            else f"Failed:\n{out}")
        self._refresh_parts()

    def _format_disk(self):
        if not self.selected_disk:
            messagebox.showwarning("", "Select a disk first"); return
        disk = self.selected_disk['path']
        if not messagebox.askyesno("⚠ WARNING",
                f"ERASE ALL DATA on {disk}?\n"
                "This cannot be undone!"):
            return
        out, code = run_cmd(
            f"parted -s {disk} mklabel gpt && "
            f"mkfs.ext4 -F {disk}")
        messagebox.showinfo("Done",
            "Disk formatted" if code == 0 else f"Failed:\n{out}")
        self._refresh_parts()

    def _create_ext4(self):
        if not self.selected_disk:
            messagebox.showwarning("", "Select a disk first"); return
        disk = self.selected_disk['path']
        cmds = [
            f"parted -s {disk} mkpart primary ext4 0% 100%",
            f"partprobe {disk}", "sleep 1",
            f"mkfs.ext4 -F {disk}1 2>/dev/null || "
            f"mkfs.ext4 -F {disk}p1 2>/dev/null || true",
        ]
        for cmd in cmds:
            run_cmd(cmd)
        messagebox.showinfo("Done", "EXT4 partition created")
        self._refresh_parts()

    def _delete_part(self):
        if not self.selected_disk:
            messagebox.showwarning("", "Select a disk first"); return
        disk = self.selected_disk['path']
        parts = get_partitions(disk)
        if not parts:
            messagebox.showinfo("", "No partitions to delete"); return
        if not messagebox.askyesno("Confirm",
                f"Delete last partition on {disk}?"):
            return
        out, code = run_cmd(f"parted -s {disk} rm {len(parts)}")
        messagebox.showinfo("Done",
            "Partition deleted" if code == 0 else f"Failed:\n{out}")
        self._refresh_parts()

    def _toggle_mount(self):
        if not self.selected_disk:
            messagebox.showwarning("", "Select a disk first"); return
        parts = get_partitions(self.selected_disk['path'])
        mounted = [p for p in parts if p['mount']]
        if mounted:
            for p in mounted:
                run_cmd(f"umount {p['path']} 2>/dev/null || true")
            messagebox.showinfo("Done", "Partitions unmounted")
        else:
            for p in parts:
                if p['fstype'] and p['fstype'] != 'swap':
                    mnt = f"/mnt/{p['name']}"
                    run_cmd(f"mkdir -p {mnt} && "
                            f"mount {p['path']} {mnt} 2>/dev/null || true")
            messagebox.showinfo("Done", "Partitions mounted to /mnt/")
        self._refresh_parts()

    # ═══════════════════════════════════════════════════════════
    # PAGE: Install OS — 4-step wizard
    # ═══════════════════════════════════════════════════════════
    def _page_install(self):
        self._install_step = 0

        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        self._step_label = tk.Label(
            top, text="Step 1 of 4: Select Disk",
            font=('Arial', 14, 'bold'),
            bg=BG2, fg=PURPLE)
        self._step_label.pack(side='left', padx=14)

        # Step indicator
        self._step_bar = tk.Frame(self.content, bg=BG, pady=4)
        self._step_bar.pack(fill='x', padx=10)
        self._step_indicators = []
        for i, name in enumerate(['Disk', 'User', 'Settings', 'Confirm']):
            f = tk.Frame(self._step_bar, bg=BG)
            f.pack(side='left', expand=True, fill='x')
            c = tk.Label(f, text=f"{i+1}. {name}",
                         font=('Arial', 9),
                         bg=BG, fg=GRAY)
            c.pack()
            self._step_indicators.append(c)

        tk.Frame(self.content, bg=BG2, height=1).pack(fill='x')

        # Wizard pages frame
        self._wizard_frame = tk.Frame(self.content, bg=BG)
        self._wizard_frame.pack(fill='both', expand=True,
                                padx=16, pady=8)

        # Navigation buttons
        nav = tk.Frame(self.content, bg=BG2, pady=8)
        nav.pack(fill='x', side='bottom')
        self._back_btn = self._btn(nav, "Back",
                                   self._install_back, BG3)
        self._back_btn.pack(side='left', padx=12)
        self._next_btn = self._btn(nav, "Next",
                                   self._install_next, PURPLE)
        self._next_btn.pack(side='right', padx=12)

        self._show_install_step(0)

    def _show_install_step(self, step):
        self._install_step = step
        for w in self._wizard_frame.winfo_children():
            w.destroy()

        names = ['Disk', 'User', 'Settings', 'Confirm']
        for i, ind in enumerate(self._step_indicators):
            if i < step:
                ind.config(fg=GREEN)
            elif i == step:
                ind.config(fg=PURPLE,
                           font=('Arial', 9, 'bold'))
            else:
                ind.config(fg=GRAY,
                           font=('Arial', 9))

        self._step_label.config(
            text=f"Step {step+1} of 4: {names[step]}")

        [self._install_step_disk,
         self._install_step_user,
         self._install_step_settings,
         self._install_step_confirm][step]()

        self._back_btn.config(state='normal' if step > 0
                              else 'disabled')
        if step == 3:
            self._next_btn.config(
                text="INSTALL NOW", bg=RED)
        else:
            self._next_btn.config(
                text="Next →", bg=PURPLE)

    def _install_back(self):
        if self._install_step > 0:
            self._show_install_step(self._install_step - 1)

    def _install_next(self):
        if self._install_step < 3:
            self._show_install_step(self._install_step + 1)
        else:
            if messagebox.askyesno(
                    "⚠ FINAL WARNING",
                    f"Install RIDOS OS to "
                    f"{self.install_data['disk']}?\n\n"
                    "ALL DATA WILL BE PERMANENTLY ERASED!\n\n"
                    "This cannot be undone."):
                self._start_install()

    def _install_step_disk(self):
        f = self._wizard_frame
        tk.Label(f, text="Select the disk to install RIDOS OS on:",
                 font=('Arial', 11), bg=BG, fg=TEXT).pack(
                     anchor='w', pady=(0, 8))
        tk.Label(f,
                 text="⚠  All data on the selected disk will be erased!",
                 font=('Arial', 10), bg=BG, fg=YELLOW).pack(
                     anchor='w', pady=(0, 12))

        disks = get_disks()
        if not disks:
            tk.Label(f, text="No disks found!",
                     font=('Arial', 11), bg=BG, fg=RED).pack()
            return

        self._disk_var = tk.StringVar()
        for d in disks:
            text = (f"/dev/{d['name']}  —  {d['size']}  "
                    f"—  {d['model']}")
            rb = tk.Radiobutton(
                f, text=text,
                variable=self._disk_var,
                value=d['path'],
                font=('Arial', 11),
                bg=BG, fg=TEXT,
                selectcolor=BG3,
                activebackground=BG,
                command=lambda p=d['path']:
                    self.install_data.__setitem__('disk', p))
            rb.pack(anchor='w', pady=3)
            if not self.install_data['disk']:
                rb.invoke()

        tk.Label(f,
                 text="\nPartition layout that will be created:\n"
                      "  1.  512 MB   EFI  (FAT32)\n"
                      "  2.    4 GB   Swap\n"
                      "  3. Remaining Root  (EXT4)",
                 font=('Courier', 9),
                 bg=BG, fg=GRAY,
                 justify='left').pack(anchor='w', pady=12)

    def _install_step_user(self):
        f = self._wizard_frame
        tk.Label(f, text="User Account",
                 font=('Arial', 12, 'bold'),
                 bg=BG, fg=PURPLE).pack(anchor='w', pady=(0, 12))

        self._user_entries = {}
        fields = [
            ('Full Name',  'fullname',  'RIDOS User', False),
            ('Username',   'username',  'ridos',      False),
            ('Password',   'password',  'ridos',      True),
            ('Hostname',   'hostname',  'ridos-os',   False),
        ]
        for label, key, default, secret in fields:
            row = tk.Frame(f, bg=BG)
            row.pack(fill='x', pady=5)
            tk.Label(row, text=f"{label}:",
                     font=('Arial', 10),
                     bg=BG, fg=TEXT,
                     width=12, anchor='e').pack(side='left')
            e = tk.Entry(row, font=('Arial', 11),
                         bg=BG2, fg=TEXT,
                         insertbackground=TEXT,
                         relief='flat', bd=4, width=28)
            e.insert(0, self.install_data.get(key, default))
            if secret:
                e.config(show='*')
            e.pack(side='left', padx=8)
            e.bind('<KeyRelease>',
                   lambda ev, k=key:
                   self.install_data.__setitem__(
                       k, ev.widget.get()))
            self._user_entries[key] = e

    def _install_step_settings(self):
        f = self._wizard_frame
        tk.Label(f, text="System Settings",
                 font=('Arial', 12, 'bold'),
                 bg=BG, fg=PURPLE).pack(anchor='w', pady=(0, 12))

        row = tk.Frame(f, bg=BG)
        row.pack(fill='x', pady=5)
        tk.Label(row, text="Timezone:",
                 font=('Arial', 10),
                 bg=BG, fg=TEXT,
                 width=12, anchor='e').pack(side='left')

        out, _ = run_cmd(
            "timedatectl list-timezones 2>/dev/null | head -100")
        zones = (out.strip().split('\n')
                 if out.strip()
                 else ["Asia/Baghdad", "UTC"])

        self._tz_var = tk.StringVar(
            value=self.install_data.get('timezone', 'Asia/Baghdad'))
        tz_combo = ttk.Combobox(row,
                                textvariable=self._tz_var,
                                values=zones,
                                font=('Arial', 10),
                                width=30, state='readonly')
        tz_combo.pack(side='left', padx=8)
        tz_combo.bind('<<ComboboxSelected>>',
                      lambda e: self.install_data.__setitem__(
                          'timezone', self._tz_var.get()))

    def _install_step_confirm(self):
        f = self._wizard_frame
        tk.Label(f, text="Review before installing:",
                 font=('Arial', 11, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w', pady=(0, 10))

        d = self.install_data
        details = (
            f"  Disk:      {d.get('disk', 'NOT SET')}\n"
            f"  Username:  {d.get('username', '')}\n"
            f"  Hostname:  {d.get('hostname', '')}\n"
            f"  Timezone:  {d.get('timezone', '')}\n"
        )
        tk.Label(f, text=details,
                 font=('Courier', 11),
                 bg=BG2, fg=TEXT,
                 justify='left',
                 padx=12, pady=10).pack(
                     fill='x', pady=8)

        tk.Label(f,
                 text="⚠  ALL DATA ON THE DISK WILL BE ERASED!",
                 font=('Arial', 12, 'bold'),
                 bg=BG, fg=RED).pack(pady=8)
        tk.Label(f,
                 text='Click "INSTALL NOW" to begin.',
                 font=('Arial', 10),
                 bg=BG, fg=GRAY).pack()

    # ─── Installation engine ───────────────────────────────────
    def _start_install(self):
        # Replace wizard with progress screen
        for w in self.content.winfo_children():
            w.destroy()

        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        tk.Label(top, text="Installing RIDOS OS...",
                 font=('Arial', 14, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left', padx=14)

        self._prog_status = tk.Label(
            self.content,
            text="Preparing...",
            font=('Arial', 10),
            bg=BG, fg=YELLOW)
        self._prog_status.pack(anchor='w', padx=14, pady=4)

        self._prog_bar = ttk.Progressbar(
            self.content,
            orient='horizontal',
            length=900, mode='determinate')
        self._prog_bar.pack(padx=14, pady=4)

        # Log window
        log_frame = tk.Frame(self.content, bg=BG)
        log_frame.pack(fill='both', expand=True, padx=14, pady=4)
        self._log_text = tk.Text(
            log_frame,
            bg='#111827', fg='#A5F3FC',
            font=('Courier', 10),
            relief='flat', state='disabled')
        scrollbar = tk.Scrollbar(log_frame,
                                 command=self._log_text.yview)
        self._log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self._log_text.pack(fill='both', expand=True)

        threading.Thread(
            target=self._do_install,
            daemon=True).start()

    def _log(self, msg):
        def _do():
            self._log_text.config(state='normal')
            self._log_text.insert('end', msg + '\n')
            self._log_text.see('end')
            self._log_text.config(state='disabled')
        self.root.after(0, _do)

    def _set_prog(self, pct, status):
        self.root.after(0, self._prog_bar.config,
                        {'value': pct})
        self.root.after(0, self._prog_status.config,
                        {'text': status})

    def _do_install(self):
        d   = self.install_data
        disk = d['disk']
        username = d['username']
        password = d['password']
        hostname = d['hostname']
        timezone = d['timezone']
        target   = '/mnt/ridos-install'

        pfx  = disk + 'p' if 'nvme' in disk else disk
        efi  = pfx + '1'
        swap = pfx + '2'
        root = pfx + '3'

        try:
            # Step 1: Partition
            self._set_prog(5, "Partitioning disk...")
            self._log(f"[1/7] Partitioning {disk}...")
            for cmd in [
                f"parted -s {disk} mklabel gpt",
                f"parted -s {disk} mkpart ESP fat32 1MiB 512MiB",
                f"parted -s {disk} set 1 esp on",
                f"parted -s {disk} mkpart primary linux-swap "
                f"512MiB 4608MiB",
                f"parted -s {disk} mkpart primary ext4 4608MiB 100%",
                "sleep 2",
                f"partprobe {disk}",
            ]:
                out, code = run_cmd(cmd, 30)
                self._log(f"  {'OK' if code==0 else 'WARN'}: "
                          f"{cmd.split()[0]}")

            # Step 2: Format
            self._set_prog(12, "Formatting partitions...")
            self._log("[2/7] Formatting...")
            for cmd, desc in [
                (f"mkfs.fat -F32 -n EFI {efi}",  "EFI"),
                (f"mkswap {swap}",                "Swap"),
                (f"mkfs.ext4 -F -L RIDOS {root}", "Root"),
            ]:
                out, code = run_cmd(cmd, 60)
                self._log(f"  {desc}: "
                          f"{'OK' if code==0 else out[:80]}")
                if code != 0 and desc == "Root":
                    raise Exception(
                        f"Format root failed: {out}")

            # Step 3: Mount
            self._set_prog(18, "Mounting target...")
            self._log("[3/7] Mounting...")
            run_cmd(f"mkdir -p {target}")
            out, code = run_cmd(f"mount {root} {target}")
            if code != 0:
                raise Exception(
                    f"Cannot mount root: {out}")
            run_cmd(f"mkdir -p {target}/boot/efi")
            run_cmd(f"mount {efi} {target}/boot/efi")
            run_cmd(f"swapon {swap} 2>/dev/null || true")

            # Step 4: Find squashfs
            self._set_prog(20, "Finding system image...")
            self._log("[4/7] Locating system image...")
            sq = find_squashfs()
            if not sq:
                raise Exception(
                    "Cannot find filesystem.squashfs!\n"
                    "Make sure you are running from the live USB.")
            self._log(f"  Found: {sq}")
            run_cmd(f"chmod 644 {sq} 2>/dev/null || true")

            # Mount squashfs
            run_cmd("mkdir -p /mnt/ridos-sq")
            out, code = run_cmd(
                f"mount -t squashfs -o loop,ro {sq} /mnt/ridos-sq")
            if code != 0:
                raise Exception(
                    f"Cannot mount squashfs: {out}")

            # Step 5: Copy files
            self._set_prog(25, "Copying files (10-20 min)...")
            self._log("[5/7] Copying RIDOS OS to disk...")
            self._log("  This will take 10-20 minutes...")
            out, code = run_cmd(
                f"rsync -aAXH "
                f"--exclude=/proc --exclude=/sys "
                f"--exclude=/dev --exclude=/run "
                f"--exclude=/tmp --exclude=/mnt "
                f"--exclude=/media --exclude=/lost+found "
                f"/mnt/ridos-sq/ {target}/",
                timeout=1800)
            run_cmd("umount /mnt/ridos-sq; "
                    "rmdir /mnt/ridos-sq 2>/dev/null || true")
            if code != 0:
                raise Exception(
                    f"rsync failed (code {code}):\n"
                    f"{out[-200:]}")
            self._log("  Copy complete!")

            # Step 6: Configure
            self._set_prog(75, "Configuring system...")
            self._log("[6/7] Configuring...")
            for dd in ['proc','sys','dev','dev/pts','run','tmp']:
                run_cmd(f"mkdir -p {target}/{dd}")

            # fstab
            ru, _ = run_cmd(
                f"blkid -s UUID -o value {root}")
            eu, _ = run_cmd(
                f"blkid -s UUID -o value {efi}")
            su, _ = run_cmd(
                f"blkid -s UUID -o value {swap}")
            with open(f"{target}/etc/fstab", 'w') as f:
                f.write(
                    f"UUID={ru.strip()}  /          "
                    f"ext4  defaults,noatime  0 1\n"
                    f"UUID={eu.strip()}  /boot/efi  "
                    f"vfat  umask=0077        0 2\n"
                    f"UUID={su.strip()}  none       "
                    f"swap  sw                0 0\n")
            self._log("  fstab written")

            with open(f"{target}/etc/hostname", 'w') as f:
                f.write(hostname + '\n')

            run_cmd(
                f"chroot {target} ln -sf "
                f"/usr/share/zoneinfo/{timezone} "
                f"/etc/localtime 2>/dev/null || true")

            run_cmd(
                f"chroot {target} userdel -r {username} "
                f"2>/dev/null || true")
            run_cmd(
                f"chroot {target} useradd -m -s /bin/bash "
                f"-G sudo,audio,video,netdev,plugdev "
                f"{username}")
            run_cmd(
                f"echo '{username}:{password}' | "
                f"chroot {target} chpasswd")
            run_cmd(
                f"echo 'root:{password}' | "
                f"chroot {target} chpasswd")
            self._log(f"  User '{username}' created")

            run_cmd(
                f"chroot {target} apt-get remove -y "
                f"live-boot live-boot-initramfs-tools "
                f"2>/dev/null || true")

            # Bind mounts for GRUB
            for dd in ['dev', 'dev/pts', 'proc', 'sys']:
                run_cmd(
                    f"mount --bind /{dd} {target}/{dd}")

            run_cmd(
                f"chroot {target} update-initramfs "
                f"-u -k all 2>/dev/null || true", 120)

            # Step 7: GRUB
            self._set_prog(88, "Installing bootloader...")
            self._log(f"[7/7] Installing GRUB on {disk}...")
            out, code = run_cmd(
                f"chroot {target} grub-install "
                f"--target=i386-pc --recheck "
                f"--force --no-floppy {disk}")
            self._log(f"  grub-install: "
                      f"{'OK' if code==0 else out[-100:]}")

            out2, code2 = run_cmd(
                f"chroot {target} update-grub")
            self._log(f"  update-grub: "
                      f"{'OK' if code2==0 else out2[-100:]}")

            # Cleanup
            for dd in ['sys','proc','dev/pts','dev']:
                run_cmd(
                    f"umount {target}/{dd} 2>/dev/null || true")
            run_cmd(
                f"umount {target}/boot/efi 2>/dev/null || true")
            run_cmd(
                f"umount {target} 2>/dev/null || true")
            run_cmd(f"swapoff {swap} 2>/dev/null || true")

            self._set_prog(100, "Installation complete!")
            self._log("\n=== RIDOS OS installed successfully! ===")
            self._log(f"Username: {username}")
            self._log(f"Password: {password}")
            self._log("\nRemove USB and reboot!")

            self.root.after(0, self._show_done)

        except Exception as e:
            self._log(f"\nFATAL ERROR: {e}")
            self._set_prog(0, f"FAILED: {e}")
            self.root.after(0, messagebox.showerror,
                            "Installation Failed", str(e))

    def _show_done(self):
        for w in self.content.winfo_children():
            w.destroy()
        f = tk.Frame(self.content, bg=BG)
        f.pack(fill='both', expand=True)
        tk.Label(f, text="✓ Installation Complete!",
                 font=('Arial', 20, 'bold'),
                 bg=BG, fg=GREEN).pack(pady=40)
        tk.Label(f,
                 text=f"Username: {self.install_data['username']}\n"
                      f"Password: {self.install_data['password']}\n\n"
                      "Remove USB drive and reboot.",
                 font=('Arial', 12),
                 bg=BG, fg=TEXT,
                 justify='center').pack()
        self._btn(f, "Reboot Now",
                  lambda: run_cmd("reboot"),
                  GREEN).pack(pady=20)
        self._btn(f, "Close",
                  self.root.destroy,
                  BG3).pack()

    # ═══════════════════════════════════════════════════════════
    # PAGE: About
    # ═══════════════════════════════════════════════════════════
    def _page_about(self):
        f = tk.Frame(self.content, bg=BG)
        f.pack(fill='both', expand=True, padx=24, pady=24)
        tk.Label(f,
                 text="RIDOS OS v1.0 Baghdad",
                 font=('Arial', 20, 'bold'),
                 bg=BG, fg=PURPLE).pack(pady=(20, 8))
        tk.Label(f,
                 text="AI-Powered Linux for IT & Communications Professionals",
                 font=('Arial', 12),
                 bg=BG, fg=TEXT).pack()
        tk.Label(f,
                 text="\nDisk Manager + OS Installer\n"
                      "Built with Python 3 + Tkinter\n"
                      "No Calamares — Full control\n\n"
                      "License: GPL v3\n"
                      "github.com/alkinanireyad/RIDOS-OS",
                 font=('Arial', 11),
                 bg=BG, fg=GRAY,
                 justify='center').pack(pady=12)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = RIDOSInstaller()
    app.run()
