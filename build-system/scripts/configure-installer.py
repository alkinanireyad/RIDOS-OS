#!/usr/bin/env python3
"""Configure RIDOS OS custom installer"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    return subprocess.run(cmd, shell=True)

# Desktop shortcut for installer
os.makedirs('chroot/home/ridos/Desktop', exist_ok=True)

write('chroot/home/ridos/Desktop/install-ridos.desktop',
    '[Desktop Entry]\n'
    'Version=1.0\n'
    'Type=Application\n'
    'Name=Install RIDOS OS\n'
    'Comment=Install RIDOS OS to hard disk\n'
    'Exec=bash -c "pkexec python3 /opt/ridos/bin/ridos-installer.py"\n'
    'Icon=drive-harddisk\n'
    'Terminal=false\n'
    'Categories=System;\n')

run('chmod +x chroot/home/ridos/Desktop/install-ridos.desktop')

# Polkit rule for installer
os.makedirs('chroot/usr/share/polkit-1/actions', exist_ok=True)
write('chroot/usr/share/polkit-1/actions/org.ridos.installer.policy',
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD polkit Policy Configuration 1.0//EN"\n'
    '  "http://www.freedesktop.org/software/polkit/policyconfig-1.dtd">\n'
    '<policyconfig>\n'
    '  <action id="org.ridos.installer">\n'
    '    <description>Run RIDOS Installer</description>\n'
    '    <message>Authentication required to install RIDOS OS</message>\n'
    '    <defaults>\n'
    '      <allow_active>yes</allow_active>\n'
    '    </defaults>\n'
    '  </action>\n'
    '</policyconfig>\n')

# Sudoers for installer
write('chroot/etc/sudoers.d/ridos-installer',
    'ridos ALL=(ALL) NOPASSWD: /usr/bin/python3 /opt/ridos/bin/ridos-installer.py\n'
    'ridos ALL=(ALL) NOPASSWD: /usr/local/bin/ridos-installer\n')
run('chmod 440 chroot/etc/sudoers.d/ridos-installer')

print("Installer configured - no Calamares needed!")
