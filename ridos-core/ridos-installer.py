#!/usr/bin/env python3
"""
RIDOS OS All-in-One Tool
Disk Manager + OS Installer in one GTK3 window
Run: sudo python3 /opt/ridos/bin/ridos-installer.py
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango
import subprocess, threading, os, json, time, shutil

# ── Helpers ───────────────────────────────────────────────────
def run(cmd, timeout=600):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "Timed out", 1
    except Exception as e:
        return str(e), 1

def get_disks():
    out, _ = run("lsblk -d -b -o NAME,SIZE,MODEL,TYPE,TRAN -n 2>/dev/null")
    disks = []
    for line in out.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name, size = parts[0], parts[1]
        dtype = parts[3] if len(parts) > 3 else ''
        model = ' '.join(parts[2:3]) if len(parts) > 2 else 'Unknown'
        if dtype != 'disk' or 'loop' in name:
            continue
        try:
            size_gb = int(size) / 1024**3
        except:
            size_gb = 0
        disks.append({
            'name': name,
            'path': f'/dev/{name}',
            'size': f'{size_gb:.1f} GB',
            'model': model,
        })
    return disks

def get_partitions(disk):
    out, _ = run(f"lsblk -b -o NAME,SIZE,FSTYPE,MOUNTPOINT,LABEL -n {disk} 2>/dev/null")
    parts = []
    for line in out.strip().split('\n'):
        if not line.strip():
            continue
        cols = line.split()
        name = cols[0].lstrip('|-`')
        if name == os.path.basename(disk):
            continue
        size = cols[1] if len(cols) > 1 else '0'
        fstype = cols[2] if len(cols) > 2 else ''
        mount = cols[3] if len(cols) > 3 else ''
        try:
            size_gb = int(size) / 1024**3
        except:
            size_gb = 0
        parts.append({
            'name': name,
            'path': f'/dev/{name}',
            'size': f'{size_gb:.1f} GB',
            'fstype': fstype,
            'mount': mount,
        })
    return parts

def find_squashfs():
    paths = [
        "/run/live/medium/live/filesystem.squashfs",
        "/lib/live/mount/medium/live/filesystem.squashfs",
        "/cdrom/live/filesystem.squashfs",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    out, _ = run("find /run /lib/live /cdrom /media -name 'filesystem.squashfs' 2>/dev/null | head -1")
    return out.strip() if out.strip() else None

# ── CSS ───────────────────────────────────────────────────────
CSS = b"""
* { font-family: Arial, sans-serif; }
window { background-color: #0F0A1E; }
.sidebar { background-color: #1E1B4B; }
.topbar { background-color: #1E1B4B; padding: 12px; }
.page-title { color: #C4B5FD; font-size: 20px; font-weight: bold; }
.content-area { background-color: #0F0A1E; padding: 16px; }
.card { background-color: #1E1B4B; border-radius: 8px; padding: 14px; margin: 4px; }
.disk-row { background-color: #1E1B4B; border-radius: 6px; padding: 10px; margin: 3px; }
.disk-row:selected { background-color: #4C1D95; }
.disk-name { color: #C4B5FD; font-size: 15px; font-weight: bold; }
.disk-info { color: #9CA3AF; font-size: 12px; }
.part-row { background-color: #111827; border-radius: 4px; padding: 8px; margin: 2px; }
.btn-primary { background-color: #7C3AED; color: white; font-weight: bold;
               border-radius: 6px; padding: 8px 20px; border: none; }
.btn-primary:hover { background-color: #6D28D9; }
.btn-danger { background-color: #DC2626; color: white; font-weight: bold;
              border-radius: 6px; padding: 8px 20px; border: none; }
.btn-danger:hover { background-color: #B91C1C; }
.btn-success { background-color: #059669; color: white; font-weight: bold;
               border-radius: 6px; padding: 8px 20px; border: none; }
.btn-success:hover { background-color: #047857; }
.btn-flat { background-color: #374151; color: #E9D5FF;
            border-radius: 6px; padding: 8px 16px; border: none; }
.btn-flat:hover { background-color: #4B5563; }
.nav-btn { background-color: transparent; color: #9CA3AF;
           border-radius: 6px; padding: 10px 16px; border: none;
           font-size: 13px; text-align: left; }
.nav-btn:hover { background-color: #2D1B69; color: #E9D5FF; }
.nav-active { background-color: #4C1D95; color: #E9D5FF; font-weight: bold; }
.input { background-color: #111827; color: #E9D5FF;
         border: 1px solid #4C1D95; border-radius: 4px; padding: 7px; }
.log { background-color: #111827; color: #A5F3FC;
       font-family: monospace; font-size: 11px;
       padding: 8px; border-radius: 4px; }
.progress trough { background-color: #374151; border-radius: 4px; min-height: 10px; }
.progress progress { background-color: #7C3AED; border-radius: 4px; }
.status-ok   { color: #10B981; font-weight: bold; }
.status-warn { color: #F59E0B; font-weight: bold; }
.status-err  { color: #EF4444; font-weight: bold; }
label { color: #E9D5FF; }
"""

# ════════════════════════════════════════════════════════════════
class RIDOSTool(Gtk.Window):
    def __init__(self):
        super().__init__(title="RIDOS OS — Disk Manager & Installer")
        self.set_default_size(1000, 680)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)
        self.connect("delete-event", Gtk.main_quit)

        # Apply CSS
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.selected_disk = None
        self.install_data = {
            'disk': None,
            'username': 'ridos',
            'password': 'ridos',
            'hostname': 'ridos-os',
            'timezone': 'Asia/Baghdad',
            'fullname': 'RIDOS User',
        }

        self._build_layout()
        self._nav_to('disks')

    def _build_layout(self):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(hbox)

        # Sidebar
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sidebar.get_style_context().add_class('sidebar')
        sidebar.set_size_request(180, -1)
        sidebar.set_border_width(8)

        logo = Gtk.Label(label="RIDOS OS")
        logo.get_style_context().add_class('page-title')
        logo.set_margin_top(12)
        logo.set_margin_bottom(16)
        sidebar.pack_start(logo, False, False, 0)

        self.nav_buttons = {}
        nav_items = [
            ('disks',   'Disk Manager'),
            ('install', 'Install OS'),
            ('about',   'About'),
        ]
        for key, label in nav_items:
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class('nav-btn')
            btn.connect('clicked', lambda w, k=key: self._nav_to(k))
            sidebar.pack_start(btn, False, False, 0)
            self.nav_buttons[key] = btn

        hbox.pack_start(sidebar, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        hbox.pack_start(sep, False, False, 0)

        # Main content
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox.pack_start(self.main_box, True, True, 0)

    def _nav_to(self, page):
        for key, btn in self.nav_buttons.items():
            btn.get_style_context().remove_class('nav-active')
        self.nav_buttons[page].get_style_context().add_class('nav-active')
        for child in self.main_box.get_children():
            self.main_box.remove(child)
        {
            'disks':   self._page_disks,
            'install': self._page_install,
            'about':   self._page_about,
        }[page]()
        self.main_box.show_all()

    # ══════════════════════════════════════════════════════════
    # PAGE: Disk Manager
    # ══════════════════════════════════════════════════════════
    def _page_disks(self):
        topbar = Gtk.Box(spacing=12)
        topbar.get_style_context().add_class('topbar')
        topbar.set_border_width(4)
        title = Gtk.Label(label="Disk Manager")
        title.get_style_context().add_class('page-title')
        topbar.pack_start(title, False, False, 8)
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.get_style_context().add_class('btn-flat')
        refresh_btn.connect('clicked', lambda w: self._reload_disks())
        topbar.pack_end(refresh_btn, False, False, 4)
        self.main_box.pack_start(topbar, False, False, 0)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_border_width(8)
        paned.set_position(320)
        self.main_box.pack_start(paned, True, True, 0)

        # Left: disk list
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        lbl = Gtk.Label(label="Storage Devices")
        lbl.set_halign(Gtk.Align.START)
        left_box.pack_start(lbl, False, False, 0)

        scroll_l = Gtk.ScrolledWindow()
        scroll_l.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.disk_list_box = Gtk.ListBox()
        self.disk_list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.disk_list_box.connect('row-selected', self._on_disk_selected)
        scroll_l.add(self.disk_list_box)
        left_box.pack_start(scroll_l, True, True, 0)

        # Action buttons
        btn_box = Gtk.Box(spacing=6)
        for lbl_txt, fn, cls in [
            ("Format Disk",   self._format_disk,   'btn-danger'),
            ("New Part Table",self._new_part_table,'btn-flat'),
        ]:
            b = Gtk.Button(label=lbl_txt)
            b.get_style_context().add_class(cls)
            b.connect('clicked', fn)
            btn_box.pack_start(b, True, True, 0)
        left_box.pack_start(btn_box, False, False, 0)
        paned.pack1(left_box, True, False)

        # Right: partition details
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        lbl2 = Gtk.Label(label="Partitions & Details")
        lbl2.set_halign(Gtk.Align.START)
        right_box.pack_start(lbl2, False, False, 0)

        scroll_r = Gtk.ScrolledWindow()
        scroll_r.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.part_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scroll_r.add(self.part_box)
        right_box.pack_start(scroll_r, True, True, 0)

        # Partition actions
        part_btn_box = Gtk.Box(spacing=6)
        for lbl_txt, fn, cls in [
            ("Create EXT4",  self._create_ext4,  'btn-primary'),
            ("Delete Part",  self._delete_part,  'btn-danger'),
            ("Mount/Unmount",self._toggle_mount,  'btn-flat'),
        ]:
            b = Gtk.Button(label=lbl_txt)
            b.get_style_context().add_class(cls)
            b.connect('clicked', fn)
            part_btn_box.pack_start(b, True, True, 0)
        right_box.pack_start(part_btn_box, False, False, 0)
        paned.pack2(right_box, True, False)

        # Status bar
        self.disk_status = Gtk.Label(label="Select a disk to view details")
        self.disk_status.set_halign(Gtk.Align.START)
        self.disk_status.get_style_context().add_class('disk-info')
        self.main_box.pack_start(self.disk_status, False, False, 6)

        self._reload_disks()

    def _reload_disks(self):
        for child in self.disk_list_box.get_children():
            self.disk_list_box.remove(child)

        disks = get_disks()
        if not disks:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label="No disks found")
            row.add(lbl)
            self.disk_list_box.add(row)
        else:
            for d in disks:
                row = Gtk.ListBoxRow()
                row.disk_data = d
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                box.set_border_width(8)
                name_lbl = Gtk.Label(label=f"/dev/{d['name']}  {d['size']}")
                name_lbl.get_style_context().add_class('disk-name')
                name_lbl.set_halign(Gtk.Align.START)
                model_lbl = Gtk.Label(label=d['model'])
                model_lbl.get_style_context().add_class('disk-info')
                model_lbl.set_halign(Gtk.Align.START)
                box.pack_start(name_lbl, False, False, 0)
                box.pack_start(model_lbl, False, False, 0)
                row.add(box)
                self.disk_list_box.add(row)

        self.disk_list_box.show_all()

    def _on_disk_selected(self, listbox, row):
        if row is None:
            return
        self.selected_disk = row.disk_data
        self.install_data['disk'] = row.disk_data['path']
        self._reload_partitions()

    def _reload_partitions(self):
        for child in self.part_box.get_children():
            self.part_box.remove(child)

        if not self.selected_disk:
            return

        disk_path = self.selected_disk['path']
        self.disk_status.set_text(
            f"Disk: {disk_path}  Size: {self.selected_disk['size']}  Model: {self.selected_disk['model']}")

        parts = get_partitions(disk_path)

        # Disk info header
        out, _ = run(f"parted -s {disk_path} print 2>/dev/null | head -8")
        info_lbl = Gtk.Label(label=out)
        info_lbl.get_style_context().add_class('log')
        info_lbl.set_halign(Gtk.Align.START)
        info_lbl.set_xalign(0)
        self.part_box.pack_start(info_lbl, False, False, 0)

        if not parts:
            lbl = Gtk.Label(label="No partitions found")
            lbl.get_style_context().add_class('status-warn')
            self.part_box.pack_start(lbl, False, False, 0)
        else:
            for p in parts:
                row_box = Gtk.Box(spacing=12)
                row_box.get_style_context().add_class('part-row')
                row_box.set_border_width(6)
                name = Gtk.Label(label=f"/dev/{p['name']}")
                name.get_style_context().add_class('disk-name')
                name.set_width_chars(14)
                size = Gtk.Label(label=p['size'])
                size.get_style_context().add_class('disk-info')
                size.set_width_chars(10)
                fs = Gtk.Label(label=p['fstype'] or 'unknown')
                fs.get_style_context().add_class('disk-info')
                fs.set_width_chars(10)
                mount = Gtk.Label(label=p['mount'] or 'not mounted')
                mount.get_style_context().add_class('disk-info')
                row_box.pack_start(name, False, False, 0)
                row_box.pack_start(size, False, False, 0)
                row_box.pack_start(fs, False, False, 0)
                row_box.pack_start(mount, False, False, 0)
                self.part_box.pack_start(row_box, False, False, 0)

        self.part_box.show_all()

    def _format_disk(self, widget):
        if not self.selected_disk:
            self._msg("Select a disk first!", "warning")
            return
        disk = self.selected_disk['path']
        confirmed = self._confirm(
            "Format Disk",
            f"This will ERASE ALL DATA on {disk}!\n\nAre you sure?")
        if not confirmed:
            return
        self._run_with_log(
            "Formatting disk...",
            [f"parted -s {disk} mklabel gpt",
             f"mkfs.ext4 -F {disk}",
             "sleep 1"],
            lambda: self._reload_partitions())

    def _new_part_table(self, widget):
        if not self.selected_disk:
            self._msg("Select a disk first!", "warning")
            return
        disk = self.selected_disk['path']
        confirmed = self._confirm(
            "New Partition Table",
            f"Create new GPT partition table on {disk}?\nThis will erase all partitions!")
        if not confirmed:
            return
        out, code = run(f"parted -s {disk} mklabel gpt")
        self._msg(
            f"Partition table created on {disk}" if code == 0 else f"Failed: {out}",
            "ok" if code == 0 else "error")
        self._reload_partitions()

    def _create_ext4(self, widget):
        if not self.selected_disk:
            self._msg("Select a disk first!", "warning")
            return
        disk = self.selected_disk['path']
        out, _ = run(f"parted -s {disk} print free 2>/dev/null")
        self._run_with_log(
            "Creating EXT4 partition...",
            [f"parted -s {disk} mkpart primary ext4 0% 100%",
             f"partprobe {disk}",
             "sleep 1",
             f"mkfs.ext4 -F {disk}1 2>/dev/null || true"],
            lambda: self._reload_partitions())

    def _delete_part(self, widget):
        if not self.selected_disk:
            self._msg("Select a disk first!", "warning")
            return
        disk = self.selected_disk['path']
        parts = get_partitions(disk)
        if not parts:
            self._msg("No partitions to delete!", "warning")
            return
        confirmed = self._confirm(
            "Delete Last Partition",
            f"Delete the last partition on {disk}?")
        if not confirmed:
            return
        num = len(parts)
        out, code = run(f"parted -s {disk} rm {num}")
        self._msg(
            f"Partition {num} deleted" if code == 0 else f"Failed: {out}",
            "ok" if code == 0 else "error")
        self._reload_partitions()

    def _toggle_mount(self, widget):
        if not self.selected_disk:
            self._msg("Select a disk first!", "warning")
            return
        parts = get_partitions(self.selected_disk['path'])
        mounted = [p for p in parts if p['mount']]
        if mounted:
            for p in mounted:
                run(f"umount {p['path']} 2>/dev/null || true")
            self._msg("Partitions unmounted", "ok")
        else:
            for p in parts:
                if p['fstype'] and p['fstype'] != 'swap':
                    mnt = f"/mnt/{p['name']}"
                    run(f"mkdir -p {mnt}")
                    run(f"mount {p['path']} {mnt} 2>/dev/null || true")
            self._msg("Partitions mounted to /mnt/", "ok")
        self._reload_partitions()

    # ══════════════════════════════════════════════════════════
    # PAGE: Install OS
    # ══════════════════════════════════════════════════════════
    def _page_install(self):
        topbar = Gtk.Box()
        topbar.get_style_context().add_class('topbar')
        topbar.set_border_width(4)
        title = Gtk.Label(label="Install RIDOS OS")
        title.get_style_context().add_class('page-title')
        topbar.pack_start(title, False, False, 8)
        self.main_box.pack_start(topbar, False, False, 0)

        # Notebook for install steps
        self.notebook = Gtk.Notebook()
        self.notebook.set_show_tabs(False)
        self.notebook.set_border_width(8)
        self.main_box.pack_start(self.notebook, True, True, 0)

        pages = [
            ("Disk",     self._install_page_disk()),
            ("User",     self._install_page_user()),
            ("Settings", self._install_page_settings()),
            ("Confirm",  self._install_page_confirm()),
            ("Progress", self._install_page_progress()),
            ("Done",     self._install_page_done()),
        ]
        for name, page in pages:
            lbl = Gtk.Label(label=name)
            self.notebook.append_page(page, lbl)

        # Nav buttons
        nav = Gtk.Box(spacing=8)
        nav.set_border_width(10)
        self.install_back_btn = Gtk.Button(label="Back")
        self.install_back_btn.get_style_context().add_class('btn-flat')
        self.install_back_btn.connect('clicked', self._install_back)
        self.install_next_btn = Gtk.Button(label="Next")
        self.install_next_btn.get_style_context().add_class('btn-primary')
        self.install_next_btn.connect('clicked', self._install_next)
        self.install_step_lbl = Gtk.Label(label="Step 1 of 4")
        self.install_step_lbl.get_style_context().add_class('disk-info')
        nav.pack_start(self.install_back_btn, False, False, 0)
        nav.pack_start(self.install_step_lbl, True, True, 0)
        nav.pack_end(self.install_next_btn, False, False, 0)
        self.main_box.pack_start(nav, False, False, 0)
        self._update_install_nav()

    def _install_page_disk(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(16)
        lbl = Gtk.Label(label="Select Target Disk")
        lbl.get_style_context().add_class('page-title')
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        warn = Gtk.Label()
        warn.set_markup('<span foreground="#F59E0B">WARNING: All data on selected disk will be erased!</span>')
        warn.set_halign(Gtk.Align.START)
        box.pack_start(warn, False, False, 0)

        disks = get_disks()
        self.install_disk_combo = Gtk.ComboBoxText()
        for d in disks:
            self.install_disk_combo.append_text(
                f"/dev/{d['name']}  —  {d['size']}  —  {d['model']}")
        if disks:
            self.install_disk_combo.set_active(0)
            self.install_data['disk'] = disks[0]['path']

        def on_disk(combo):
            idx = combo.get_active()
            if 0 <= idx < len(disks):
                self.install_data['disk'] = disks[idx]['path']

        self.install_disk_combo.connect('changed', on_disk)
        box.pack_start(self.install_disk_combo, False, False, 0)

        # Partition preview
        prev = Gtk.Label()
        prev.set_markup(
            '<span foreground="#6B7280" size="small">\n'
            'Partitions to be created:\n'
            '  1.  512 MB   EFI  (FAT32)\n'
            '  2.  4 GB     Swap\n'
            '  3.  Remaining  Root  (EXT4)\n</span>')
        prev.set_halign(Gtk.Align.START)
        box.pack_start(prev, False, False, 0)
        return box

    def _install_page_user(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(16)
        lbl = Gtk.Label(label="User Account")
        lbl.get_style_context().add_class('page-title')
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        fields = [
            ("Full Name",  'fullname',  'RIDOS User', False),
            ("Username",   'username',  'ridos',      False),
            ("Password",   'password',  'ridos',      True),
            ("Hostname",   'hostname',  'ridos-os',   False),
        ]
        for i, (label, key, default, secret) in enumerate(fields):
            lbl2 = Gtk.Label(label=f"{label}:")
            lbl2.set_halign(Gtk.Align.END)
            entry = Gtk.Entry()
            entry.set_text(self.install_data.get(key, default))
            entry.get_style_context().add_class('input')
            entry.set_width_chars(28)
            if secret:
                entry.set_visibility(False)
            def make_cb(k):
                return lambda e: self.install_data.__setitem__(k, e.get_text())
            entry.connect('changed', make_cb(key))
            grid.attach(lbl2, 0, i, 1, 1)
            grid.attach(entry, 1, i, 1, 1)
        box.pack_start(grid, False, False, 0)
        return box

    def _install_page_settings(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(16)
        lbl = Gtk.Label(label="System Settings")
        lbl.get_style_context().add_class('page-title')
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        row = Gtk.Box(spacing=12)
        tz_lbl = Gtk.Label(label="Timezone:")
        tz_lbl.set_width_chars(12)
        out, _ = run("timedatectl list-timezones 2>/dev/null | head -80")
        zones = out.strip().split('\n') if out.strip() else ["Asia/Baghdad", "UTC"]
        self.tz_combo = Gtk.ComboBoxText()
        default_idx = 0
        for i, z in enumerate(zones):
            self.tz_combo.append_text(z)
            if z == "Asia/Baghdad":
                default_idx = i
        self.tz_combo.set_active(default_idx)
        self.install_data['timezone'] = zones[default_idx] if zones else "Asia/Baghdad"
        self.tz_combo.connect('changed', lambda c: self.install_data.__setitem__(
            'timezone', c.get_active_text() or 'Asia/Baghdad'))
        row.pack_start(tz_lbl, False, False, 0)
        row.pack_start(self.tz_combo, False, False, 0)
        box.pack_start(row, False, False, 0)
        return box

    def _install_page_confirm(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(16)
        lbl = Gtk.Label(label="Confirm Installation")
        lbl.get_style_context().add_class('page-title')
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        self.confirm_summary = Gtk.Label(label="")
        self.confirm_summary.set_halign(Gtk.Align.START)
        box.pack_start(self.confirm_summary, False, False, 0)

        warn = Gtk.Label()
        warn.set_markup(
            '<span foreground="#EF4444" size="large">'
            '<b>ALL DATA ON THE DISK WILL BE ERASED!</b></span>')
        warn.set_justify(Gtk.Justification.CENTER)
        box.pack_start(warn, False, False, 20)

        note = Gtk.Label()
        note.set_markup('<span foreground="#9CA3AF">Click "Install" to begin installation.</span>')
        box.pack_start(note, False, False, 0)
        return box

    def _install_page_progress(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(16)
        self.progress_title = Gtk.Label(label="Installing RIDOS OS...")
        self.progress_title.get_style_context().add_class('page-title')
        self.progress_title.set_halign(Gtk.Align.START)
        box.pack_start(self.progress_title, False, False, 0)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.get_style_context().add_class('progress')
        box.pack_start(self.progress_bar, False, False, 0)

        self.progress_status = Gtk.Label(label="Preparing...")
        self.progress_status.set_halign(Gtk.Align.START)
        box.pack_start(self.progress_status, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(300)
        self.log_buf = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buf)
        self.log_view.get_style_context().add_class('log')
        self.log_view.set_editable(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scroll.add(self.log_view)
        box.pack_start(scroll, True, True, 0)
        return box

    def _install_page_done(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_border_width(24)
        icon = Gtk.Label(label="RIDOS OS Installed!")
        icon.get_style_context().add_class('status-ok')
        icon.set_halign(Gtk.Align.CENTER)
        box.pack_start(icon, False, False, 20)

        self.done_info = Gtk.Label(label="")
        self.done_info.set_halign(Gtk.Align.CENTER)
        box.pack_start(self.done_info, False, False, 0)

        reboot_btn = Gtk.Button(label="Reboot Now")
        reboot_btn.get_style_context().add_class('btn-success')
        reboot_btn.connect('clicked', lambda w: run("reboot"))
        reboot_btn.set_halign(Gtk.Align.CENTER)
        box.pack_start(reboot_btn, False, False, 20)
        return box

    def _update_install_nav(self):
        page = self.notebook.get_current_page()
        total = 4
        self.install_step_lbl.set_text(f"Step {page+1} of {total}")
        self.install_back_btn.set_sensitive(page > 0 and page < 4)
        self.install_next_btn.set_sensitive(page < 4)
        if page == 3:
            self.install_next_btn.set_label("Install!")
            self.install_next_btn.get_style_context().add_class('btn-danger')
            self.install_next_btn.get_style_context().remove_class('btn-primary')
            # Update summary
            d = self.install_data
            self.confirm_summary.set_markup(
                f'<span foreground="#E9D5FF">'
                f'<b>Disk:</b>      {d.get("disk","?")}\n'
                f'<b>Username:</b>  {d.get("username","?")}\n'
                f'<b>Hostname:</b>  {d.get("hostname","?")}\n'
                f'<b>Timezone:</b>  {d.get("timezone","?")}\n'
                f'</span>')
        elif page >= 4:
            self.install_next_btn.set_sensitive(False)
            self.install_back_btn.set_sensitive(False)
        else:
            self.install_next_btn.set_label("Next")
            self.install_next_btn.get_style_context().remove_class('btn-danger')
            self.install_next_btn.get_style_context().add_class('btn-primary')

    def _install_next(self, widget):
        page = self.notebook.get_current_page()
        if page == 3:
            self.notebook.set_current_page(4)
            self._update_install_nav()
            threading.Thread(target=self._do_install, daemon=True).start()
        elif page < 4:
            self.notebook.set_current_page(page + 1)
            self._update_install_nav()

    def _install_back(self, widget):
        page = self.notebook.get_current_page()
        if page > 0:
            self.notebook.set_current_page(page - 1)
            self._update_install_nav()

    def _log(self, msg):
        def _do(m):
            end = self.log_buf.get_end_iter()
            self.log_buf.insert(end, m + "\n")
            self.log_view.scroll_to_iter(
                self.log_buf.get_end_iter(), 0, False, 0, 1)
        GLib.idle_add(_do, msg)

    def _set_progress(self, frac, status):
        GLib.idle_add(self.progress_bar.set_fraction, frac)
        GLib.idle_add(self.progress_status.set_text, status)

    def _do_install(self):
        d = self.install_data
        disk     = d['disk']
        username = d['username']
        password = d['password']
        hostname = d['hostname']
        timezone = d['timezone']
        target   = '/mnt/ridos-install'

        if 'nvme' in disk:
            efi = disk + 'p1'; swap = disk + 'p2'; root = disk + 'p3'
        else:
            efi = disk + '1';  swap = disk + '2';  root = disk + '3'

        try:
            # 1. Partition
            self._set_progress(0.05, "Partitioning disk...")
            self._log(f"[1/7] Partitioning {disk}...")
            for cmd in [
                f"parted -s {disk} mklabel gpt",
                f"parted -s {disk} mkpart ESP fat32 1MiB 512MiB",
                f"parted -s {disk} set 1 esp on",
                f"parted -s {disk} mkpart primary linux-swap 512MiB 4608MiB",
                f"parted -s {disk} mkpart primary ext4 4608MiB 100%",
                "sleep 2",
                f"partprobe {disk}",
            ]:
                out, code = run(cmd)
                self._log(f"  {'OK' if code==0 else 'WARN'}: {cmd}")

            # 2. Format
            self._set_progress(0.12, "Formatting partitions...")
            self._log("[2/7] Formatting...")
            for cmd, desc in [
                (f"mkfs.fat -F32 -n EFI {efi}", "EFI"),
                (f"mkswap {swap}",               "Swap"),
                (f"mkfs.ext4 -F -L RIDOS {root}","Root"),
            ]:
                out, code = run(cmd, 60)
                self._log(f"  {desc}: {'OK' if code==0 else out[:80]}")
                if code != 0 and desc == "Root":
                    raise Exception(f"Format failed: {out}")

            # 3. Mount
            self._set_progress(0.18, "Mounting target...")
            self._log("[3/7] Mounting...")
            run(f"mkdir -p {target}")
            out, code = run(f"mount {root} {target}")
            if code != 0:
                raise Exception(f"Cannot mount root: {out}")
            run(f"mkdir -p {target}/boot/efi")
            run(f"mount {efi} {target}/boot/efi")
            run(f"swapon {swap} 2>/dev/null || true")

            # 4. Find and copy squashfs
            self._set_progress(0.20, "Finding system image...")
            self._log("[4/7] Locating system image...")
            sq = find_squashfs()
            if not sq:
                raise Exception("Cannot find filesystem.squashfs!")
            self._log(f"  Found: {sq}")

            # Fix permissions
            run(f"chmod 644 {sq} 2>/dev/null || true")

            # Mount squashfs
            run("mkdir -p /mnt/ridos-sq")
            out, code = run(f"mount -t squashfs -o loop,ro {sq} /mnt/ridos-sq")
            if code != 0:
                raise Exception(f"Cannot mount squashfs: {out}")

            self._set_progress(0.25, "Copying files (10-20 min)...")
            self._log("[5/7] Copying RIDOS OS to disk...")
            out, code = run(
                f"rsync -aAXH "
                f"--exclude=/proc --exclude=/sys --exclude=/dev "
                f"--exclude=/run --exclude=/tmp --exclude=/mnt "
                f"--exclude=/media --exclude=/lost+found "
                f"/mnt/ridos-sq/ {target}/",
                timeout=1800)
            run("umount /mnt/ridos-sq 2>/dev/null; rmdir /mnt/ridos-sq 2>/dev/null || true")
            if code != 0:
                raise Exception(f"Copy failed (rsync exit {code}): {out[-300:]}")
            self._log("  Copy complete!")

            # 5. Configure
            self._set_progress(0.75, "Configuring system...")
            self._log("[6/7] Configuring installed system...")

            for dd in ['proc','sys','dev','run','tmp']:
                run(f"mkdir -p {target}/{dd}")

            # fstab
            ru, _ = run(f"blkid -s UUID -o value {root}")
            eu, _ = run(f"blkid -s UUID -o value {efi}")
            su, _ = run(f"blkid -s UUID -o value {swap}")
            with open(f"{target}/etc/fstab", 'w') as f:
                f.write(f"UUID={ru.strip()}  /          ext4  defaults,noatime  0 1\n")
                f.write(f"UUID={eu.strip()}  /boot/efi  vfat  umask=0077        0 2\n")
                f.write(f"UUID={su.strip()}  none       swap  sw                0 0\n")
            self._log("  fstab written")

            with open(f"{target}/etc/hostname", 'w') as f:
                f.write(hostname + "\n")

            run(f"chroot {target} ln -sf /usr/share/zoneinfo/{timezone} /etc/localtime 2>/dev/null || true")

            # User
            run(f"chroot {target} userdel -r {username} 2>/dev/null || true")
            run(f"chroot {target} useradd -m -s /bin/bash -G sudo,audio,video,netdev,plugdev {username}")
            run(f"echo '{username}:{password}' | chroot {target} chpasswd")
            run(f"echo 'root:{password}' | chroot {target} chpasswd")
            self._log(f"  User '{username}' created")

            # Remove live packages
            run(f"chroot {target} apt-get remove -y live-boot live-boot-initramfs-tools 2>/dev/null || true")

            # Bind mounts for GRUB
            for dd in ['dev','dev/pts','proc','sys']:
                run(f"mount --bind /{dd} {target}/{dd}")

            # Update initramfs
            self._set_progress(0.85, "Updating initramfs...")
            run(f"chroot {target} update-initramfs -u -k all 2>/dev/null || true", 120)
            self._log("  initramfs updated")

            # 6. GRUB
            self._set_progress(0.90, "Installing bootloader...")
            self._log(f"[7/7] Installing GRUB on {disk}...")
            out, code = run(
                f"chroot {target} grub-install "
                f"--target=i386-pc --recheck --force --no-floppy {disk}")
            self._log(f"  grub-install: {'OK' if code==0 else out[-200:]}")

            out2, code2 = run(f"chroot {target} update-grub")
            self._log(f"  update-grub: {'OK' if code2==0 else out2[-200:]}")

            # Unmount
            for dd in ['sys','proc','dev/pts','dev']:
                run(f"umount {target}/{dd} 2>/dev/null || true")
            run(f"umount {target}/boot/efi 2>/dev/null || true")
            run(f"umount {target} 2>/dev/null || true")
            run(f"swapoff {swap} 2>/dev/null || true")

            self._set_progress(1.0, "Done!")
            self._log("\n=== Installation complete! ===")

            GLib.idle_add(self._install_done)

        except Exception as e:
            self._log(f"\nFATAL ERROR: {e}")
            self._set_progress(0, f"FAILED: {e}")
            GLib.idle_add(self._msg, str(e), "error")

    def _install_done(self):
        self.done_info.set_markup(
            f'<span foreground="#E9D5FF">\n'
            f'Username: <b>{self.install_data["username"]}</b>\n'
            f'Password: <b>{self.install_data["password"]}</b>\n\n'
            f'Remove USB and reboot!\n</span>')
        self.notebook.set_current_page(5)
        self._update_install_nav()

    # ══════════════════════════════════════════════════════════
    # PAGE: About
    # ══════════════════════════════════════════════════════════
    def _page_about(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(24)
        lbl = Gtk.Label()
        lbl.set_markup(
            '<span foreground="#C4B5FD" size="xx-large"><b>RIDOS OS</b></span>\n'
            '<span foreground="#E9D5FF">v1.0 Baghdad</span>\n\n'
            '<span foreground="#9CA3AF">'
            'AI-Powered Linux for IT Professionals\n\n'
            'Disk Manager + OS Installer\n'
            'No Calamares - Pure Python GTK3\n\n'
            'License: GPL v3\n'
            'github.com/alkinanireyad/RIDOS-OS'
            '</span>')
        lbl.set_justify(Gtk.Justification.CENTER)
        box.pack_start(lbl, True, True, 0)
        self.main_box.pack_start(box, True, True, 0)

    # ── Helpers ───────────────────────────────────────────────
    def _confirm(self, title, message):
        dialog = Gtk.MessageDialog(
            parent=self, flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=title)
        dialog.format_secondary_text(message)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES

    def _msg(self, message, kind="info"):
        types = {
            "info":    Gtk.MessageType.INFO,
            "warning": Gtk.MessageType.WARNING,
            "error":   Gtk.MessageType.ERROR,
            "ok":      Gtk.MessageType.INFO,
        }
        dialog = Gtk.MessageDialog(
            parent=self, flags=0,
            message_type=types.get(kind, Gtk.MessageType.INFO),
            buttons=Gtk.ButtonsType.OK,
            text=message)
        dialog.run()
        dialog.destroy()

    def _run_with_log(self, title, commands, callback=None):
        win = Gtk.Dialog(title=title, parent=self, flags=0)
        win.set_default_size(500, 300)
        box = win.get_content_area()
        buf = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=buf)
        tv.get_style_context().add_class('log')
        tv.set_editable(False)
        sc = Gtk.ScrolledWindow()
        sc.add(tv)
        sc.set_min_content_height(200)
        box.pack_start(sc, True, True, 8)
        win.show_all()

        def do_run():
            for cmd in commands:
                out, code = run(cmd)
                GLib.idle_add(lambda o=f"$ {cmd}\n{out}\n": buf.insert(buf.get_end_iter(), o))
                time.sleep(0.3)
            GLib.idle_add(win.destroy)
            if callback:
                GLib.idle_add(callback)

        threading.Thread(target=do_run, daemon=True).start()
        win.run()


def main():
    # Fix DISPLAY for sudo - GTK needs it
    if 'DISPLAY' not in os.environ:
        os.environ['DISPLAY'] = ':0'
    if 'XAUTHORITY' not in os.environ:
        # Try common locations
        for xauth in [
            f"/home/{os.environ.get('SUDO_USER','ridos')}/.Xauthority",
            "/home/ridos/.Xauthority",
            "/root/.Xauthority",
        ]:
            if os.path.exists(xauth):
                os.environ['XAUTHORITY'] = xauth
                break

    if os.geteuid() != 0:
        # Not root - relaunch with sudo preserving environment
        env_args = f"DISPLAY={os.environ.get('DISPLAY',':0')} "
        xauth = os.environ.get('XAUTHORITY','')
        if xauth:
            env_args += f"XAUTHORITY={xauth} "
        os.execvp('sudo', ['sudo', '-E', 'python3',
                           '/opt/ridos/bin/ridos-installer.py'])
        return

    app = RIDOSTool()
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
