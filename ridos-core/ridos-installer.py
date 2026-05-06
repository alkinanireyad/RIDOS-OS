#!/usr/bin/env python3
"""
RIDOS OS Installer v1.0 Baghdad
Proven 12-step installation method
12-step installation — GTK3/Tkinter — No Calamares
"""
# ── Fix DISPLAY before any import ────────────────────────────
import os, sys, subprocess

os.environ.setdefault('DISPLAY', ':0')
_su = os.environ.get('SUDO_USER', 'ridos')
if not os.environ.get('XAUTHORITY'):
    for _xa in [f'/home/{_su}/.Xauthority',
                '/home/ridos/.Xauthority',
                '/root/.Xauthority']:
        if os.path.exists(_xa):
            os.environ['XAUTHORITY'] = _xa
            break
subprocess.run('xhost +SI:localuser:root 2>/dev/null || true',
               shell=True, capture_output=True)
if os.geteuid() != 0:
    os.execvp('sudo', ['sudo', '-E', 'python3',
                       os.path.abspath(__file__)])
    sys.exit()

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
except ImportError:
    print("ERROR: python3-tk missing")
    sys.exit(1)

import threading, glob, shutil, re

# ── Colors ────────────────────────────────────────────────────
BG=     "#0F0A1E"
BG2=    "#1E1B4B"
BG3=    "#2D1B69"
PURPLE= "#7C3AED"
TEXT=   "#E9D5FF"
GREEN=  "#10B981"
YELLOW= "#F59E0B"
RED=    "#EF4444"
CYAN=   "#06B6D4"
GRAY=   "#6B7280"

MNT = "/mnt/ridos_target"

# ════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════

def sh(cmd, inp=None, timeout=600):
    r = subprocess.run(cmd, shell=True, capture_output=True,
                       text=True, timeout=timeout, input=inp)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def sh_log(cmd, log_fn, timeout=3600):
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:
        log_fn(line.rstrip())
    p.wait()
    return p.returncode

def is_efi():
    return os.path.exists('/sys/firmware/efi')

def get_disks():
    disks = []
    # Method 1: lsblk JSON
    out, _, rc = sh("lsblk -d -b -J -o NAME,SIZE,MODEL,TYPE 2>/dev/null")
    if rc == 0 and out:
        try:
            import json
            for d in json.loads(out).get('blockdevices', []):
                if d.get('type') != 'disk': continue
                name = d.get('name', '')
                if 'loop' in name or 'ram' in name: continue
                try: gb = int(d.get('size', 0)) / 1024**3
                except: gb = 0
                model = (d.get('model') or '').strip()
                disks.append((f'/dev/{name}',
                               f'{model} [{gb:.1f} GB]', gb))
            if disks: return disks
        except: pass
    # Method 2: lsblk text (TYPE is last column)
    out, _, _ = sh("lsblk -d -b -o NAME,SIZE,MODEL,TYPE -n 2>/dev/null")
    for line in out.split('\n'):
        parts = line.split()
        if len(parts) < 2: continue
        name = parts[0]
        if 'loop' in name or 'ram' in name: continue
        size = parts[1]
        dtype = parts[-1].strip()
        model = ' '.join(parts[2:-1]).strip() if len(parts) > 3 else ''
        if dtype != 'disk': continue
        try: gb = int(size) / 1024**3
        except: gb = 0
        disks.append((f'/dev/{name}', f'{model} [{gb:.1f} GB]', gb))
    if disks: return disks
    # Method 3: /proc/partitions
    out, _, _ = sh("cat /proc/partitions 2>/dev/null")
    for line in out.split('\n')[2:]:
        parts = line.split()
        if len(parts) < 4: continue
        name = parts[3]
        if 'loop' in name or 'ram' in name: continue
        if re.search(r'\d$', name): continue
        try: gb = int(parts[2]) * 1024 / 1024**3
        except: gb = 0
        disks.append((f'/dev/{name}', f'[{gb:.1f} GB]', gb))
    return disks

def get_partitions(disk):
    parts = []
    disk_name = os.path.basename(disk)
    # Method 1: JSON
    out, _, rc = sh(f"lsblk -b -J -o NAME,SIZE,FSTYPE,MOUNTPOINT {disk} 2>/dev/null")
    if rc == 0 and out:
        try:
            import json
            for d in json.loads(out).get('blockdevices', []):
                for c in d.get('children', []):
                    name = c.get('name', '')
                    if not name: continue
                    try: gb = int(c.get('size', 0)) / 1024**3
                    except: gb = 0
                    parts.append({'name': name, 'path': f'/dev/{name}',
                                  'size': f'{gb:.2f} GB',
                                  'fstype': c.get('fstype') or '',
                                  'mount': c.get('mountpoint') or ''})
            if parts: return parts
        except: pass
    # Method 2: key=value
    out, _, _ = sh(f"lsblk -b -o NAME,SIZE,FSTYPE,MOUNTPOINT -n -P {disk} 2>/dev/null")
    for line in out.split('\n'):
        if not line.strip(): continue
        kv = dict(re.findall(r'(\w+)="([^"]*)"', line))
        name = kv.get('NAME', '').strip()
        if not name or name == disk_name: continue
        try: gb = int(kv.get('SIZE', '0')) / 1024**3
        except: gb = 0
        parts.append({'name': name, 'path': f'/dev/{name}',
                      'size': f'{gb:.2f} GB',
                      'fstype': kv.get('FSTYPE', ''),
                      'mount': kv.get('MOUNTPOINT', '')})
    return parts

def find_squashfs():
    for p in ['/run/live/medium/live/filesystem.squashfs',
              '/lib/live/mount/medium/live/filesystem.squashfs',
              '/run/initramfs/live/filesystem.squashfs',
              '/cdrom/live/filesystem.squashfs']:
        if os.path.exists(p): return p
    out, _, _ = sh("mount | grep iso9660 | awk '{print $3}'")
    for mp in out.split('\n'):
        p = f"{mp.strip()}/live/filesystem.squashfs"
        if os.path.exists(p): return p
    out, _, _ = sh("find /run /cdrom /media /lib/live -name 'filesystem.squashfs' 2>/dev/null | head -1")
    return out.strip() if out.strip() else None

def write_minimal_grub_cfg(mnt, root_uuid, kern_path, init_path):
    """Write grub.cfg with exact kernel filename — proven fix"""
    os.makedirs(f"{mnt}/boot/grub", exist_ok=True)
    with open(f"{mnt}/boot/grub/grub.cfg", 'w') as f:
        f.write(f"""set default=0
set timeout=5

insmod part_gpt
insmod part_msdos
insmod ext2
insmod gzio

menuentry "RIDOS OS v1.0 Baghdad" {{
  search --no-floppy --fs-uuid --set=root {root_uuid}
  linux   {kern_path} root=UUID={root_uuid} ro quiet splash
  initrd  {init_path}
}}

menuentry "RIDOS OS (recovery)" {{
  search --no-floppy --fs-uuid --set=root {root_uuid}
  linux   {kern_path} root=UUID={root_uuid} ro single
  initrd  {init_path}
}}
""")

# ════════════════════════════════════════════════════════════════
class RIDOSInstaller:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RIDOS OS Installer v1.0 Baghdad")
        self.root.geometry("1020x680")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self._disks = []
        self._sel_disk = None
        self._sel_part = None
        self._efi = is_efi()
        self.install_data = {
            'disk': None, 'username': 'ridos',
            'password': 'ridos', 'hostname': 'ridos-os',
            'timezone': 'Asia/Baghdad',
        }
        self._build_ui()

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=BG2, pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="RIDOS OS", font=('Arial', 20, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left', padx=16)
        mode = "UEFI" if self._efi else "BIOS"
        tk.Label(hdr, text=f"Installer v1.0  |  {mode} mode",
                 font=('Arial', 11), bg=BG2, fg=TEXT).pack(side='left')
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)
        sb = tk.Frame(body, bg=BG2, width=155)
        sb.pack(side='left', fill='y')
        sb.pack_propagate(False)
        tk.Label(sb, text="MENU", font=('Arial', 9, 'bold'),
                 bg=BG2, fg=GRAY).pack(pady=(16, 4))
        self._nav_btns = {}
        for key, lbl in [('disks','  Disk Manager'),
                          ('install','  Install OS'),
                          ('about','  About')]:
            b = tk.Button(sb, text=lbl, font=('Arial', 11), anchor='w',
                          bg=BG2, fg=TEXT, relief='flat',
                          activebackground=BG3, cursor='hand2',
                          command=lambda k=key: self._nav(k))
            b.pack(fill='x', pady=2, padx=4)
            self._nav_btns[key] = b
        tk.Frame(body, bg='#2D1B69', width=1).pack(side='left', fill='y')
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side='left', fill='both', expand=True)
        self._nav('disks')

    def _nav(self, page):
        for k, b in self._nav_btns.items():
            b.config(bg=BG3 if k==page else BG2,
                     fg=TEXT if k==page else GRAY)
        for w in self.content.winfo_children():
            w.destroy()
        {'disks': self._page_disks,
         'install': self._page_install,
         'about': self._page_about}[page]()

    def _btn(self, parent, text, cmd, color=PURPLE, fg=TEXT, **kw):
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg=fg, font=('Arial', 9, 'bold'),
                         relief='flat', padx=8, pady=4, cursor='hand2', **kw)

    # ─── DISK MANAGER ─────────────────────────────────────────
    def _page_disks(self):
        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        tk.Label(top, text="Disk Manager", font=('Arial', 14, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left', padx=14)
        self._btn(top, "⟳ Refresh", self._refresh_disks, BG3).pack(side='right', padx=8)
        pane = tk.Frame(self.content, bg=BG)
        pane.pack(fill='both', expand=True, padx=8, pady=6)
        left = tk.Frame(pane, bg=BG, width=260)
        left.pack(side='left', fill='y', padx=(0,6))
        left.pack_propagate(False)
        tk.Label(left, text="Storage Devices", font=('Arial', 10, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w')
        self.disk_lb = tk.Listbox(left, bg=BG2, fg=TEXT,
                                   selectbackground=PURPLE,
                                   font=('Courier', 10), relief='flat',
                                   width=30, height=12, activestyle='none')
        self.disk_lb.pack(fill='both', expand=True, pady=4)
        self.disk_lb.bind('<<ListboxSelect>>', self._on_disk_sel)
        dbf = tk.Frame(left, bg=BG); dbf.pack(fill='x', pady=2)
        self._btn(dbf,"New GPT",self._new_part_table,BG3).grid(row=0,column=0,padx=2,pady=2)
        self._btn(dbf,"Format Disk",self._format_disk,RED).grid(row=0,column=1,padx=2,pady=2)
        right = tk.Frame(pane, bg=BG)
        right.pack(side='left', fill='both', expand=True)
        tk.Label(right, text="Partitions", font=('Arial', 10, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w')
        cols = ('Device','Size','FS','Mount','Flags')
        self.part_tree = ttk.Treeview(right, columns=cols,
                                       show='headings', height=11)
        sty = ttk.Style(); sty.theme_use('default')
        sty.configure('Treeview', background=BG2, foreground=TEXT,
                       fieldbackground=BG2, rowheight=22)
        sty.configure('Treeview.Heading', background=BG3,
                       foreground=CYAN, font=('Arial', 9, 'bold'))
        sty.map('Treeview', background=[('selected', PURPLE)])
        for col, w in zip(cols, [110,85,80,130,80]):
            self.part_tree.heading(col, text=col)
            self.part_tree.column(col, width=w, anchor='w')
        self.part_tree.pack(fill='both', expand=True, pady=4)
        self.part_tree.bind('<<TreeviewSelect>>', self._on_part_sel)
        pbf = tk.Frame(right, bg=BG); pbf.pack(fill='x', pady=2)
        for txt,cmd,color,row,col in [
            ("+ EXT4",self._create_ext4,PURPLE,0,0),
            ("+ Swap",self._create_swap,BG3,0,1),
            ("Set Boot",self._set_boot,GREEN,0,2),
            ("Set Active",self._set_active,GREEN,0,3),
            ("Resize",self._resize_part,CYAN,1,0),
            ("Format",self._format_part,YELLOW,1,1),
            ("Delete",self._delete_part,RED,1,2),
            ("Mount",self._toggle_mount,BG3,1,3),
        ]:
            self._btn(pbf,txt,cmd,color).grid(row=row,column=col,padx=2,pady=2,sticky='ew')
        self.disk_status = tk.Label(self.content, text="Select a disk",
                                     font=('Arial',9), bg=BG2, fg=GRAY,
                                     anchor='w', pady=3)
        self.disk_status.pack(fill='x', padx=8, pady=(0,4))
        self._refresh_disks()

    def _refresh_disks(self):
        self._disks = get_disks()
        self.disk_lb.delete(0, 'end')
        if not self._disks:
            self.disk_lb.insert('end', '  No disks found'); return
        for path, label, gb in self._disks:
            self.disk_lb.insert('end', f"  {path}  {label}")

    def _on_disk_sel(self, event):
        sel = self.disk_lb.curselection()
        if not sel or sel[0] >= len(self._disks): return
        self._sel_disk = self._disks[sel[0]][0]
        self.install_data['disk'] = self._sel_disk
        self.disk_status.config(
            text=f"  {self._disks[sel[0]][0]}  {self._disks[sel[0]][1]}")
        self._refresh_parts()

    def _on_part_sel(self, event):
        sel = self.part_tree.selection()
        if sel:
            vals = self.part_tree.item(sel[0], 'values')
            if vals: self._sel_part = vals[0]

    def _refresh_parts(self):
        for r in self.part_tree.get_children():
            self.part_tree.delete(r)
        if not self._sel_disk: return
        parts = get_partitions(self._sel_disk)
        flags_out, _, _ = sh(f"parted -s {self._sel_disk} print 2>/dev/null")
        flags_map = {}
        for line in flags_out.split('\n'):
            toks = line.strip().split()
            if toks and toks[0].isdigit():
                flags_map[toks[0]] = toks[-1]
        if not parts:
            self.part_tree.insert('','end',values=('No partitions','','','','')); return
        for i, p in enumerate(parts, 1):
            self.part_tree.insert('','end', values=(
                f"/dev/{p['name']}", p['size'],
                p['fstype'] or '-', p['mount'] or '-',
                flags_map.get(str(i), '')))

    def _req_disk(self):
        if not self._sel_disk:
            messagebox.showwarning("","Select a disk first"); return False
        return True

    def _req_part(self):
        if not self._sel_part:
            messagebox.showwarning("","Select a partition first"); return False
        return True

    def _new_part_table(self):
        if not self._req_disk(): return
        if not messagebox.askyesno("Confirm",
                f"New GPT table on {self._sel_disk}?\nErases all partitions!"): return
        sh(f"parted -s {self._sel_disk} mklabel gpt")
        self._refresh_parts()

    def _format_disk(self):
        if not self._req_disk(): return
        if not messagebox.askyesno("⚠ WARNING",
                f"ERASE ALL DATA on {self._sel_disk}?"): return
        sh(f"parted -s {self._sel_disk} mklabel gpt")
        messagebox.showinfo("Done","Disk formatted")
        self._refresh_parts()

    def _create_ext4(self):
        if not self._req_disk(): return
        size = simpledialog.askstring("Size",
            "Size in GB (empty=all free space):", parent=self.root)
        if size is None: return
        disk = self._sel_disk
        parts = get_partitions(disk)
        start = "1MiB" if not parts else "100%"
        if parts:
            fp, _, _ = sh(f"parted -s {disk} unit MiB print free 2>/dev/null")
            for line in reversed(fp.split('\n')):
                if 'Free Space' in line:
                    toks = line.split()
                    if toks: start = toks[0]; break
        end = "100%"
        if size and size.strip():
            try:
                sz = float(size.strip())
                s_mib = float(start.replace('MiB','') or '1')
                end = f"{s_mib + sz*1024:.0f}MiB"
            except: pass
        sh(f"parted -s {disk} mkpart primary ext4 {start} {end}")
        sh("partprobe 2>/dev/null || true")
        sh("udevadm settle 2>/dev/null || true")
        sh("sleep 2")
        parts2 = get_partitions(disk)
        if parts2:
            new_p = parts2[-1]['path']
            _, err, rc = sh(f"mkfs.ext4 -F -E lazy_itable_init=0,lazy_journal_init=0 {new_p}", timeout=120)
            messagebox.showinfo("Done", f"EXT4: {new_p}" if rc==0 else f"Failed:\n{err}")
        self._refresh_parts()

    def _create_swap(self):
        if not self._req_disk(): return
        size = simpledialog.askstring("Swap","Size in GB:", parent=self.root)
        if not size: return
        try: sz = float(size.strip())
        except: messagebox.showerror("Error","Invalid"); return
        disk = self._sel_disk
        parts = get_partitions(disk)
        start = "1MiB" if not parts else "100%"
        if parts:
            fp, _, _ = sh(f"parted -s {disk} unit MiB print free 2>/dev/null")
            for line in reversed(fp.split('\n')):
                if 'Free Space' in line:
                    toks = line.split()
                    if toks: start = toks[0]; break
        s_mib = float(start.replace('MiB','') or '1')
        end = f"{s_mib + sz*1024:.0f}MiB"
        sh(f"parted -s {disk} mkpart primary linux-swap {start} {end}")
        sh("partprobe 2>/dev/null || true")
        sh("udevadm settle 2>/dev/null || true"); sh("sleep 2")
        parts2 = get_partitions(disk)
        if parts2:
            new_p = parts2[-1]['path']
            sh(f"mkswap {new_p}")
            messagebox.showinfo("Done", f"Swap: {new_p}")
        self._refresh_parts()

    def _set_boot(self):
        if not self._req_part(): return
        num = re.sub(r'^.*?(\d+)$', r'\1', os.path.basename(self._sel_part))
        sh(f"parted -s {self._sel_disk} set {num} boot on")
        messagebox.showinfo("Done", f"Boot flag set on {self._sel_part}")
        self._refresh_parts()

    def _set_active(self):
        if not self._req_part(): return
        num = re.sub(r'^.*?(\d+)$', r'\1', os.path.basename(self._sel_part))
        sh(f"parted -s {self._sel_disk} set {num} esp on 2>/dev/null || true")
        sh(f"parted -s {self._sel_disk} set {num} boot on")
        sh(f"sfdisk --activate {self._sel_disk} {num} 2>/dev/null || true")
        messagebox.showinfo("Done", f"Active set on {self._sel_part}")
        self._refresh_parts()

    def _resize_part(self):
        if not self._req_part(): return
        cur, _, _ = sh(f"lsblk -b -o SIZE -n {self._sel_part} 2>/dev/null")
        try: cur_gb = int(cur.split('\n')[-1]) / 1024**3
        except: cur_gb = 0
        new_size = simpledialog.askstring("Resize",
            f"Current: {cur_gb:.1f} GB\nNew size in GB:", parent=self.root)
        if not new_size: return
        try: new_gb = float(new_size.strip())
        except: messagebox.showerror("Error","Invalid"); return
        parts = get_partitions(self._sel_disk)
        for p in parts:
            if p['path'] == self._sel_part and p['mount']:
                messagebox.showerror("Error", f"Unmount {self._sel_part} first!"); return
        fs, _, _ = sh(f"blkid -s TYPE -o value {self._sel_part} 2>/dev/null")
        num = re.sub(r'^.*?(\d+)$', r'\1', os.path.basename(self._sel_part))
        if not messagebox.askyesno("Confirm",
                f"Resize {self._sel_part} to {new_gb:.1f} GB?\nBackup first!"): return
        self._task_win("Resize", self._do_resize,
                       self._sel_disk, self._sel_part, num, new_gb, fs.strip())

    def _do_resize(self, log, done, disk, part, num, new_gb, fstype):
        try:
            if 'ext' in fstype:
                log("e2fsck..."); sh(f"e2fsck -f -y {part}", timeout=120)
            new_mib = int(new_gb * 1024)
            log(f"Resizing to {new_mib} MiB...")
            sh(f"parted -s {disk} resizepart {num} {new_mib}MiB", timeout=30)
            sh("partprobe 2>/dev/null || true")
            sh("udevadm settle 2>/dev/null || true")
            if 'ext' in fstype:
                log("resize2fs..."); sh(f"resize2fs {part}", timeout=120)
            elif 'xfs' in fstype:
                mnt = f"/mnt/xfs_{num}"
                sh(f"mkdir -p {mnt}"); sh(f"mount {part} {mnt}")
                sh(f"xfs_growfs {mnt}", timeout=60)
                sh(f"umount {mnt}"); sh(f"rmdir {mnt}")
            log("Resize complete!")
        except Exception as e: log(f"ERROR: {e}")
        finally: done()

    def _format_part(self):
        if not self._req_part(): return
        fs = simpledialog.askstring("Format",
            f"Format {self._sel_part} as:\next4/fat32/xfs/swap", parent=self.root)
        if not fs: return
        fs = fs.strip().lower()
        if not messagebox.askyesno("⚠ WARNING",
                f"Format {self._sel_part} as {fs}?\nALL DATA ERASED!"): return
        cmds = {
            'ext4': f"mkfs.ext4 -F -E lazy_itable_init=0,lazy_journal_init=0 {self._sel_part}",
            'fat32': f"mkfs.fat -F32 {self._sel_part}",
            'vfat': f"mkfs.fat -F32 {self._sel_part}",
            'xfs': f"mkfs.xfs -f {self._sel_part}",
            'swap': f"mkswap {self._sel_part}",
        }
        cmd = cmds.get(fs)
        if not cmd: messagebox.showerror("Error",f"Unknown: {fs}"); return
        _, err, rc = sh(cmd, timeout=120)
        messagebox.showinfo("Done", f"Formatted as {fs}" if rc==0 else f"Failed:\n{err}")
        self._refresh_parts()

    def _delete_part(self):
        if not self._req_part(): return
        num = re.sub(r'^.*?(\d+)$', r'\1', os.path.basename(self._sel_part))
        if not messagebox.askyesno("Confirm Delete",
                f"Delete {self._sel_part}?\nALL DATA LOST!"): return
        _, err, rc = sh(f"parted -s {self._sel_disk} rm {num}", timeout=30)
        messagebox.showinfo("Done", f"Deleted" if rc==0 else f"Failed:\n{err}")
        self._sel_part = None
        sh(f"partprobe {self._sel_disk}")
        sh("udevadm settle 2>/dev/null || true")
        self._refresh_parts()

    def _toggle_mount(self):
        if not self._req_part(): return
        parts = get_partitions(self._sel_disk)
        mounted = None
        for p in parts:
            if p['path'] == self._sel_part and p['mount']:
                mounted = p['mount']; break
        if mounted:
            sh(f"umount {self._sel_part} 2>/dev/null || true")
            messagebox.showinfo("Done", f"Unmounted")
        else:
            mnt = f"/mnt/{os.path.basename(self._sel_part)}"
            sh(f"mkdir -p {mnt}")
            _, err, rc = sh(f"mount {self._sel_part} {mnt}")
            messagebox.showinfo("Done", f"Mounted at {mnt}" if rc==0 else f"Failed:\n{err}")
        self._refresh_parts()

    def _task_win(self, title, func, *args):
        win = tk.Toplevel(self.root)
        win.title(title); win.geometry("560x340")
        win.configure(bg=BG); win.grab_set()
        tk.Label(win, text=title, font=('Arial',12,'bold'),
                 bg=BG, fg=PURPLE).pack(pady=8)
        lt = tk.Text(win, bg='#111827', fg='#A5F3FC',
                     font=('Courier',10), relief='flat', state='disabled')
        lt.pack(fill='both', expand=True, padx=12, pady=4)
        cb = self._btn(win, "Close", win.destroy, BG3)
        cb.pack(pady=8); cb.config(state='disabled')
        def log(msg):
            def _do():
                lt.config(state='normal'); lt.insert('end',msg+'\n')
                lt.see('end'); lt.config(state='disabled')
            win.after(0, _do)
        def done():
            win.after(0, cb.config, {'state':'normal'})
            log("Done!"); self._refresh_parts()
        threading.Thread(target=func, args=(log,done)+args, daemon=True).start()

    # ─── INSTALL OS ────────────────────────────────────────────
    def _page_install(self):
        self._step = 0
        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        self._step_lbl = tk.Label(top, text="Step 1 of 4",
            font=('Arial',13,'bold'), bg=BG2, fg=PURPLE)
        self._step_lbl.pack(side='left', padx=14)
        strip = tk.Frame(self.content, bg=BG, pady=4)
        strip.pack(fill='x', padx=10)
        self._inds = []
        for n in ['1.Disk','2.User','3.Settings','4.Confirm']:
            l = tk.Label(strip, text=n, font=('Arial',9), bg=BG, fg=GRAY)
            l.pack(side='left', expand=True); self._inds.append(l)
        tk.Frame(self.content, bg=BG2, height=1).pack(fill='x')
        # nav BEFORE wiz
        nav = tk.Frame(self.content, bg=BG2, pady=8)
        nav.pack(fill='x', side='bottom')
        self._back = self._btn(nav,"◀ Back",self._step_back,BG3)
        self._back.pack(side='left', padx=12)
        self._next = self._btn(nav,"Next ▶",self._step_next,PURPLE)
        self._next.pack(side='right', padx=12)
        self._wiz = tk.Frame(self.content, bg=BG)
        self._wiz.pack(fill='both', expand=True, padx=16, pady=8)
        self._show_step(0)

    def _show_step(self, step):
        self._step = step
        for w in self._wiz.winfo_children(): w.destroy()
        names = ['Disk','User','Settings','Confirm']
        for i, ind in enumerate(self._inds):
            ind.config(fg=GREEN if i<step else PURPLE if i==step else GRAY,
                       font=('Arial',9,'bold') if i<=step else ('Arial',9))
        self._step_lbl.config(text=f"Step {step+1} of 4: {names[step]}")
        [self._s_disk,self._s_user,self._s_settings,self._s_confirm][step]()
        self._back.config(state='normal' if step>0 else 'disabled')
        if step == 3: self._next.config(text="INSTALL NOW", bg=RED)
        else: self._next.config(text="Next ▶", bg=PURPLE)

    def _step_back(self):
        if self._step > 0: self._show_step(self._step - 1)

    def _step_next(self):
        if self._step < 3: self._show_step(self._step + 1)
        else:
            if not self.install_data.get('disk'):
                messagebox.showerror("Error","Select a disk first!"); return
            if messagebox.askyesno("⚠ FINAL CONFIRMATION",
                    f"Install RIDOS OS on {self.install_data['disk']}?\n\n"
                    "ALL DATA WILL BE ERASED!\nThis cannot be undone!"):
                self._start_install()

    def _s_disk(self):
        f = self._wiz
        tk.Label(f, text="Select installation disk:",
                 font=('Arial',11,'bold'), bg=BG, fg=TEXT).pack(anchor='w', pady=(0,6))
        tk.Label(f, text=f"Boot mode: {'UEFI' if self._efi else 'BIOS/MBR'}",
                 font=('Arial',10), bg=BG, fg=CYAN).pack(anchor='w', pady=(0,4))
        tk.Label(f, text="⚠  All data on selected disk will be erased!",
                 font=('Arial',10), bg=BG, fg=YELLOW).pack(anchor='w', pady=(0,10))
        disks = get_disks()
        if not disks:
            tk.Label(f, text="No disks found!", bg=BG, fg=RED).pack(); return
        self._dv = tk.StringVar(value=self.install_data.get('disk',''))
        for path, label, gb in disks:
            tk.Radiobutton(f, text=f"{path}  —  {label}",
                variable=self._dv, value=path,
                font=('Arial',11), bg=BG, fg=TEXT,
                selectcolor=BG3, activebackground=BG,
                command=lambda p=path:
                    self.install_data.__setitem__('disk', p)
            ).pack(anchor='w', pady=3)
        if disks and not self.install_data.get('disk'):
            self._dv.set(disks[0][0])
            self.install_data['disk'] = disks[0][0]
        layout = ("\nLayout (UEFI):\n"
                  "  1. 512MB EFI [esp+boot]\n"
                  "  2. 2GB Swap\n"
                  "  3. Rest Root EXT4 [boot]"
                  ) if self._efi else (
                  "\nLayout (BIOS/MBR):\n"
                  "  1. 2GB Swap\n"
                  "  2. Rest Root EXT4 [boot]")
        tk.Label(f, text=layout, font=('Courier',9),
                 bg=BG, fg=GRAY, justify='left').pack(anchor='w', pady=10)

    def _s_user(self):
        f = self._wiz
        tk.Label(f, text="User Account", font=('Arial',12,'bold'),
                 bg=BG, fg=PURPLE).pack(anchor='w', pady=(0,10))
        for label, key, default, secret in [
            ('Full Name','fullname','RIDOS User',False),
            ('Username','username','ridos',False),
            ('Password','password','ridos',True),
            ('Hostname','hostname','ridos-os',False),
        ]:
            row = tk.Frame(f, bg=BG); row.pack(fill='x', pady=4)
            tk.Label(row, text=f"{label}:", font=('Arial',10),
                     bg=BG, fg=TEXT, width=12, anchor='e').pack(side='left')
            e = tk.Entry(row, font=('Arial',11), bg=BG2, fg=TEXT,
                         insertbackground=TEXT, relief='flat', bd=4, width=26)
            e.insert(0, self.install_data.get(key, default))
            if secret: e.config(show='*')
            e.pack(side='left', padx=8)
            e.bind('<KeyRelease>',
                   lambda ev, k=key:
                   self.install_data.__setitem__(k, ev.widget.get()))

    def _s_settings(self):
        f = self._wiz
        tk.Label(f, text="System Settings", font=('Arial',12,'bold'),
                 bg=BG, fg=PURPLE).pack(anchor='w', pady=(0,10))
        row = tk.Frame(f, bg=BG); row.pack(fill='x', pady=4)
        tk.Label(row, text="Timezone:", font=('Arial',10),
                 bg=BG, fg=TEXT, width=12, anchor='e').pack(side='left')
        out, _, _ = sh("timedatectl list-timezones 2>/dev/null | head -100")
        zones = out.split('\n') if out else ["Asia/Baghdad","UTC"]
        self._tz = tk.StringVar(
            value=self.install_data.get('timezone','Asia/Baghdad'))
        combo = ttk.Combobox(row, textvariable=self._tz,
                             values=zones, font=('Arial',10),
                             width=30, state='readonly')
        combo.pack(side='left', padx=8)
        combo.bind('<<ComboboxSelected>>',
                   lambda e: self.install_data.__setitem__(
                       'timezone', self._tz.get()))

    def _s_confirm(self):
        f = self._wiz
        d = self.install_data
        tk.Label(f, text="Review before installing:",
                 font=('Arial',11,'bold'), bg=BG, fg=TEXT).pack(anchor='w', pady=(0,8))
        tk.Label(f,
            text=f"  Disk:     {d.get('disk','NOT SET')}\n"
                 f"  Mode:     {'UEFI' if self._efi else 'BIOS/MBR'}\n"
                 f"  Username: {d.get('username','')}\n"
                 f"  Hostname: {d.get('hostname','')}\n"
                 f"  Timezone: {d.get('timezone','')}",
            font=('Courier',11), bg=BG2, fg=TEXT,
            justify='left', padx=12, pady=10).pack(fill='x', pady=6)
        tk.Label(f, text="⚠  ALL DATA WILL BE ERASED!",
                 font=('Arial',12,'bold'), bg=BG, fg=RED).pack(pady=8)

    # ─── INSTALLATION ENGINE — 12 proven steps ────────────────
    def _start_install(self):
        for w in self.content.winfo_children(): w.destroy()
        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        tk.Label(top, text="Installing RIDOS OS...",
                 font=('Arial',13,'bold'), bg=BG2, fg=PURPLE).pack(side='left', padx=14)
        self._ps = tk.Label(self.content, text="Preparing...",
                            font=('Arial',10), bg=BG, fg=YELLOW)
        self._ps.pack(anchor='w', padx=14, pady=2)
        self._pb = ttk.Progressbar(self.content, orient='horizontal',
                                   length=950, mode='determinate')
        self._pb.pack(padx=14, pady=2)
        lf = tk.Frame(self.content, bg=BG)
        lf.pack(fill='both', expand=True, padx=14, pady=4)
        self._lt = tk.Text(lf, bg='#111827', fg='#A5F3FC',
                           font=('Courier',10), relief='flat', state='disabled')
        sb2 = tk.Scrollbar(lf, command=self._lt.yview)
        self._lt.config(yscrollcommand=sb2.set)
        sb2.pack(side='right', fill='y')
        self._lt.pack(fill='both', expand=True)
        threading.Thread(target=self._run_install, daemon=True).start()

    def _log(self, msg):
        def _do():
            self._lt.config(state='normal')
            self._lt.insert('end', msg+'\n')
            self._lt.see('end')
            self._lt.config(state='disabled')
        self.root.after(0, _do)

    def _prog(self, pct, msg):
        self.root.after(0, self._pb.config, {'value': pct})
        self.root.after(0, self._ps.config, {'text': msg})

    def _run_install(self):
        d    = self.install_data
        disk = d['disk']
        user = d.get('username','ridos')
        pw   = d.get('password','ridos')
        host = d.get('hostname','ridos-os')
        tz   = d.get('timezone','Asia/Baghdad')
        mnt  = MNT
        efi  = self._efi

        try:
            # ── Step 1: Clean old mounts ──────────────────────
            self._prog(1, "[1/12] Cleaning...")
            self._log("[1/12] Cleaning old mounts...")
            for sub in ['dev/pts','dev','proc','sys','run',
                        'boot/efi','']:
                sh(f"umount -l {mnt}/{sub} 2>/dev/null || true")
            sh(f"rm -rf {mnt}")
            sh(f"mkdir -p {mnt}")
            self._log("  OK")

            # ── Step 2: Partition ─────────────────────────────
            self._prog(4, "[2/12] Partitioning...")
            self._log(f"[2/12] Partitioning {disk}...")
            if efi:
                self._log("  UEFI/GPT mode")
                sh(f"parted -s {disk} mklabel gpt")
                sh(f"parted -s {disk} mkpart ESP fat32 1MiB 513MiB")
                sh(f"parted -s {disk} set 1 esp on")
                sh(f"parted -s {disk} set 1 boot on")
                sh(f"parted -s {disk} mkpart primary linux-swap 513MiB 2561MiB")
                sh(f"parted -s {disk} mkpart primary ext4 2561MiB 100%")
                sh(f"parted -s {disk} set 3 boot on")
                pfx = disk+'p' if 'nvme' in disk else disk
                efi_p=pfx+'1'; swap_p=pfx+'2'; root_p=pfx+'3'
            else:
                self._log("  BIOS/MBR mode")
                sh(f"parted -s {disk} mklabel msdos")
                sh(f"parted -s {disk} mkpart primary linux-swap 1MiB 2049MiB")
                sh(f"parted -s {disk} mkpart primary ext4 2049MiB 100%")
                sh(f"parted -s {disk} set 2 boot on")
                pfx = disk+'p' if 'nvme' in disk else disk
                efi_p=None; swap_p=pfx+'1'; root_p=pfx+'2'
            self._log(f"  swap={swap_p} root={root_p}")

            # ── Step 3: Wait for kernel ───────────────────────
            self._prog(7, "[3/12] Waiting for kernel...")
            self._log("[3/12] partprobe + udevadm settle + sleep 3...")
            sh("partprobe 2>/dev/null || true")
            sh("udevadm settle 2>/dev/null || true")
            sh("sleep 3")
            self._log("  OK")

            # ── Step 4: Format ────────────────────────────────
            self._prog(10, "[4/12] Formatting...")
            self._log("[4/12] Formatting partitions...")
            if efi_p:
                _, err, rc = sh(f"mkfs.fat -F 32 {efi_p}", timeout=60)
                self._log(f"  EFI: {'OK' if rc==0 else err[:80]}")
            _, err, rc = sh(f"mkswap {swap_p}", timeout=30)
            self._log(f"  Swap: {'OK' if rc==0 else err[:80]}")
            sh(f"swapon {swap_p} 2>/dev/null || true")
            _, err, rc = sh(
                f"mkfs.ext4 -F "
                f"-E lazy_itable_init=0,lazy_journal_init=0 "
                f"{root_p}", timeout=120)
            self._log(f"  Root: {'OK' if rc==0 else err[:80]}")
            if rc != 0:
                raise Exception(f"mkfs.ext4 failed: {err}")

            # ── Step 5: Mount ─────────────────────────────────
            self._prog(13, "[5/12] Mounting...")
            self._log("[5/12] Mounting partitions...")
            _, err, rc = sh(f"mount {root_p} {mnt}")
            if rc != 0:
                raise Exception(f"Cannot mount root: {err}")
            if efi_p:
                sh(f"mkdir -p {mnt}/boot/efi")
                sh(f"mount {efi_p} {mnt}/boot/efi")
            self._log("  OK")

            # ── Step 6: Copy filesystem ───────────────────────
            self._prog(15, "[6/12] Finding squashfs...")
            self._log("[6/12] Finding system image...")
            sq = find_squashfs()
            if not sq:
                raise Exception(
                    "Cannot find filesystem.squashfs!\n"
                    "Boot from live USB first.")
            self._log(f"  Found: {sq}")
            sh(f"chmod 644 {sq} 2>/dev/null || true")

            # unsquashfs to temp then rsync
            tmp_sq = "/tmp/sq_extract"
            sh(f"rm -rf {tmp_sq}")
            sh(f"mkdir -p {tmp_sq}")
            self._prog(18, "[6/12] Extracting squashfs...")
            self._log("  Extracting squashfs...")
            rc2 = sh_log(
                f"unsquashfs -f -d {tmp_sq} {sq}",
                self._log, timeout=1800)

            # unsquashfs creates squashfs-root/ inside tmp_sq
            src = f"{tmp_sq}/squashfs-root"
            if not os.path.exists(src):
                self._log("  Mounting squashfs (fallback)...")
                sh(f"rm -rf {tmp_sq}"); sh(f"mkdir -p {tmp_sq}")
                _, err, rc3 = sh(
                    f"mount -t squashfs -o loop,ro {sq} {tmp_sq}")
                if rc3 != 0:
                    raise Exception(f"Cannot mount squashfs: {err}")
                src = tmp_sq

            self._prog(25, "[6/12] Copying files (10-20 min)...")
            self._log("  Copying files to disk...")
            rc4 = sh_log(
                f"rsync -aAXH "
                f"--exclude=/proc --exclude=/sys "
                f"--exclude=/dev --exclude=/run "
                f"--exclude=/tmp --exclude=/mnt "
                f"--exclude=/media --exclude=/lost+found "
                f"{src}/ {mnt}/",
                self._log, timeout=1800)
            sh(f"umount {tmp_sq} 2>/dev/null || true")
            sh(f"rm -rf {tmp_sq} 2>/dev/null || true")
            if rc4 != 0:
                raise Exception(f"rsync failed (exit {rc4})")
            self._log("  Files copied: OK")

            # ── Step 7: Bind mounts AFTER rsync ───────────────
            self._prog(65, "[7/12] Bind mounts...")
            self._log("[7/12] Binding system dirs (after rsync)...")
            for d_bind in ['/dev','/dev/pts','/proc','/sys','/run']:
                sh(f"mkdir -p {mnt}{d_bind}")
                sh(f"mount --rbind {d_bind} {mnt}{d_bind}")
            self._log("  OK")

            # ── Step 8: Configure ─────────────────────────────
            self._prog(68, "[8/12] Configuring system...")
            self._log("[8/12] Configuring...")
            with open(f"{mnt}/etc/hostname",'w') as f:
                f.write(host+'\n')
            sh(f"chroot {mnt} ln -sf "
               f"/usr/share/zoneinfo/{tz} /etc/localtime 2>/dev/null || true")
            root_uuid,_,_ = sh(f"blkid -s UUID -o value {root_p}")
            root_uuid = root_uuid.strip()
            swap_uuid,_,_ = sh(f"blkid -s UUID -o value {swap_p}")
            swap_uuid = swap_uuid.strip()
            fstab = (f"UUID={root_uuid}  /  ext4  "
                     f"defaults,errors=remount-ro  0  1\n"
                     f"UUID={swap_uuid}  none  swap  sw  0  0\n")
            if efi_p:
                efi_uuid,_,_ = sh(f"blkid -s UUID -o value {efi_p}")
                fstab += (f"UUID={efi_uuid.strip()}  /boot/efi  "
                          f"vfat  umask=0077  0  2\n")
            with open(f"{mnt}/etc/fstab",'w') as f:
                f.write(fstab)
            self._log(f"  fstab: root UUID={root_uuid[:8]}...")
            sh(f"chroot {mnt} userdel -r {user} 2>/dev/null || true")
            sh(f"chroot {mnt} useradd -m -s /bin/bash "
               f"-G sudo,audio,video,netdev,plugdev {user}")
            p = subprocess.Popen(
                f"chroot {mnt} chpasswd",
                shell=True, stdin=subprocess.PIPE)
            p.communicate(
                input=f"{user}:{pw}\nroot:{pw}\n".encode())
            self._log(f"  User '{user}': OK")
            # disable live autologin
            for fp in [f"{mnt}/etc/lightdm/lightdm.conf.d/50-ridos.conf",
                       f"{mnt}/etc/lightdm/lightdm.conf"]:
                if os.path.exists(fp):
                    c = open(fp).read()
                    c = c.replace('autologin-user=ridos',
                                  '#autologin-user=ridos')
                    open(fp,'w').write(c)
            sh(f"chroot {mnt} apt-get remove -y "
               f"live-boot live-boot-initramfs-tools "
               f"2>/dev/null || true")

            # ── Step 9: DNS + apt ─────────────────────────────
            self._prog(77, "[9/12] DNS + apt...")
            self._log("[9/12] Configuring network...")
            shutil.copy('/etc/resolv.conf', f"{mnt}/etc/resolv.conf")
            with open(f"{mnt}/etc/apt/sources.list",'w') as f:
                f.write(
                    "deb http://deb.debian.org/debian "
                    "bookworm main contrib non-free non-free-firmware\n"
                    "deb http://security.debian.org/debian-security "
                    "bookworm-security main contrib non-free non-free-firmware\n")
            sh_log(f"chroot {mnt} apt-get update -qq",
                   self._log, timeout=120)
            self._log("  apt: OK")

            # ── Step 10: Install + run GRUB ───────────────────
            self._prog(78, "[10/12] Installing GRUB...")
            self._log("[10/12] Installing GRUB...")
            if efi:
                self._log("  Installing grub-efi...")
                sh_log(
                    f"chroot {mnt} apt-get install -y "
                    f"grub-efi-amd64 grub-efi-amd64-bin "
                    f"grub-common grub2-common",
                    self._log, timeout=300)
                _, err, rc = sh(
                    f"chroot {mnt} grub-install "
                    f"--target=x86_64-efi "
                    f"--efi-directory=/boot/efi "
                    f"--bootloader-id=RIDOS "
                    f"--recheck", 60)
            else:
                self._log("  Installing grub-pc...")
                sh_log(
                    f"chroot {mnt} apt-get install -y "
                    f"grub-pc grub-pc-bin "
                    f"grub-common grub2-common",
                    self._log, timeout=300)
                _, err, rc = sh(
                    f"chroot {mnt} grub-install "
                    f"--target=i386-pc "
                    f"--recheck "
                    f"{disk}", 60)
            self._log(f"  grub-install: {'OK' if rc==0 else err[-150:]}")

            # ── Step 11: grub.cfg ─────────────────────────────
            self._prog(85, "[11/12] grub.cfg...")
            self._log("[11/12] Generating grub.cfg...")
            kern_files = sorted(glob.glob(f"{mnt}/boot/vmlinuz-*"))
            init_files = sorted(glob.glob(f"{mnt}/boot/initrd.img-*"))
            if not kern_files:
                raise Exception("No kernel in /boot!")
            kern_name = os.path.basename(kern_files[-1])
            init_name = os.path.basename(init_files[-1]) \
                if init_files else f"initrd.img-{kern_name[8:]}"
            kern_path = f"/boot/{kern_name}"
            init_path = f"/boot/{init_name}"
            self._log(f"  kernel: {kern_name}")
            self._log(f"  initrd: {init_name}")
            # symlinks
            sh(f"ln -sf {kern_path} {mnt}/vmlinuz 2>/dev/null || true")
            sh(f"ln -sf {init_path} {mnt}/initrd.img 2>/dev/null || true")
            # run update-grub
            sh_log(f"chroot {mnt} update-grub", self._log, timeout=60)
            # verify kernel name in grub.cfg
            cfg = f"{mnt}/boot/grub/grub.cfg"
            needs_rewrite = True
            if os.path.exists(cfg):
                content = open(cfg).read()
                if kern_name in content:
                    needs_rewrite = False
                    self._log("  grub.cfg: OK")
                else:
                    self._log("  grub.cfg missing kernel name, rewriting...")
            if needs_rewrite:
                write_minimal_grub_cfg(mnt, root_uuid, kern_path, init_path)
                self._log("  grub.cfg: rewritten with exact kernel name")
            # show key lines
            if os.path.exists(cfg):
                for line in open(cfg):
                    if 'linux ' in line or 'menuentry' in line:
                        self._log(f"    {line.rstrip()}")

            # ── Step 12: Cleanup ──────────────────────────────
            self._prog(97, "[12/12] Cleaning up...")
            self._log("[12/12] Unmounting...")
            for sub in ['dev/pts','dev','proc','sys','run']:
                sh(f"umount -l {mnt}/{sub} 2>/dev/null || true")
            if efi_p:
                sh(f"umount -l {mnt}/boot/efi 2>/dev/null || true")
            sh(f"umount -l {mnt} 2>/dev/null || true")
            sh(f"swapoff {swap_p} 2>/dev/null || true")
            self._log("  OK")

            self._prog(100, "Installation complete!")
            self._log("\n" + "="*45 +
                      "\nRIDOS OS installed successfully!" +
                      f"\n  Username: {user}" +
                      f"\n  Password: {pw}" +
                      "\n  Remove USB and reboot!" +
                      "\n" + "="*45)
            self.root.after(0, self._done, user, pw)

        except Exception as e:
            self._log(f"\nFATAL ERROR: {e}")
            self._prog(0, f"FAILED: {e}")
            for sub in ['dev/pts','dev','proc','sys','run']:
                sh(f"umount -l {mnt}/{sub} 2>/dev/null || true")
            sh(f"umount -l {mnt}/boot/efi 2>/dev/null || true")
            sh(f"umount -l {mnt} 2>/dev/null || true")
            self.root.after(0, messagebox.showerror,
                            "Installation Failed", str(e))

    def _done(self, user, pw):
        for w in self.content.winfo_children(): w.destroy()
        f = tk.Frame(self.content, bg=BG)
        f.pack(fill='both', expand=True)
        tk.Label(f, text="✓ Installation Complete!",
                 font=('Arial',22,'bold'), bg=BG, fg=GREEN).pack(pady=40)
        tk.Label(f,
                 text=f"Username: {user}\nPassword: {pw}\n\n"
                      "Remove USB and reboot.",
                 font=('Arial',13), bg=BG, fg=TEXT,
                 justify='center').pack()
        self._btn(f,"Reboot Now", lambda: sh("reboot"), GREEN).pack(pady=20)
        self._btn(f,"Close", self.root.destroy, BG3).pack()

    # ─── ABOUT ────────────────────────────────────────────────
    def _page_about(self):
        f = tk.Frame(self.content, bg=BG)
        f.pack(fill='both', expand=True, padx=24, pady=24)
        tk.Label(f, text="RIDOS OS v1.0 Baghdad",
                 font=('Arial',20,'bold'), bg=BG, fg=PURPLE).pack(pady=(20,8))
        tk.Label(f,
                 text="AI-Powered Linux for IT & Communications\n\n"
                      "Installer v1.0 Baghdad\n"
                      "Disk Manager + OS Installer — BIOS/MBR + UEFI/GPT\n\n"
                      "License: GPL v3\n"
                      "github.com/alkinanireyad/RIDOS-OS",
                 font=('Arial',11), bg=BG, fg=TEXT,
                 justify='center').pack(pady=12)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = RIDOSInstaller()
    app.run()
