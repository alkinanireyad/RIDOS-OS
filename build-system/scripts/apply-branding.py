#!/usr/bin/env python3
"""Apply RIDOS OS branding"""
import os, subprocess, glob, shutil

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    return subprocess.run(cmd, shell=True)

os.makedirs('chroot/home/ridos/.config/xfce4/xfconf/xfce-perchannel-xml', exist_ok=True)
os.makedirs('chroot/home/ridos/Desktop', exist_ok=True)
os.makedirs('chroot/usr/share/ridos', exist_ok=True)

write('chroot/home/ridos/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml', '''<?xml version="1.0" encoding="UTF-8"?>
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

# Wallpaper - all monitor names covered
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
    </property>
  </property>
</channel>
''')

# Clean desktop
for f in glob.glob('chroot/home/ridos/Desktop/*.desktop'):
    os.remove(f)

# Desktop icons
icons = [
    ('01-control-center.desktop', 'RIDOS Control Center',
     'xfce4-terminal -e "python3 /opt/ridos/bin/control_center.py"',
     'utilities-system-monitor'),
    ('02-ai-terminal.desktop', 'AI Terminal',
     'xfce4-terminal -e "python3 /opt/ridos/bin/ai_features.py"',
     'utilities-terminal'),
    ('03-ai-shell.desktop', 'RIDOS AI Shell',
     'xfce4-terminal -e "python3 /opt/ridos/bin/ridos_shell.py"',
     'utilities-terminal'),
    ('04-firefox.desktop', 'Firefox',
     'firefox-esr %u', 'firefox-esr'),
    ('05-brave.desktop', 'Brave Browser',
     'brave-browser %u', 'brave-browser'),
    ('06-files.desktop', 'File Manager',
     'thunar', 'system-file-manager'),
    ('07-install-ridos.desktop', 'Install RIDOS OS',
     'pkexec /usr/bin/calamares',
     'drive-harddisk'),
]

for fname, name, exec_cmd, icon in icons:
    write(f'chroot/home/ridos/Desktop/{fname}',
        f'[Desktop Entry]\nVersion=1.0\nType=Application\n'
        f'Name={name}\nExec={exec_cmd}\nIcon={icon}\n'
        f'Terminal=false\nCategories=System;\n')
    os.chmod(f'chroot/home/ridos/Desktop/{fname}', 0o755)

run('chroot chroot chown -R ridos:ridos /home/ridos 2>/dev/null || true')
print("Branding applied - 7 desktop icons")
