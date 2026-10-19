#!/usr/bin/env bash
# End-to-end demo against a deployed stack:
#   1. ask the API for an upload URL
#   2. upload the image straight to S3
#   3. poll the status until the workflow finishes
#
# Usage: scripts/demo.sh path/to/image.jpg
# Requires: curl, jq, terraform outputs (run from the repo root after `make deploy`).
set -euo pipefail

FILE="${1:?Usage: scripts/demo.sh path/to/image.(jpg|png|webp)}"
API="$(terraform -chdir=terraform output -raw api_endpoint)"

case "$(echo "$FILE" | tr '[:upper:]' '[:lower:]')" in
  *.jpg|*.jpeg) TYPE="image/jpeg" ;;
  *.png)        TYPE="image/png" ;;
  *.webp)       TYPE="image/webp" ;;
  *) echo "Only .jpg, .png and .webp are accepted" >&2; exit 1 ;;
esac

echo "==> 1. Requesting upload URL"
RESPONSE="$(curl -sS -X POST "$API/uploads" \
  -H "Content-Type: application/json" \
  -d "{\"contentType\":\"$TYPE\",\"fileName\":\"$(basename "$FILE")\"}")"
echo "$RESPONSE" | jq '{imageId, expiresInSeconds, maxBytes}'
IMAGE_ID="$(echo "$RESPONSE" | jq -r .imageId)"
URL="$(echo "$RESPONSE" | jq -r .upload.url)"

# Every policy field must be sent as a form field, and the file must come last.
FORM_ARGS=()
while IFS= read -r field; do
  FORM_ARGS+=(-F "$field")
done < <(echo "$RESPONSE" | jq -r '.upload.fields | to_entries[] | "\(.key)=\(.value)"')

echo "==> 2. Uploading $FILE directly to S3"
curl -sS -f -o /dev/null -w "S3 answered HTTP %{http_code}\n" "${FORM_ARGS[@]}" -F "file=@$FILE" "$URL"

echo "==> 3. Waiting for processing"
for _ in $(seq 1 30); do
  STATUS_JSON="$(curl -sS "$API/images/$IMAGE_ID")"
  STATUS="$(echo "$STATUS_JSON" | jq -r .status)"
  echo "   status: $STATUS"
  case "$STATUS" in
    COMPLETED|REJECTED|FAILED) echo "$STATUS_JSON" | jq .; exit 0 ;;
  esac
  sleep 2
done
echo "Timed out waiting for $IMAGE_ID" >&2
exit 1
