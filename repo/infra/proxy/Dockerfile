FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY nginx.conf /etc/nginx/nginx.conf
COPY docker-entrypoint.sh /docker-entrypoint-custom.sh

RUN chmod +x /docker-entrypoint-custom.sh && mkdir -p /etc/nginx/certs

ENTRYPOINT ["/docker-entrypoint-custom.sh"]
