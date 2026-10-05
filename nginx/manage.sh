#!/usr/bin/env bash
# Always address this repository's NGINX instance, independent of the shell cwd.
set -euo pipefail

nginx_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
nginx_bin=${NGINX_BIN:-nginx}
action=${1:-test}

if ! command -v "$nginx_bin" >/dev/null 2>&1; then
    printf 'NGINX is required in this Linux/WSL environment. Check nginx -v.\n' >&2
    exit 1
fi

mkdir -p "$nginx_dir/runtime"
options=(-p "$nginx_dir/" -c nginx.conf -e stderr)

case "$action" in
    test)
        exec "$nginx_bin" "${options[@]}" -t
        ;;
    start)
        "$nginx_bin" "${options[@]}" -t
        exec "$nginx_bin" "${options[@]}"
        ;;
    foreground)
        "$nginx_bin" "${options[@]}" -t
        exec "$nginx_bin" "${options[@]}" -g 'daemon off;'
        ;;
    reload)
        "$nginx_bin" "${options[@]}" -t
        exec "$nginx_bin" "${options[@]}" -s reload
        ;;
    stop)
        exec "$nginx_bin" "${options[@]}" -s quit
        ;;
    *)
        printf 'Usage: bash nginx/manage.sh {test|start|foreground|reload|stop}\n' >&2
        exit 2
        ;;
esac
