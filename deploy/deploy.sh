#!/usr/bin/env bash
# ============================================================
# MyPi Raspberry Pi deployment script
#
# Run ON the Pi as your normal user (linsen):
#   bash ~/workspace/MyPi/deploy/deploy.sh
#
# What it does:
#   1. Enable SPI (needed by the e-ink display)
#   2. Install system packages (Python, Node.js, git, SPI libs)
#   3. Clone / update the Waveshare e-Paper SDK
#   4. Create Python venv & install backend deps
#   5. Build frontend (web/)
#   6. Install & start the systemd service
# ============================================================

set -euo pipefail

MYPI_DIR="$HOME/workspace/MyPi"
VENV_DIR="$MYPI_DIR/.venv"
EPAPER_DIR="$HOME/workspace/e-Paper"
NODE_MAJOR=20

log()  { printf '\n\033[1;36m>>> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!! %s\033[0m\n' "$*"; }

# ----------------------------------------------------------
# 0. Preflight
# ----------------------------------------------------------
if [ ! -d "$MYPI_DIR/server" ]; then
    echo "ERROR: $MYPI_DIR/server not found."
    echo "Please clone the MyPi repo to $MYPI_DIR first:"
    echo "  git clone <repo-url> $MYPI_DIR"
    exit 1
fi

# ----------------------------------------------------------
# 1. Enable SPI interface
# ----------------------------------------------------------
log "Checking SPI..."
if ! lsmod | grep -q spi_bcm2835; then
    warn "SPI not loaded. Enabling via raspi-config..."
    sudo raspi-config nonint do_spi 0
    warn "SPI enabled. A reboot may be required if this is the first time."
fi

# ----------------------------------------------------------
# 2. System packages
# ----------------------------------------------------------
log "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    git curl build-essential \
    libspidev-dev \
    libjpeg-dev libopenjp2-7 libtiff-dev libfreetype6-dev

# Node.js (for building frontend)
if ! command -v node &>/dev/null || [ "$(node -e 'console.log(process.versions.node.split(".")[0])')" -lt "$NODE_MAJOR" ]; then
    log "Installing Node.js $NODE_MAJOR..."
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | sudo -E bash -
    sudo apt-get install -y -qq nodejs
fi

# ----------------------------------------------------------
# 3. Waveshare e-Paper SDK
# ----------------------------------------------------------
log "Setting up Waveshare e-Paper SDK..."
if [ -d "$EPAPER_DIR" ]; then
    (cd "$EPAPER_DIR" && git pull --ff-only 2>/dev/null || true)
else
    git clone --depth 1 https://github.com/waveshareteam/e-Paper.git "$EPAPER_DIR"
fi

EPD_LIB="$EPAPER_DIR/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib"
if [ ! -f "$EPD_LIB/epd13in3E.py" ]; then
    echo "ERROR: epd13in3E.py not found at $EPD_LIB"
    exit 1
fi
log "EPD SDK ready at $EPD_LIB"

# ----------------------------------------------------------
# 4. Python virtual environment & backend deps
# ----------------------------------------------------------
log "Setting up Python venv..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip wheel -q
pip install -r "$MYPI_DIR/server/requirements.txt" -q
log "Backend dependencies installed."

# ----------------------------------------------------------
# 5. Build frontend
# ----------------------------------------------------------
log "Building frontend (web/)..."
cd "$MYPI_DIR/web"
npm ci --prefer-offline 2>/dev/null || npm install
npm run build
log "Frontend built → web/dist/"

# ----------------------------------------------------------
# 6. systemd service
# ----------------------------------------------------------
log "Installing systemd service..."
sudo cp "$MYPI_DIR/deploy/mypi.service" /etc/systemd/system/mypi.service

# Patch MYPI_EPD_SDK into the service if it differs from default
if ! grep -q "MYPI_EPD_SDK" /etc/systemd/system/mypi.service; then
    sudo sed -i "/^Environment=MYPI_DISPLAY/a Environment=MYPI_EPD_SDK=$EPD_LIB" \
        /etc/systemd/system/mypi.service
fi

sudo systemctl daemon-reload
sudo systemctl enable mypi.service
sudo systemctl restart mypi.service

# ----------------------------------------------------------
# 7. Summary
# ----------------------------------------------------------
sleep 2
IP=$(hostname -I | awk '{print $1}')

log "Deployment complete!"
echo ""
echo "  Service status : sudo systemctl status mypi"
echo "  View logs      : sudo journalctl -u mypi -f"
echo "  Restart        : sudo systemctl restart mypi"
echo ""
echo "  Access the web console from any device on the LAN:"
echo "    http://${IP}:5050"
echo ""
echo "  The e-ink display will refresh when scenes trigger or"
echo "  you press 'show now' in the web console."
echo ""
