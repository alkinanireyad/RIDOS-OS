#!/usr/bin/env python3
"""Write GRUB boot menu for RIDOS OS"""
import os

os.makedirs('iso/boot/grub', exist_ok=True)

# IMPORTANT: boot=live tells live-boot where to find filesystem.squashfs
# live-boot looks for /live/filesystem.squashfs on the boot medium
with open('iso/boot/grub/grub.cfg', 'w') as f:
    f.write('''set default=0
set timeout=8

insmod all_video
insmod gfxterm

menuentry "RIDOS OS v1.0 Baghdad" {
  search --no-floppy --file --set=root /live/filesystem.squashfs
  linux /live/vmlinuz boot=live live-media-path=/live components quiet splash
  initrd /live/initrd
}
menuentry "RIDOS OS (safe mode)" {
  search --no-floppy --file --set=root /live/filesystem.squashfs
  linux /live/vmlinuz boot=live live-media-path=/live components nomodeset
  initrd /live/initrd
}
menuentry "RIDOS OS (RAM mode)" {
  search --no-floppy --file --set=root /live/filesystem.squashfs
  linux /live/vmlinuz boot=live live-media-path=/live components toram quiet splash
  initrd /live/initrd
}
''')

print("GRUB config written with live-media-path=/live")
