#!/usr/bin/env python3
import os
os.makedirs('iso/boot/grub', exist_ok=True)
with open('iso/boot/grub/grub.cfg', 'w') as f:
    f.write('''set default=0
set timeout=8

menuentry "RIDOS OS v1.0 Baghdad" {
  search --no-floppy --file --set=root /live/filesystem.squashfs
  linux /live/vmlinuz boot=live components quiet splash
  initrd /live/initrd
}
menuentry "RIDOS OS (safe mode)" {
  search --no-floppy --file --set=root /live/filesystem.squashfs
  linux /live/vmlinuz boot=live components nomodeset
  initrd /live/initrd
}
menuentry "RIDOS OS (RAM mode - needs 4GB RAM)" {
  search --no-floppy --file --set=root /live/filesystem.squashfs
  linux /live/vmlinuz boot=live components toram quiet splash
  initrd /live/initrd
}
''')
print("GRUB config written")
