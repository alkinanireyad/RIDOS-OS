#!/usr/bin/env python3
"""Configure Calamares installer for RIDOS OS"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    return subprocess.run(cmd, shell=True)

os.makedirs('chroot/etc/calamares/branding/ridos', exist_ok=True)
os.makedirs('chroot/etc/calamares/modules', exist_ok=True)

write('chroot/etc/calamares/settings.conf', '''---
modules-search: [ local, /usr/lib/calamares/modules ]

sequence:
  - show:
      - welcome
      - locale
      - keyboard
      - partition
      - users
      - summary
  - exec:
      - partition
      - mount
      - unpackfs
      - machineid
      - fstab
      - locale
      - keyboard
      - users
      - displaymanager
      - packages
      - grubcfg
      - shellprocess
      - finished

branding: ridos
prompt-install: false
dont-chroot: false
''')

write('chroot/etc/calamares/branding/ridos/branding.desc', '''---
componentName: ridos
welcomeStyleCalamares: true
strings:
  productName: RIDOS OS
  shortProductName: RIDOS
  version: "1.0"
  shortVersion: "1.0"
  versionedName: "RIDOS OS 1.0 Baghdad"
  shortVersionedName: "RIDOS 1.0"
  bootloaderEntryName: RIDOS
  productUrl: "https://github.com/alkinanireyad/RIDOS-OS"
  supportUrl: "https://github.com/alkinanireyad/RIDOS-OS/issues"
  releaseNotesUrl: "https://github.com/alkinanireyad/RIDOS-OS"
images:
  productLogo: "logo.png"
  productIcon: "logo.png"
  productWelcome: "languages.png"
slideshow: "show.qml"
style:
  sidebarBackground: "#1E1B4B"
  sidebarText: "#FFFFFF"
  sidebarTextSelect: "#6B21A8"
''')

write('chroot/etc/calamares/branding/ridos/show.qml', '''import QtQuick 2.0
Rectangle {
    color: "#1E1B4B"
    width: 800; height: 500
    Column {
        anchors.centerIn: parent
        spacing: 20
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "RIDOS OS"
            color: "#C4B5FD"
            font.pointSize: 36
            font.bold: true
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "v1.0 Baghdad - AI-Powered Linux"
            color: "#E9D5FF"
            font.pointSize: 14
        }
    }
}
''')

write('chroot/etc/calamares/modules/partition.conf', '''---
efiSystemPartition: "/boot/efi"
defaultPartitionTableType: gpt
availableFileSystemTypes: [ ext4, btrfs, xfs ]
initialPartitioningChoice: erase
initialSwapChoice: small
''')

write('chroot/etc/calamares/modules/users.conf', '''---
defaultGroups:
  - sudo
  - audio
  - video
  - netdev
  - plugdev
  - bluetooth
  - storage
autologinGroup: autologin
doAutologin: false
sudoersGroup: sudo
setRootPassword: false
passwordRequirements:
  minLength: 3
  maxLength: 255
''')

# CRITICAL: find squashfs at runtime
write('chroot/etc/calamares/modules/unpackfs.conf', '''---
unpack:
  - source: "/run/live/medium/live/filesystem.squashfs"
    sourcefs: "squashfs"
    destination: ""
''')

write('chroot/etc/calamares/modules/displaymanager.conf', '''---
displaymanagers:
  - lightdm
defaultDesktopEnvironment:
  executable: "startxfce4"
  desktopFile: "xfce.desktop"
basicSetup: false
''')

# CRITICAL: fstab fix
write('chroot/etc/calamares/modules/fstab.conf', '''---
mountOptions:
  default: defaults
  btrfs: defaults,noatime,autodefrag
  ext4: defaults,noatime
  fat32: defaults,umask=0077
  vfat: defaults,umask=0077
ssdExtraMountOptions:
  ext4: discard
  btrfs: discard,ssd
efiMountOptions: umask=0077
ensureSuspendToDisk: true
neverCheckSuspendToDisk: false
''')

write('chroot/etc/calamares/modules/locale.conf', '''---
region: "Asia"
zone: "Baghdad"
useSystemTimezone: false
''')

write('chroot/etc/calamares/modules/keyboard.conf', '''---
writeEtcDefaultKeyboard: true
''')

write('chroot/etc/calamares/modules/networkcfg.conf', '''---
explicitNMconfig: true
''')

# CRITICAL: only remove packages - no install (no internet during install)
write('chroot/etc/calamares/modules/packages.conf', '''---
backend: apt
update_db: false
operations:
  - remove:
      - live-boot
      - live-boot-initramfs-tools
      - calamares
      - calamares-settings-debian
''')

write('chroot/etc/calamares/modules/grubcfg.conf', '''---
overwrite: true
noProxy: false
''')

# CRITICAL: shellprocess handles GRUB installation
write('chroot/etc/calamares/modules/shellprocess.conf', '''---
dontChroot: true
timeout: 300
verbose: true

script:
  - command: "bash /usr/local/bin/ridos-fix-squashfs"
    timeout: 30
  - command: "bash /usr/local/bin/ridos-grub-install"
    timeout: 300
''')

write('chroot/etc/default/grub',
    'GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\n'
    'GRUB_DISTRIBUTOR="RIDOS OS"\n'
    'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n'
    'GRUB_CMDLINE_LINUX=""\n')

# Fix squashfs path finder script
write('chroot/usr/local/bin/ridos-fix-squashfs', '''#!/bin/bash
CONF="/etc/calamares/modules/unpackfs.conf"
for path in \
    "/run/live/medium/live/filesystem.squashfs" \
    "/lib/live/mount/medium/live/filesystem.squashfs" \
    "/run/initramfs/live/filesystem.squashfs" \
    "/cdrom/live/filesystem.squashfs"; do
    if [ -f "$path" ]; then
        echo "Found squashfs: $path"
        printf "---\\nunpack:\\n  - source: \\"%s\\"\\n    sourcefs: squashfs\\n    destination: \\"\\"\\n" "$path" > "$CONF"
        echo "Fixed unpackfs.conf"
        exit 0
    fi
done
echo "squashfs not found - using default path"
''')

run('chmod +x chroot/usr/local/bin/ridos-fix-squashfs')

run('convert -size 200x200 gradient:"#6B21A8-#1E1B4B" '
    '-font DejaVu-Sans-Bold -pointsize 32 '
    '-fill white -gravity center -annotate 0 "RIDOS" '
    'chroot/etc/calamares/branding/ridos/logo.png 2>/dev/null || true')
run('cp chroot/etc/calamares/branding/ridos/logo.png '
    'chroot/etc/calamares/branding/ridos/languages.png 2>/dev/null || true')
run('chroot chroot apt-get remove -y calamares-settings-debian 2>/dev/null || true')

print("Calamares configured")
