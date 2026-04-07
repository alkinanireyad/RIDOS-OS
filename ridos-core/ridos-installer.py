#!/usr/bin/env python3
"""
RIDOS OS Installer - Custom GTK3 Python Installer
Replaces Calamares completely
Run: sudo python3 /opt/ridos/bin/ridos-installer.py
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango
import subprocess, threading, os, re, json, time

# ── Colors ────────────────────────────────────────────────────
CSS = b"""
window { background-color: #0F0A1E; }
.header { background-color: #1E1B4B; padding: 20px; }
.title { color: #C4B5FD; font-size: 24px; font-weight: bold; }
.subtitle { color: #E9D5FF; font-size: 13px; }
.step-label { color: #7C3AED; font-size: 13px; font-weight: bold; }
.step-done { color: #10B981; font-size: 13px; }
.step-wait { color: #6B7280; font-size: 13px; }
.card { background-color: #1E1B4B; border-radius: 8px; padding: 16px; margin: 8px; }
.btn-primary { background-color: #7C3AED; color: white; font-size: 14px;
               font-weight: bold; border-radius: 6px; padding: 10px 24px; border: none; }
.btn-primary:hover { background-color: #6D28D9; }
.btn-secondary { background-color: #374151; color: #E9D5FF; font-size: 13px;
                 border-radius: 6px; padding: 8px 18px; border: none; }
.btn-danger { background-color: #DC2626; color: white; font-size: 14px;
              font-weight: bold; border-radius: 6px; padding: 10px 24px; border: none; }
.input-field { background-color: #111827; color: #E9D5FF; border: 1px solid #7C3AED;
               border-radius: 4px; padding: 8px; font-size: 13px; }
.progress-bar trough { background-color: #374151; border-radius: 4px; }
.progress-bar progress { background-color: #7C3AED; border-radius: 4px; }
.log-view { background-color: #111827; color: #A5F3FC; font-family: monospace;
            font-size: 12px; border-radius: 4px; padding: 8px; }
.warning { color: #F59E0B; font-size: 12px; }
.error { color: #EF4444; font-size: 13px; font-weight: bold; }
.success { color: #10B981; font-size: 13px; font-weight: bold; }
label { color: #E9D5FF; }
"""

def run(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", 1
    except Exception as e:
        return str(e), 1

def get_disks():
    out, _ = run("lsblk -d -o NAME,SIZE,MODEL,TYPE --json 2>/dev/null")
    disks = []
    try:
        data = json.loads(out)
        for d in data.get('blockdevices', []):
            if d.get('type') == 'disk' and 'loop' not in d['name']:
                disks.append({
                    'name': d['name'],
                    'size': d.get('size', '?'),
                    'model': d.get('model', 'Unknown') or 'Unknown',
                    'path': f"/dev/{d['name']}"
                })
    except:
        out2, _ = run("lsblk -d -o NAME,SIZE -n | grep -v loop")
        for line in out2.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if parts:
                    disks.append({'name': parts[0], 'size': parts[1] if len(parts)>1 else '?',
                                  'model': '', 'path': f"/dev/{parts[0]}"})
    return disks

def get_timezones():
    out, _ = run("timedatectl list-timezones 2>/dev/null | head -100")
    zones = out.strip().split('\n') if out.strip() else ["Asia/Baghdad", "UTC", "Europe/London"]
    return zones if zones else ["Asia/Baghdad", "UTC"]

def find_squashfs():
    paths = [
        "/run/live/medium/live/filesystem.squashfs",
        "/lib/live/mount/medium/live/filesystem.squashfs",
        "/cdrom/live/filesystem.squashfs",
        "/isodevice/live/filesystem.squashfs",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    out, _ = run("find /run /lib/live /cdrom /media -name 'filesystem.squashfs' 2>/dev/null | head -1")
    return out.strip() if out.strip() else None

# ════════════════════════════════════════════════════════════════
class RIDOSInstaller(Gtk.Window):

    def __init__(self):
        super().__init__(title="RIDOS OS Installer v1.0")
        self.set_default_size(800, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.connect("delete-event", Gtk.main_quit)

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Installation data
        self.data = {
            'disk': None,
            'username': 'ridos',
            'password': 'ridos',
            'hostname': 'ridos-os',
            'timezone': 'Asia/Baghdad',
            'fullname': 'RIDOS User',
        }

        self.current_step = 0
        self.steps = [
            "Welcome",
            "Select Disk",
            "User Setup",
            "Timezone",
            "Summary",
            "Installing",
            "Complete",
        ]

        self._build_ui()
        self._show_step(0)

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(main_box)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.get_style_context().add_class('header')
        header.set_border_width(0)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.title_label = Gtk.Label(label="RIDOS OS Installer")
        self.title_label.get_style_context().add_class('title')
        self.title_label.set_halign(Gtk.Align.START)
        self.subtitle_label = Gtk.Label(label="Step 1 of 7")
        self.subtitle_label.get_style_context().add_class('subtitle')
        self.subtitle_label.set_halign(Gtk.Align.START)
        left.pack_start(self.title_label, False, False, 0)
        left.pack_start(self.subtitle_label, False, False, 0)
        header.pack_start(left, True, True, 20)
        main_box.pack_start(header, False, False, 0)

        # Steps indicator
        steps_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        steps_bar.set_border_width(12)
        self.step_labels = []
        for i, s in enumerate(self.steps):
            lbl = Gtk.Label(label=f"{'>' if i==0 else '○'} {s}")
            lbl.get_style_context().add_class('step-wait')
            steps_bar.pack_start(lbl, True, True, 0)
            self.step_labels.append(lbl)
        main_box.pack_start(steps_bar, False, False, 0)

        sep = Gtk.Separator()
        main_box.pack_start(sep, False, False, 0)

        # Content area
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.set_border_width(20)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.content)
        main_box.pack_start(scroll, True, True, 0)

        sep2 = Gtk.Separator()
        main_box.pack_start(sep2, False, False, 0)

        # Navigation buttons
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        nav.set_border_width(16)
        self.btn_back = Gtk.Button(label="Back")
        self.btn_back.get_style_context().add_class('btn-secondary')
        self.btn_back.connect('clicked', self._go_back)
        self.btn_next = Gtk.Button(label="Next")
        self.btn_next.get_style_context().add_class('btn-primary')
        self.btn_next.connect('clicked', self._go_next)
        nav.pack_start(self.btn_back, False, False, 0)
        nav.pack_end(self.btn_next, False, False, 0)
        main_box.pack_start(nav, False, False, 0)

    def _clear_content(self):
        for child in self.content.get_children():
            self.content.remove(child)

    def _update_steps(self, current):
        for i, lbl in enumerate(self.step_labels):
            for cls in ['step-label', 'step-done', 'step-wait']:
                lbl.get_style_context().remove_class(cls)
            if i < current:
                lbl.set_text(f"+ {self.steps[i]}")
                lbl.get_style_context().add_class('step-done')
            elif i == current:
                lbl.set_text(f"> {self.steps[i]}")
                lbl.get_style_context().add_class('step-label')
            else:
                lbl.set_text(f"o {self.steps[i]}")
                lbl.get_style_context().add_class('step-wait')

    def _show_step(self, step):
        self.current_step = step
        self._clear_content()
        self._update_steps(step)
        self.subtitle_label.set_text(f"Step {step+1} of {len(self.steps)}: {self.steps[step]}")

        steps_fn = [
            self._step_welcome,
            self._step_disk,
            self._step_user,
            self._step_timezone,
            self._step_summary,
            self._step_install,
            self._step_complete,
        ]
        steps_fn[step]()
        self.content.show_all()

        self.btn_back.set_sensitive(step > 0 and step < 5)
        self.btn_next.set_sensitive(step < 5)
        if step == 4:
            self.btn_next.set_label("Install Now!")
            self.btn_next.get_style_context().add_class('btn-danger')
        elif step >= 5:
            self.btn_next.set_sensitive(False)
            self.btn_back.set_sensitive(False)
        else:
            self.btn_next.set_label("Next")

    def _go_next(self, widget):
        if self.current_step == 4:
            self._show_step(5)
            threading.Thread(target=self._do_install, daemon=True).start()
        elif self.current_step < 5:
            self._show_step(self.current_step + 1)

    def _go_back(self, widget):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    # ── Step 0: Welcome ───────────────────────────────────────
    def _step_welcome(self):
        self.title_label.set_text("Welcome to RIDOS OS")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content.pack_start(box, True, True, 0)

        lbl = Gtk.Label()
        lbl.set_markup(
            '<span size="large" foreground="#C4B5FD"><b>RIDOS OS v1.0 Baghdad</b></span>\n'
            '<span foreground="#E9D5FF">AI-Powered Linux for IT Professionals</span>')
        lbl.set_justify(Gtk.Justification.CENTER)
        box.pack_start(lbl, False, False, 20)

        info = Gtk.Label()
        info.set_markup(
            '<span foreground="#9CA3AF">This installer will:\n\n'
            '  1. Partition your selected disk\n'
            '  2. Install RIDOS OS\n'
            '  3. Set up your user account\n'
            '  4. Install the bootloader (GRUB)\n\n'
            'Requirements:\n'
            '  - Minimum 20GB free disk space\n'
            '  - Minimum 2GB RAM\n\n'
            '<b>WARNING: Selected disk will be completely erased!</b></span>')
        info.set_justify(Gtk.Justification.LEFT)
        info.set_halign(Gtk.Align.CENTER)
        box.pack_start(info, False, False, 0)

    # ── Step 1: Disk Selection ────────────────────────────────
    def _step_disk(self):
        self.title_label.set_text("Select Installation Disk")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.pack_start(box, True, True, 0)

        warn = Gtk.Label()
        warn.set_markup('<span foreground="#F59E0B"><b>WARNING: All data on selected disk will be erased!</b></span>')
        box.pack_start(warn, False, False, 0)

        disks = get_disks()
        if not disks:
            err = Gtk.Label(label="No disks found!")
            err.get_style_context().add_class('error')
            box.pack_start(err, False, False, 0)
            return

        lbl = Gtk.Label(label="Select target disk:")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        self.disk_combo = Gtk.ComboBoxText()
        for d in disks:
            self.disk_combo.append_text(
                f"/dev/{d['name']} — {d['size']} — {d['model']}")
        self.disk_combo.set_active(0)
        if disks:
            self.data['disk'] = disks[0]['path']
        box.pack_start(self.disk_combo, False, False, 0)

        def on_disk_changed(combo):
            idx = combo.get_active()
            if 0 <= idx < len(disks):
                self.data['disk'] = disks[idx]['path']

        self.disk_combo.connect('changed', on_disk_changed)

        # Partition preview
        preview = Gtk.Label()
        preview.set_markup(
            '<span foreground="#6B7280" size="small">\n'
            'Partition layout:\n'
            '  /dev/sdX1  512MB   EFI System Partition\n'
            '  /dev/sdX2  4GB     Swap\n'
            '  /dev/sdX3  Rest    Root (ext4) - RIDOS OS\n</span>')
        preview.set_halign(Gtk.Align.START)
        box.pack_start(preview, False, False, 8)

    # ── Step 2: User Setup ────────────────────────────────────
    def _step_user(self):
        self.title_label.set_text("User Account Setup")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.pack_start(box, True, True, 0)

        fields = [
            ('Full Name',  'fullname',  'RIDOS User',  False),
            ('Username',   'username',  'ridos',       False),
            ('Password',   'password',  'ridos',       True),
            ('Hostname',   'hostname',  'ridos-os',    False),
        ]

        for label, key, default, secret in fields:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            lbl = Gtk.Label(label=f"{label}:")
            lbl.set_width_chars(12)
            lbl.set_halign(Gtk.Align.END)
            entry = Gtk.Entry()
            entry.set_text(self.data.get(key, default))
            entry.get_style_context().add_class('input-field')
            entry.set_width_chars(30)
            if secret:
                entry.set_visibility(False)

            def make_cb(k):
                def cb(e):
                    self.data[k] = e.get_text()
                return cb

            entry.connect('changed', make_cb(key))
            row.pack_start(lbl, False, False, 0)
            row.pack_start(entry, False, False, 0)
            box.pack_start(row, False, False, 0)

    # ── Step 3: Timezone ──────────────────────────────────────
    def _step_timezone(self):
        self.title_label.set_text("Select Timezone")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.pack_start(box, True, True, 0)

        lbl = Gtk.Label(label="Timezone:")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        zones = get_timezones()
        self.tz_combo = Gtk.ComboBoxText()
        default_idx = 0
        for i, z in enumerate(zones):
            self.tz_combo.append_text(z)
            if z == "Asia/Baghdad":
                default_idx = i
        self.tz_combo.set_active(default_idx)
        self.data['timezone'] = zones[default_idx]

        def on_tz(combo):
            self.data['timezone'] = combo.get_active_text()

        self.tz_combo.connect('changed', on_tz)
        box.pack_start(self.tz_combo, False, False, 0)

    # ── Step 4: Summary ───────────────────────────────────────
    def _step_summary(self):
        self.title_label.set_text("Installation Summary")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.pack_start(box, True, True, 0)

        summary = Gtk.Label()
        summary.set_markup(
            f'<span foreground="#E9D5FF">'
            f'<b>Disk:</b>      {self.data["disk"]}\n'
            f'<b>Username:</b>  {self.data["username"]}\n'
            f'<b>Hostname:</b>  {self.data["hostname"]}\n'
            f'<b>Timezone:</b>  {self.data["timezone"]}\n'
            f'</span>')
        summary.set_halign(Gtk.Align.START)
        box.pack_start(summary, False, False, 0)

        warn = Gtk.Label()
        warn.set_markup(
            '<span foreground="#EF4444" size="large">'
            '<b>ALL DATA ON THE SELECTED DISK WILL BE PERMANENTLY ERASED!</b>'
            '</span>')
        warn.set_justify(Gtk.Justification.CENTER)
        box.pack_start(warn, False, False, 20)

        note = Gtk.Label()
        note.set_markup('<span foreground="#9CA3AF">Click "Install Now!" to begin.</span>')
        note.set_halign(Gtk.Align.CENTER)
        box.pack_start(note, False, False, 0)

    # ── Step 5: Installing ────────────────────────────────────
    def _step_install(self):
        self.title_label.set_text("Installing RIDOS OS...")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.pack_start(box, True, True, 0)

        self.install_status = Gtk.Label(label="Preparing installation...")
        self.install_status.get_style_context().add_class('step-label')
        self.install_status.set_halign(Gtk.Align.START)
        box.pack_start(self.install_status, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.get_style_context().add_class('progress-bar')
        self.progress.set_pulse_step(0.1)
        box.pack_start(self.progress, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(280)
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.get_style_context().add_class('log-view')
        self.log_view.set_editable(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scroll.add(self.log_view)
        box.pack_start(scroll, True, True, 0)

    def _log(self, msg):
        def _do(m):
            end = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end, m + "\n")
            self.log_view.scroll_to_iter(
                self.log_buffer.get_end_iter(), 0.0, False, 0.0, 1.0)
        GLib.idle_add(_do, msg)

    def _set_status(self, msg, progress=None):
        GLib.idle_add(self.install_status.set_text, msg)
        if progress is not None:
            GLib.idle_add(self.progress.set_fraction, progress)

    def _do_install(self):
        disk = self.data['disk']
        username = self.data['username']
        password = self.data['password']
        hostname = self.data['hostname']
        timezone = self.data['timezone']
        fullname = self.data['fullname']

        # Partition names
        if 'nvme' in disk:
            efi  = disk + 'p1'
            swap = disk + 'p2'
            root = disk + 'p3'
        else:
            efi  = disk + '1'
            swap = disk + '2'
            root = disk + '3'

        target = '/mnt/ridos-install'

        try:
            # ── Step 1: Partition ─────────────────────────────
            self._set_status("Partitioning disk...", 0.05)
            self._log(f"Partitioning {disk}...")
            cmds = [
                f"parted -s {disk} mklabel gpt",
                f"parted -s {disk} mkpart primary fat32 1MiB 512MiB",
                f"parted -s {disk} set 1 esp on",
                f"parted -s {disk} mkpart primary linux-swap 512MiB 4608MiB",
                f"parted -s {disk} mkpart primary ext4 4608MiB 100%",
                "sleep 2", "partprobe " + disk,
            ]
            for cmd in cmds:
                out, code = run(cmd)
                self._log(f"  {cmd.split()[0]}: {'OK' if code==0 else 'WARN'}")

            # ── Step 2: Format ────────────────────────────────
            self._set_status("Formatting partitions...", 0.10)
            self._log("Formatting partitions...")
            for cmd in [
                f"mkfs.fat -F32 {efi}",
                f"mkswap {swap}",
                f"mkfs.ext4 -F {root}",
            ]:
                out, code = run(cmd)
                self._log(f"  {cmd}: {'OK' if code==0 else out[:80]}")

            # ── Step 3: Mount ─────────────────────────────────
            self._set_status("Mounting target...", 0.15)
            self._log("Mounting target system...")
            run(f"mkdir -p {target}")
            run(f"mount {root} {target}")
            run(f"mkdir -p {target}/boot/efi")
            run(f"mount {efi} {target}/boot/efi")
            run(f"swapon {swap} 2>/dev/null || true")

            # ── Step 4: Find squashfs ─────────────────────────
            self._set_status("Locating system image...", 0.18)
            squashfs = find_squashfs()
            if not squashfs:
                raise Exception("Cannot find filesystem.squashfs!")
            self._log(f"Found system image: {squashfs}")

            # ── Step 5: Copy system ───────────────────────────
            self._set_status("Copying RIDOS OS (10-20 min)...", 0.20)
            self._log("Mounting squashfs...")
            run("mkdir -p /mnt/ridos-squashfs")
            out, code = run(f"mount -t squashfs -o loop,ro {squashfs} /mnt/ridos-squashfs")
            if code != 0:
                # Try chmod fix
                run(f"chmod 644 {squashfs}")
                out, code = run(f"mount -t squashfs -o loop,ro {squashfs} /mnt/ridos-squashfs")
            if code != 0:
                raise Exception(f"Cannot mount squashfs: {out}")

            self._log("Copying files (this takes time)...")
            out, code = run(
                f"rsync -aAX --progress "
                f"--exclude=/proc --exclude=/sys --exclude=/dev "
                f"--exclude=/run --exclude=/tmp "
                f"/mnt/ridos-squashfs/ {target}/",
                timeout=1800)
            self._log(f"rsync: {'OK' if code==0 else f'FAILED: {out[-200:]}'}")
            if code != 0:
                raise Exception(f"rsync failed: {out[-200:]}")
            run("umount /mnt/ridos-squashfs && rmdir /mnt/ridos-squashfs")

            # ── Step 6: Configure system ──────────────────────
            self._set_status("Configuring system...", 0.70)
            self._log("Creating essential directories...")
            for d in ['proc','sys','dev','run','tmp']:
                run(f"mkdir -p {target}/{d}")

            # fstab
            self._log("Writing fstab...")
            root_uuid, _ = run(f"blkid -s UUID -o value {root}")
            efi_uuid,  _ = run(f"blkid -s UUID -o value {efi}")
            swap_uuid, _ = run(f"blkid -s UUID -o value {swap}")
            root_uuid = root_uuid.strip()
            efi_uuid  = efi_uuid.strip()
            swap_uuid = swap_uuid.strip()

            with open(f"{target}/etc/fstab", 'w') as f:
                f.write(f"# RIDOS OS fstab\n")
                f.write(f"UUID={root_uuid}  /          ext4  defaults,noatime  0  1\n")
                f.write(f"UUID={efi_uuid}   /boot/efi  vfat  umask=0077        0  2\n")
                f.write(f"UUID={swap_uuid}  none       swap  sw                0  0\n")

            # hostname
            with open(f"{target}/etc/hostname", 'w') as f:
                f.write(hostname + "\n")

            # timezone
            run(f"chroot {target} ln -sf /usr/share/zoneinfo/{timezone} /etc/localtime")

            # Create user
            self._log(f"Creating user '{username}'...")
            run(f"chroot {target} userdel -r {username} 2>/dev/null || true")
            run(f"chroot {target} useradd -m -s /bin/bash "
                f"-G sudo,audio,video,netdev,plugdev,bluetooth {username}")
            run(f"echo '{username}:{password}' | chroot {target} chpasswd")
            run(f"echo 'root:{password}' | chroot {target} chpasswd")

            # Remove live-boot
            self._log("Removing live-boot...")
            run(f"chroot {target} apt-get remove -y "
                f"live-boot live-boot-initramfs-tools calamares 2>/dev/null || true")

            # Update initramfs
            self._log("Updating initramfs...")
            run(f"mount --bind /dev     {target}/dev")
            run(f"mount --bind /dev/pts {target}/dev/pts")
            run(f"mount --bind /proc    {target}/proc")
            run(f"mount --bind /sys     {target}/sys")
            run(f"chroot {target} update-initramfs -u -k all 2>/dev/null || true", timeout=120)

            # ── Step 7: Install GRUB ──────────────────────────
            self._set_status("Installing bootloader...", 0.85)
            self._log(f"Installing GRUB on {disk}...")
            out, code = run(
                f"chroot {target} grub-install "
                f"--target=i386-pc --recheck --force --no-floppy {disk}")
            self._log(f"grub-install: {'OK' if code==0 else out[-200:]}")

            self._log("Running update-grub...")
            out, code = run(f"chroot {target} update-grub")
            self._log(f"update-grub: {'OK' if code==0 else out[-200:]}")

            # Unmount
            self._log("Unmounting...")
            for d in ['sys','proc','dev/pts','dev']:
                run(f"umount {target}/{d} 2>/dev/null || true")
            run(f"umount {target}/boot/efi 2>/dev/null || true")
            run(f"umount {target} 2>/dev/null || true")
            run(f"swapoff {swap} 2>/dev/null || true")

            self._set_status("Installation complete!", 1.0)
            self._log("\n=== RIDOS OS installed successfully! ===")
            GLib.idle_add(self._show_step, 6)

        except Exception as e:
            self._log(f"\nFATAL ERROR: {e}")
            self._set_status(f"Installation failed: {e}", None)
            GLib.idle_add(self._show_error, str(e))

    def _show_error(self, msg):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Installation Failed"
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()

    # ── Step 6: Complete ──────────────────────────────────────
    def _step_complete(self):
        self.title_label.set_text("Installation Complete!")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content.pack_start(box, True, True, 0)

        lbl = Gtk.Label()
        lbl.set_markup(
            '<span foreground="#10B981" size="xx-large"><b>RIDOS OS installed successfully!</b></span>')
        lbl.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl, False, False, 20)

        info = Gtk.Label()
        info.set_markup(
            f'<span foreground="#E9D5FF">'
            f'Username: <b>{self.data["username"]}</b>\n'
            f'Password: <b>{self.data["password"]}</b>\n\n'
            f'Remove the USB drive and reboot.\n'
            f'After boot, set your API key:\n'
            f'<tt>mkdir -p ~/.ridos\n'
            f'echo "YOUR_KEY" > ~/.ridos/api_key</tt>'
            f'</span>')
        info.set_justify(Gtk.Justification.CENTER)
        box.pack_start(info, False, False, 0)

        reboot_btn = Gtk.Button(label="Reboot Now")
        reboot_btn.get_style_context().add_class('btn-primary')
        reboot_btn.connect('clicked', lambda w: run("reboot"))
        reboot_btn.set_halign(Gtk.Align.CENTER)
        box.pack_start(reboot_btn, False, False, 20)

        close_btn = Gtk.Button(label="Close")
        close_btn.get_style_context().add_class('btn-secondary')
        close_btn.connect('clicked', lambda w: Gtk.main_quit())
        close_btn.set_halign(Gtk.Align.CENTER)
        box.pack_start(close_btn, False, False, 0)


def main():
    if os.geteuid() != 0:
        dialog = Gtk.MessageDialog(
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Root required"
        )
        dialog.format_secondary_text(
            "Please run as root:\nsudo python3 /opt/ridos/bin/ridos-installer.py")
        dialog.run()
        return

    app = RIDOSInstaller()
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
