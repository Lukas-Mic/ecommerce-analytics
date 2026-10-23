#!/usr/bin/env bash
# Jednorazowe przygotowanie świeżego VPS (Ubuntu 24.04) pod projekt ecommerce-analytics.
# Uruchom jako root:  bash setup_vps.sh [nazwa_uzytkownika]
#
# Co robi:
#   - aktualizuje system i włącza automatyczne poprawki bezpieczeństwa,
#   - instaluje Dockera (oficjalne repozytorium) z limitem rozmiaru logów,
#   - tworzy użytkownika roboczego z Twoim kluczem SSH (z konta root),
#   - wyłącza logowanie na roota i logowanie hasłem,
#   - włącza firewall (SSH, HTTP, HTTPS) i fail2ban,
#   - dodaje 2 GB swapu.
set -euo pipefail

NEW_USER="${1:-analityk}"

[ "$(id -u)" -eq 0 ] || { echo "Uruchom jako root."; exit 1; }
[ -s /root/.ssh/authorized_keys ] || {
  echo "Brak /root/.ssh/authorized_keys - najpierw dodaj klucz SSH, inaczej stracisz dostęp."; exit 1; }

export DEBIAN_FRONTEND=noninteractive

echo "==> Aktualizacja systemu"
apt-get update
apt-get -y upgrade
apt-get install -y ca-certificates curl git make unzip ufw fail2ban unattended-upgrades

echo "==> Docker"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
systemctl enable --now docker
systemctl restart docker

echo "==> Użytkownik $NEW_USER"
if ! id "$NEW_USER" &>/dev/null; then
  adduser --disabled-password --gecos "" "$NEW_USER"
fi
usermod -aG sudo,docker "$NEW_USER"
install -d -m 700 -o "$NEW_USER" -g "$NEW_USER" "/home/$NEW_USER/.ssh"
install -m 600 -o "$NEW_USER" -g "$NEW_USER" /root/.ssh/authorized_keys "/home/$NEW_USER/.ssh/authorized_keys"
# Konto bez hasła (logowanie tylko kluczem), więc sudo bez hasła
echo "$NEW_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$NEW_USER"
chmod 440 "/etc/sudoers.d/90-$NEW_USER"
visudo -cf "/etc/sudoers.d/90-$NEW_USER"

echo "==> SSH: tylko klucze, bez roota"
cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
sshd -t
systemctl reload ssh

echo "==> Firewall i fail2ban"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
systemctl enable --now fail2ban

echo "==> Swap 2 GB"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf
sysctl -p /etc/sysctl.d/99-swap.conf

echo "==> Automatyczne poprawki bezpieczeństwa"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo
echo "Gotowe. Docker: $(docker --version)"
echo "WAŻNE: NIE zamykaj tej sesji, dopóki w nowym oknie nie zalogujesz się:"
echo "  ssh $NEW_USER@$(hostname -I | awk '{print $1}')"
echo "Jeśli system prosi o restart (nowe jądro): sudo reboot"
