#!/usr/bin/env python3
"""Configure RIDOS OS system settings"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    return subprocess.run(cmd, shell=True)

write('chroot/etc/hostname', 'ridos-os\n')
write('chroot/etc/hosts',
    '127.0.0.1 localhost\n127.0.1.1 ridos-os\n::1 localhost\n')
write('chroot/etc/locale.gen', 'en_US.UTF-8 UTF-8\nar_IQ.UTF-8 UTF-8\n')
write('chroot/etc/default/locale', 'LANG=en_US.UTF-8\n')
run('chroot chroot locale-gen')
run('chroot chroot ln -sf /usr/share/zoneinfo/Asia/Baghdad /etc/localtime')

run('chroot chroot useradd -m -s /bin/bash -G sudo,audio,video,netdev,plugdev,bluetooth ridos 2>/dev/null || true')
run('echo "ridos:ridos" | chroot chroot chpasswd')
run('echo "root:ridos"  | chroot chroot chpasswd')

os.makedirs('chroot/etc/lightdm/lightdm.conf.d', exist_ok=True)
write('chroot/etc/lightdm/lightdm.conf.d/50-ridos.conf',
    '[Seat:*]\nuser-session=xfce\ngreeter-session=lightdm-gtk-greeter\n')
write('chroot/etc/lightdm/lightdm-gtk-greeter.conf',
    '[greeter]\nbackground=#6B21A8\ntheme-name=Adwaita-dark\n'
    'icon-theme-name=Papirus-Dark\nfont-name=Noto Sans 11\n')
write('chroot/etc/os-release',
    'PRETTY_NAME="RIDOS OS v1.0 Baghdad"\nNAME="RIDOS OS"\n'
    'VERSION_ID="1.0"\nVERSION="1.0 (Baghdad)"\nID=ridos\nID_LIKE=debian\n'
    'HOME_URL="https://github.com/alkinanireyad/RIDOS-OS"\n')
write('chroot/etc/issue',
    'RIDOS OS v1.0 Baghdad - AI-Powered Linux\nLogin: ridos / ridos\n')

os.makedirs('chroot/etc/systemd/system.conf.d', exist_ok=True)
write('chroot/etc/systemd/system.conf.d/timeout.conf',
    '[Manager]\nDefaultTimeoutStopSec=5s\nDefaultTimeoutStartSec=10s\n')

os.makedirs('chroot/home/ridos/.config/autostart', exist_ok=True)
write('chroot/home/ridos/.config/autostart/vboxclient.desktop',
    '[Desktop Entry]\nType=Application\nName=VirtualBox Guest\n'
    'Exec=VBoxClient-all\nHidden=false\nNoDisplay=false\n'
    'X-GNOME-Autostart-enabled=true\n')

for svc in ['lightdm','NetworkManager','bluetooth','ssh',
            'spice-vdagentd','virtualbox-guest-utils']:
    run(f'chroot chroot systemctl enable {svc} 2>/dev/null || true')

run('chroot chroot chown -R ridos:ridos /home/ridos 2>/dev/null || true')
print("System configured")
