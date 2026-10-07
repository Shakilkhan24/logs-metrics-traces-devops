FROM prom/node-exporter:v1.12.1@sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0

# This lab uses kernel disk counters without optional host udev properties.
USER root
RUN mkdir -p /run/udev/data
USER nobody
COPY --chmod=0555 prometheus/host-filesystem.sh /usr/local/bin/host-filesystem.sh
ENTRYPOINT ["/bin/sh", "/usr/local/bin/host-filesystem.sh"]
