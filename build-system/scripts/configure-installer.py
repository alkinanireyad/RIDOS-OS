#!/usr/bin/env python3
"""Configure RIDOS OS installer - NO Calamares"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    return subprocess.run(cmd, shell=True)

# Sudoers - allow ridos to run installer without password prompt
write('chroot/etc/sudoers.d/ridos-installer',
    'ridos ALL=(ALL) NOPASSWD: /usr/bin/python3 /opt/ridos/bin/ridos-installer.py\n'
    'ridos ALL=(ALL) NOPASSWD: /usr/local/bin/ridos-installer\n'
    'ridos ALL=(ALL) NOPASSWD: /usr/local/bin/ridos-install\n')
run('chmod 440 chroot/etc/sudoers.d/ridos-installer')

# Ensure GTK3 python bindings are available
run('chroot chroot apt-get install -y python3-gi python3-gi-cairo '
    'gir1.2-gtk-3.0 gir1.2-glib-2.0 parted rsync 2>/dev/null || true')

print("Installer configured")
print("No Calamares - using ridos-installer.py (GTK3 Python)")
