#!/usr/bin/env bash
# Create a read-only collector view of the daemon's log directory. No socket is
# mounted into the collector. The external volume is shared by disposable tests.
set -euo pipefail

docker_command=(docker)
docker_os=$(docker info --format '{{.OperatingSystem}}')
if [[ "$docker_os" == *"Docker Desktop"* ]] && command -v wsl.exe >/dev/null 2>&1; then
    # The WSL API proxy rewrites bind devices relative to the user distro.
    # The Windows client creates this volume against the daemon's real data root.
    windows_cli=${DOCKER_WINDOWS_CLI:-}
    if [[ -z "$windows_cli" ]]; then
        windows_cli=$(command -v docker.exe || true)
    fi
    if [[ -z "$windows_cli" ]]; then
        windows_cli='/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe'
    fi
    if [[ ! -x "$windows_cli" ]]; then
        echo 'Set DOCKER_WINDOWS_CLI to the Docker Desktop docker.exe path.' >&2
        exit 1
    fi
    docker_command=("$windows_cli")
    native_daemon=$(docker info --format '{{.ID}}')
    windows_daemon=$("${docker_command[@]}" info --format '{{.ID}}')
    windows_daemon=${windows_daemon//$'\r'/}
    if [[ "$native_daemon" != "$windows_daemon" ]]; then
        echo 'The Windows and WSL Docker clients point at different daemons; align their contexts first.' >&2
        exit 1
    fi
fi

volume_name=${DOCKER_LOG_VOLUME:-shopsphere_docker_logs}
docker_root=$(docker info --format '{{.DockerRootDir}}')
log_root=${DOCKER_LOG_ROOT:-$docker_root/containers}
if existing=$("${docker_command[@]}" volume inspect "$volume_name" \
    --format '{{index .Options "device"}}|{{index .Options "type"}}|{{index .Options "o"}}' 2>/dev/null); then
    existing=${existing//$'\r'/}
    if [[ "$existing" != "$log_root|none|bind" ]]; then
        echo "Volume $volume_name already exists with different options; choose another DOCKER_LOG_VOLUME." >&2
        exit 1
    fi
else
    "${docker_command[@]}" volume create --driver local \
        --label shopsphere.purpose=container-log-source \
        --opt type=none --opt o=bind --opt "device=$log_root" "$volume_name" >/dev/null
fi
printf 'Prepared Docker log volume %s from %s\n' "$volume_name" "$log_root"
