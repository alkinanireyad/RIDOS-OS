#!/bin/bash
# RIDOS OS Simple Installer - Alternative to Calamares
# Works by directly copying the live system to HDD

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

clear
echo -e "${PURPLE}"
echo "╔══════════════════════════════════════════╗"
echo "║     RIDOS OS Installer v1.0              ║"
echo "║     Baghdad Edition                      ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Must run as root
if [ "$(id -u)" != "0" ]; then
    echo -e "${RED}Please run as root: sudo bash /usr/local/bin/ridos-install${NC}"
    exit 1
fi

# Show available disks
echo -e "${YELLOW}Available disks:${NC}"
lsblk -d -o NAME,SIZE,MODEL | grep -v "loop\|sr"
echo ""

# Ask for target disk
echo -e "${YELLOW}WARNING: All data on the selected disk will be ERASED!${NC}"
echo -e "Enter target disk (example: sda, sdb, nvme0n1): "
read -r DISK
DISK="/dev/$DISK"

# Validate disk
if [ ! -b "$DISK" ]; then
    echo -e "${RED}Error: $DISK is not a valid disk!${NC}"
    exit 1
fi

# Confirm
echo -e "${RED}WARNING: This will ERASE ALL DATA on $DISK${NC}"
echo -e "Type 'YES' to continue: "
read -r CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo -e "${GREEN}Starting RIDOS OS installation...${NC}"
echo ""

# Step 1: Partition the disk
echo -e "${BLUE}[1/7] Partitioning disk...${NC}"
parted -s "$DISK" mklabel gpt
parted -s "$DISK" mkpart primary fat32 1MiB 512MiB
parted -s "$DISK" set 1 esp on
parted -s "$DISK" mkpart primary linux-swap 512MiB 4608MiB
parted -s "$DISK" mkpart primary ext4 4608MiB 100%

# Get partition names
if echo "$DISK" | grep -q "nvme"; then
    EFI="${DISK}p1"
    SWAP="${DISK}p2"
    ROOT="${DISK}p3"
else
    EFI="${DISK}1"
    SWAP="${DISK}2"
    ROOT="${DISK}3"
fi

sleep 2
echo -e "${GREEN}Partitions: EFI=$EFI SWAP=$SWAP ROOT=$ROOT${NC}"

# Step 2: Format partitions
echo -e "${BLUE}[2/7] Formatting partitions...${NC}"
mkfs.fat -F32 "$EFI"
mkswap "$SWAP"
mkfs.ext4 -F "$ROOT"

# Step 3: Mount target
echo -e "${BLUE}[3/7] Mounting target...${NC}"
mkdir -p /mnt/ridos-target
mount "$ROOT" /mnt/ridos-target
mkdir -p /mnt/ridos-target/boot/efi
mount "$EFI" /mnt/ridos-target/boot/efi
swapon "$SWAP"

# Step 4: Copy system from squashfs
echo -e "${BLUE}[4/7] Copying RIDOS OS to disk (this takes 10-20 minutes)...${NC}"

# Find squashfs
SQUASHFS=""
for path in \
    "/run/live/medium/live/filesystem.squashfs" \
    "/lib/live/mount/medium/live/filesystem.squashfs" \
    "/cdrom/live/filesystem.squashfs"; do
    if [ -f "$path" ]; then
        SQUASHFS="$path"
        break
    fi
done

if [ -z "$SQUASHFS" ]; then
    SQUASHFS=$(find /run /lib/live /cdrom /media -name "filesystem.squashfs" 2>/dev/null | head -1)
fi

if [ -z "$SQUASHFS" ]; then
    echo -e "${RED}Error: Cannot find filesystem.squashfs!${NC}"
    exit 1
fi

echo "Using: $SQUASHFS"

# Mount squashfs and copy
mkdir -p /mnt/squashfs-src
mount -t squashfs -o loop "$SQUASHFS" /mnt/squashfs-src

echo "Copying files..."
rsync -aAX --progress \
    --exclude=/proc \
    --exclude=/sys \
    --exclude=/dev \
    --exclude=/run \
    --exclude=/tmp \
    /mnt/squashfs-src/ /mnt/ridos-target/

umount /mnt/squashfs-src
rmdir /mnt/squashfs-src

# Step 5: Fix system files
echo -e "${BLUE}[5/7] Configuring installed system...${NC}"

# Create essential dirs
mkdir -p /mnt/ridos-target/{proc,sys,dev,run,tmp}

# Fix fstab
ROOT_UUID=$(blkid -s UUID -o value "$ROOT")
EFI_UUID=$(blkid -s UUID -o value "$EFI")
SWAP_UUID=$(blkid -s UUID -o value "$SWAP")

cat > /mnt/ridos-target/etc/fstab << FSTABEOF
# RIDOS OS fstab
UUID=$ROOT_UUID  /          ext4  defaults,noatime  0  1
UUID=$EFI_UUID   /boot/efi  vfat  umask=0077        0  2
UUID=$SWAP_UUID  none       swap  sw                0  0
FSTABEOF

# Remove live-boot
rm -f /mnt/ridos-target/etc/live/boot.conf 2>/dev/null || true

# Step 6: Install GRUB
echo -e "${BLUE}[6/7] Installing bootloader...${NC}"

mount --bind /dev     /mnt/ridos-target/dev
mount --bind /dev/pts /mnt/ridos-target/dev/pts
mount --bind /proc    /mnt/ridos-target/proc
mount --bind /sys     /mnt/ridos-target/sys

# Install GRUB for BIOS
chroot /mnt/ridos-target grub-install \
    --target=i386-pc \
    --recheck \
    --force \
    "$DISK" 2>&1

# Update GRUB config
chroot /mnt/ridos-target update-grub 2>&1

# Unmount
umount /mnt/ridos-target/sys
umount /mnt/ridos-target/proc
umount /mnt/ridos-target/dev/pts
umount /mnt/ridos-target/dev

# Step 7: Finish
echo -e "${BLUE}[7/7] Finalizing...${NC}"

umount /mnt/ridos-target/boot/efi
umount /mnt/ridos-target
swapoff "$SWAP"
rmdir /mnt/ridos-target

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   RIDOS OS installed successfully!       ║${NC}"
echo -e "${GREEN}║   Remove USB and reboot                  ║${NC}"
echo -e "${GREEN}║   Login: ridos / ridos                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "Reboot now? (yes/no): "
read -r REBOOT
if [ "$REBOOT" = "yes" ]; then
    reboot
fi
