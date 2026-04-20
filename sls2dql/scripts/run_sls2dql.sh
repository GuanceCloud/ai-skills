#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/bin/sls2dql" validate \
  --namespace L \
  --index access_log_index \
  --source access_log \
  --query "api:login and not(api:2fa) | select json_extract(requeststr, '$.account') as username, json_extract(requeststr, '$.password') as pwd, bizstatus"
