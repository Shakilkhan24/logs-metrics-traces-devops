# NGINX reverse proxy

In Phase 4, `nginx.conf` will define how NGINX receives client requests and
forwards them to FastAPI. A reverse proxy provides a stable entry point in front
of an application and produces access and error logs at that boundary.

Later phases will collect those logs and scrape NGINX measurements through an
exporter. In production, this layer may also handle TLS, routing, and load
balancing. Phase 1 contains no runnable NGINX configuration.
