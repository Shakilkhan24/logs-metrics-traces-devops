FROM nginx:1.30.5-alpine3.24@sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94

COPY nginx/container.conf /etc/nginx/nginx.conf
COPY nginx/includes/ /etc/nginx/includes/

USER nginx
EXPOSE 8088
STOPSIGNAL SIGQUIT
# Configuration is baked into the image; no root entrypoint edits are needed.
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
