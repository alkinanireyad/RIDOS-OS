#!/usr/bin/env python3
"""Apply RIDOS OS branding - desktop shortcuts, wallpaper, theme"""
import os, subprocess, glob

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    return subprocess.run(cmd, shell=True)

# ── Directories ───────────────────────────────────────────────
for d in [
    'chroot/home/ridos/.config/xfce4/xfconf/xfce-perchannel-xml',
    'chroot/home/ridos/.config/xfce4/terminal',
    'chroot/home/ridos/Desktop',
    'chroot/home/ridos/.config/autostart',
    'chroot/usr/share/ridos',
    'chroot/opt/ridos/bin',
]:
    os.makedirs(d, exist_ok=True)

# ── XFCE dark theme ───────────────────────────────────────────
write('chroot/home/ridos/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml',
'''<?xml version="1.0" encoding="UTF-8"?>
<channel name="xsettings" version="1.0">
  <property name="Net" type="empty">
    <property name="ThemeName" type="string" value="Adwaita-dark"/>
    <property name="IconThemeName" type="string" value="Papirus-Dark"/>
  </property>
  <property name="Gtk" type="empty">
    <property name="FontName" type="string" value="Noto Sans 10"/>
  </property>
</channel>
''')

# ── Wallpaper ─────────────────────────────────────────────────
wp = '/usr/share/ridos/ridos-wallpaper.png'
write('chroot/home/ridos/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml',
f'''<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="backdrop" type="empty">
    <property name="screen0" type="empty">
      <property name="monitorVirtual1" type="empty">
        <property name="workspace0" type="empty">
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="{wp}"/>
        </property>
      </property>
      <property name="monitor0" type="empty">
        <property name="workspace0" type="empty">
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="{wp}"/>
        </property>
      </property>
      <property name="monitorHDMI-1" type="empty">
        <property name="workspace0" type="empty">
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="{wp}"/>
        </property>
      </property>
      <property name="monitorVGA-1" type="empty">
        <property name="workspace0" type="empty">
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="{wp}"/>
        </property>
      </property>
      <property name="monitorScreen0" type="empty">
        <property name="workspace0" type="empty">
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="{wp}"/>
        </property>
      </property>
    </property>
  </property>
</channel>
''')

# ── Terminal colors ───────────────────────────────────────────
write('chroot/home/ridos/.config/xfce4/terminal/terminalrc',
'[Configuration]\n'
'ColorForeground=#E9D5FF\n'
'ColorBackground=#0F0A1E\n'
'ColorCursor=#7C3AED\n'
'FontName=Noto Mono 11\n')

# ── Sudoers - THE KEY FIX ─────────────────────────────────────
# No password for RIDOS scripts + preserve DISPLAY env var
os.makedirs('chroot/etc/sudoers.d', exist_ok=True)
write('chroot/etc/sudoers.d/ridos-tools',
'# RIDOS OS sudoers - no password for RIDOS launcher scripts\n'
'Defaults env_keep += "DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS"\n'
'ridos ALL=(ALL) NOPASSWD: /opt/ridos/bin/launch-control-center.sh\n'
'ridos ALL=(ALL) NOPASSWD: /opt/ridos/bin/launch-installer.sh\n'
'ridos ALL=(ALL) NOPASSWD: /usr/bin/python3\n'
'ridos ALL=(ALL) NOPASSWD: /usr/local/bin/ridos-installer\n'
'ridos ALL=(ALL) NOPASSWD: /usr/local/bin/debian-flex\n')
run('chmod 440 chroot/etc/sudoers.d/ridos-tools')
print("Sudoers: OK")

# ── Wrapper scripts - PROVEN RELIABLE METHOD ─────────────────
# Use wrapper scripts instead of complex Exec lines
# This is how Ubuntu/Mint handle privileged GUI apps

write('chroot/opt/ridos/bin/launch-control-center.sh',
'#!/bin/bash\n'
'# RIDOS Control Center launcher\n'
'export DISPLAY=${DISPLAY:-:0}\n'
'# Find XAUTHORITY\n'
'for u in $SUDO_USER ridos; do\n'
'  if [ -f "/home/$u/.Xauthority" ]; then\n'
'    export XAUTHORITY="/home/$u/.Xauthority"\n'
'    break\n'
'  fi\n'
'done\n'
'exec python3 /opt/ridos/bin/control_center.py\n')
run('chmod +x chroot/opt/ridos/bin/launch-control-center.sh')

write('chroot/opt/ridos/bin/launch-installer.sh',
'#!/bin/bash\n'
'# RIDOS Installer launcher\n'
'# Set DISPLAY unconditionally\n'
'export DISPLAY=:0\n'
'# Find XAUTHORITY\n'
'for u in ridos $SUDO_USER $(logname 2>/dev/null); do\n'
'  if [ -f "/home/$u/.Xauthority" ]; then\n'
'    export XAUTHORITY="/home/$u/.Xauthority"\n'
'    break\n'
'  fi\n'
'done\n'
'# Allow root on display\n'
'xhost +SI:localuser:root 2>/dev/null || true\n'
'exec python3 /opt/ridos/bin/ridos-installer.py\n')
run('chmod +x chroot/opt/ridos/bin/launch-installer.sh')
print("Launcher scripts: OK")

# ── Clean old desktop files ───────────────────────────────────
for f in glob.glob('chroot/home/ridos/Desktop/*.desktop'):
    os.remove(f)

# ── Desktop shortcuts - CLEAN SIMPLE FORMAT ──────────────────
# Rules:
# 1. No quotes in --title (breaks arg parsing)
# 2. Use wrapper scripts for root tools
# 3. xfce4-terminal -e "script" format is reliable
# 4. Terminal=false always (we control terminal ourselves)

# 01 - RIDOS Control Center
write('chroot/home/ridos/Desktop/01-control-center.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=RIDOS Control Center\n'
'Comment=AI System Management Dashboard\n'
'Exec=xfce4-terminal -e "sudo /opt/ridos/bin/launch-control-center.sh"\n'
'Icon=utilities-system-monitor\n'
'Terminal=false\n'
'Categories=System;\n')
os.chmod('chroot/home/ridos/Desktop/01-control-center.desktop', 0o755)
print("Created: RIDOS Control Center")

# 02 - AI Terminal
write('chroot/home/ridos/Desktop/02-ai-terminal.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=AI Terminal\n'
'Comment=Intelligent Command Assistant\n'
'Exec=xfce4-terminal -e "python3 /opt/ridos/bin/ai_features.py"\n'
'Icon=utilities-terminal\n'
'Terminal=false\n'
'Categories=System;\n')
os.chmod('chroot/home/ridos/Desktop/02-ai-terminal.desktop', 0o755)
print("Created: AI Terminal")

# 03 - RIDOS AI Shell
write('chroot/home/ridos/Desktop/03-ai-shell.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=RIDOS AI Shell\n'
'Comment=AI Assistant Interactive Shell\n'
'Exec=xfce4-terminal -e "python3 /opt/ridos/bin/ridos_shell.py"\n'
'Icon=utilities-terminal\n'
'Terminal=false\n'
'Categories=System;\n')
os.chmod('chroot/home/ridos/Desktop/03-ai-shell.desktop', 0o755)
print("Created: RIDOS AI Shell")

# 04 - Firefox
write('chroot/home/ridos/Desktop/04-firefox.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=Firefox\n'
'Comment=Web Browser\n'
'Exec=firefox-esr %u\n'
'Icon=firefox-esr\n'
'Terminal=false\n'
'Categories=Network;WebBrowser;\n')
os.chmod('chroot/home/ridos/Desktop/04-firefox.desktop', 0o755)
print("Created: Firefox")

# 05 - Brave
write('chroot/home/ridos/Desktop/05-brave.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=Brave Browser\n'
'Comment=Secure Web Browser\n'
'Exec=brave-browser %u\n'
'Icon=brave-browser\n'
'Terminal=false\n'
'Categories=Network;WebBrowser;\n')
os.chmod('chroot/home/ridos/Desktop/05-brave.desktop', 0o755)
print("Created: Brave Browser")

# 06 - File Manager
write('chroot/home/ridos/Desktop/06-files.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=File Manager\n'
'Comment=Browse Files\n'
'Exec=thunar\n'
'Icon=system-file-manager\n'
'Terminal=false\n'
'Categories=System;FileManager;\n')
os.chmod('chroot/home/ridos/Desktop/06-files.desktop', 0o755)
print("Created: File Manager")

# 07 - Install RIDOS OS
write('chroot/home/ridos/Desktop/07-install-ridos.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=Install RIDOS OS\n'
'Comment=Install RIDOS OS to hard disk\n'
'Exec=xfce4-terminal -e "sudo /opt/ridos/bin/launch-installer.sh"\n'
'Icon=drive-harddisk\n'
'Terminal=false\n'
'Categories=System;\n')
os.chmod('chroot/home/ridos/Desktop/07-install-ridos.desktop', 0o755)
print("Created: Install RIDOS OS")

# 08 - debian-flex
write('chroot/home/ridos/Desktop/08-debian-flex.desktop',
'[Desktop Entry]\n'
'Version=1.0\n'
'Type=Application\n'
'Name=debian-flex\n'
'Comment=System Management CLI Tool\n'
'Exec=xfce4-terminal -e "debian-flex --help"\n'
'Icon=utilities-terminal\n'
'Terminal=false\n'
'Categories=System;\n')
os.chmod('chroot/home/ridos/Desktop/08-debian-flex.desktop', 0o755)
print("Created: debian-flex")

# ── VBoxClient autostart ──────────────────────────────────────
write('chroot/home/ridos/.config/autostart/vboxclient.desktop',
'[Desktop Entry]\n'
'Type=Application\n'
'Name=VirtualBox Guest\n'
'Exec=VBoxClient-all\n'
'Hidden=false\n'
'NoDisplay=false\n'
'X-GNOME-Autostart-enabled=true\n')

# ── Fix ownership ─────────────────────────────────────────────
run('chroot chroot chown -R ridos:ridos /home/ridos 2>/dev/null || true')

print("\nBranding complete - 8 desktop shortcuts")
print("Launcher scripts: /opt/ridos/bin/launch-*.sh")
print("Sudoers: NOPASSWD for launcher scripts")
