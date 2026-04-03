#!/bin/bash
# RIDOS GRUB Installer - fixes Calamares grub-install error
LOG="/tmp/ridos-grub.log"
exec > "$LOG" 2>&1
set -x
echo "=== RIDOS GRUB Install $(date) ==="

# Find Calamares mount point /tmp/calamares-root-XXXXXXXX
T=""
for d in /tmp/calamares-root-*; do
    [ -d "$d/boot" ] && [ -d "$d/etc" ] && T="$d" && break
done

if [ -z "$T" ]; then
    while read -r dev mnt fs rest; do
        if [ "$mnt" != "/" ] && [ "$mnt" != "none" ] && \
           [ -d "$mnt/boot" ] && [ -d "$mnt/etc" ] && [ -d "$mnt/bin" ]; then
            T="$mnt" && break
        fi
    done < /proc/mounts
fi

[ -z "$T" ] && echo "FATAL: No target" && exit 1
echo "Target: $T"

DEV=$(awk -v t="$T" '$2==t {print $1}' /proc/mounts | head -1)
echo "Device: $DEV"

if echo "$DEV" | grep -q "nvme"; then
    DISK=$(echo "$DEV" | sed 's/p[0-9]*$//')
else
    DISK=$(echo "$DEV" | sed 's/[0-9]*$//')
fi
[ ! -b "$DISK" ] && DISK="/dev/sda"
echo "Disk: $DISK"

mount --bind /dev     "$T/dev"
mount --bind /dev/pts "$T/dev/pts"
mount --bind /proc    "$T/proc"
mount --bind /sys     "$T/sys"

# Install grub-pc on target system first
chroot "$T" apt-get install -y grub-pc grub-pc-bin \
    --no-install-recommends 2>/dev/null || true

chroot "$T" grub-install \
    --target=i386-pc \
    --recheck \
    --force \
    --no-floppy \
    "$DISK"
R=$?
echo "grub-install: $R"

chroot "$T" update-grub
echo "update-grub done"

umount "$T/sys"     2>/dev/null || true
umount "$T/proc"    2>/dev/null || true
umount "$T/dev/pts" 2>/dev/null || true
umount "$T/dev"     2>/dev/null || true

echo "=== Done: $R ==="
exit $R
