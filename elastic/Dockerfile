FROM docker.elastic.co/elastic-agent/elastic-agent-slim:9.5.4@sha256:8cea7e31be5c8495c2de85cf7258ecb77f977fe59988997923c9eab51dab8c62

# Bake permissions into the image; Windows/WSL bind mounts may appear writable.
COPY --chmod=0644 elastic/elastic-agent.yml /usr/share/elastic-agent/elastic-agent.yml
COPY --chmod=0644 elastic/docker-source.js /usr/share/elastic-agent/docker-source.js
