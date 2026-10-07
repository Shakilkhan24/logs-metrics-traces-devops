#!/bin/sh
# Measure Docker storage through the existing non-recursive log directory view.
# Avoid parsing WSL mountinfo; CPU/memory/disk I/O remain native collectors.
set -eu

collect_storage() {
    while :; do
        destination=/textfile/docker-storage.prom
        if values=$(stat -f -c '%S %b %a' /docker-storage); then
            printf '%s\n' "$values" | awk '
                { print "# HELP shopsphere_docker_storage_size_bytes Docker storage filesystem capacity."
                  print "# TYPE shopsphere_docker_storage_size_bytes gauge"
                  printf "shopsphere_docker_storage_size_bytes %.0f\n", $1 * $2
                  print "# HELP shopsphere_docker_storage_avail_bytes Docker storage space available to unprivileged users."
                  print "# TYPE shopsphere_docker_storage_avail_bytes gauge"
                  printf "shopsphere_docker_storage_avail_bytes %.0f\n", $1 * $3
                  print "# HELP shopsphere_docker_storage_collection_success Docker storage stat collection succeeded."
                  print "# TYPE shopsphere_docker_storage_collection_success gauge"
                  print "shopsphere_docker_storage_collection_success 1" }
            ' > "$destination.tmp"
        else
            printf '%s\n' '# TYPE shopsphere_docker_storage_collection_success gauge' \
                'shopsphere_docker_storage_collection_success 0' > "$destination.tmp"
        fi
        # The exporter never sees a partially written exposition file.
        mv "$destination.tmp" "$destination"
        sleep 5
    done
}

collect_storage &
exec /bin/node_exporter "$@"
