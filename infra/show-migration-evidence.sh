#!/usr/bin/env bash
# Evidence that migration V002 altered a table that already held data on Azure:
# prints schema_migrations and the recordings rows (without the audio bytes) of the
# recordings database, and saves the output in docs/evidence/. Run from the repo root:
#
#     bash infra/show-migration-evidence.sh
#
# The admin password is reset to a new random one for this run and never printed or saved.
set -euo pipefail

PREFIX=mgimenes
RG=rg-$PREFIX
SERVER=$PREFIX-sql
ADMIN_PASSWORD="Aa1$(openssl rand -hex 16)"
OUT=docs/evidence/v002-migration-on-azure.txt

az sql server update -n "$SERVER" -g "$RG" --admin-password "$ADMIN_PASSWORD" -o none
MY_IP=$(curl -fsS https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$SERVER" -n evidence-this-machine \
  --start-ip-address "$MY_IP" --end-ip-address "$MY_IP" -o none
trap 'az sql server firewall-rule delete -g "$RG" -s "$SERVER" -n evidence-this-machine -o none' EXIT

mkdir -p docs/evidence
SERVER="$SERVER.database.windows.net" DATABASE="$PREFIX-recordings-db" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
.venv/bin/python - <<'PY' | tee "$OUT"
import os, time
from datetime import datetime, timezone

import pymssql

e = os.environ
for attempt in range(6):  # the database may be paused and need a minute to resume
    try:
        conn = pymssql.connect(server=e["SERVER"], user="karaokeadmin", password=e["ADMIN_PASSWORD"],
                               database=e["DATABASE"], encryption="require", login_timeout=60, as_dict=True)
        break
    except pymssql.OperationalError:
        if attempt == 5:
            raise
        time.sleep(15)
cur = conn.cursor()
print(f"Azure SQL {e['SERVER']} / {e['DATABASE']}, queried {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
print("schema_migrations:")
cur.execute("SELECT version, applied_at FROM schema_migrations ORDER BY version")
for row in cur.fetchall():
    print(f"  {row['version']:40} applied {row['applied_at']}")
print("\nrecordings (audio bytes not shown):")
cur.execute("""
    SELECT id, turn_id, session_id, file_name, size_bytes, created_at,
           CASE WHEN audio IS NULL THEN 'NULL (saved before V002)' ELSE CONCAT(DATALENGTH(audio), ' bytes') END AS audio
    FROM recordings ORDER BY id""")
for row in cur.fetchall():
    print(f"  id={row['id']} turn={row['turn_id']} session={row['session_id']} file={row['file_name']} "
          f"size={row['size_bytes']} created={row['created_at']} audio={row['audio']}")
conn.close()
PY
echo
echo "Saved to $OUT"
