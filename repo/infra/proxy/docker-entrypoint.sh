#!/bin/sh
set -eu

CERT_DIR="/etc/nginx/certs"
CERT_FILE="${CERT_DIR}/dev.crt"
KEY_FILE="${CERT_DIR}/dev.key"
CERT_CN="${HH_CERT_CN:-localhost}"

mkdir -p "${CERT_DIR}"

if [ ! -f "${CERT_FILE}" ] || [ ! -f "${KEY_FILE}" ]; then
  echo "[proxy] generating self-signed certificate for CN=${CERT_CN}"
  openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -subj "/CN=${CERT_CN}" >/dev/null 2>&1
else
  echo "[proxy] using existing certificate at ${CERT_FILE}"
fi

exec nginx -g "daemon off;"
