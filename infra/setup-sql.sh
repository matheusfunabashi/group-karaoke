#!/usr/bin/env bash
# Guide step 4 (SQL server, two serverless free-offer databases, one contained user each)
# plus the database secrets of step 7. Run once from the repository root:
#
#     bash infra/setup-sql.sh
#
# Every password is generated here and goes straight to Azure and GitHub: none is printed,
# written to a file or committed. The server admin password is thrown away at the end; reset
# it with `az sql server update --admin-password` if you ever need the admin again.
# The users are created with Python (pymssql from .venv), so sqlcmd and Docker aren't needed.
set -euo pipefail

PREFIX=mgimenes
RG=rg-$PREFIX
LOCATION=${SQL_LOCATION:-germanywestcentral}   # free offer missing there? SQL_LOCATION=<other allowed region>
SERVER=$PREFIX-sql
REPO=matheusfunabashi/group-karaoke

new_password() { echo "Aa1$(openssl rand -hex 16)"; }   # 35 chars: upper, lower and digits

ADMIN_USER=karaokeadmin
ADMIN_PASSWORD=$(new_password)

echo "1/5 SQL server $SERVER in $LOCATION"
if ! az sql server show -n "$SERVER" -g "$RG" -o none 2>/dev/null; then
  az sql server create -n "$SERVER" -g "$RG" -l "$LOCATION" \
    --admin-user "$ADMIN_USER" --admin-password "$ADMIN_PASSWORD" --minimal-tls-version 1.2 -o none
else
  az sql server update -n "$SERVER" -g "$RG" --admin-password "$ADMIN_PASSWORD" -o none
fi
# 0.0.0.0 - 0.0.0.0 is Azure's special rule for "allow Azure services" (the Container Apps)
az sql server firewall-rule create -g "$RG" -s "$SERVER" -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o none

echo "2/5 Databases (serverless, free offer: auto-pause and size are fixed by the offer)"
for svc in sessions recordings; do
  if ! az sql db show -g "$RG" -s "$SERVER" -n "$PREFIX-$svc-db" -o none 2>/dev/null; then
    az sql db create -g "$RG" -s "$SERVER" -n "$PREFIX-$svc-db" \
      --edition GeneralPurpose --compute-model Serverless --family Gen5 \
      --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local \
      --use-free-limit true --free-limit-exhaustion-behavior AutoPause -o none
  fi
done

echo "3/5 Opening the firewall to this machine for the setup only"
MY_IP=$(curl -fsS https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$SERVER" -n setup-this-machine \
  --start-ip-address "$MY_IP" --end-ip-address "$MY_IP" -o none
close_firewall() {
  echo "5/5 Closing the firewall again"
  az sql server firewall-rule delete -g "$RG" -s "$SERVER" -n setup-this-machine -o none
}
trap close_firewall EXIT

echo "4/5 One contained user per database (db_ddladmin, db_datareader, db_datawriter)"
for svc in sessions recordings; do
  USER_PASSWORD=$(new_password)
  # Passwords reach Python through environment variables, never the command line. The
  # password is only letters and digits (new_password), so it is safe inside the SQL text.
  SERVER="$SERVER.database.windows.net" DATABASE="$PREFIX-$svc-db" DB_USER="${svc}_user" \
  ADMIN_USER="$ADMIN_USER" ADMIN_PASSWORD="$ADMIN_PASSWORD" USER_PASSWORD="$USER_PASSWORD" \
  .venv/bin/python - <<'PY'
import os, time
import pymssql

e = os.environ
assert e["USER_PASSWORD"].isalnum()
for attempt in range(6):  # a new database may still be waking up
    try:
        conn = pymssql.connect(server=e["SERVER"], user=e["ADMIN_USER"], password=e["ADMIN_PASSWORD"],
                               database=e["DATABASE"], encryption="require", login_timeout=60, autocommit=True)
        break
    except pymssql.OperationalError:
        if attempt == 5:
            raise
        time.sleep(15)
user, password = e["DB_USER"], e["USER_PASSWORD"]
cur = conn.cursor()
cur.execute(f"""
    IF USER_ID('{user}') IS NULL
        CREATE USER {user} WITH PASSWORD = '{password}';
    ELSE
        ALTER USER {user} WITH PASSWORD = '{password}';
    ALTER ROLE db_ddladmin ADD MEMBER {user};
    ALTER ROLE db_datareader ADD MEMBER {user};
    ALTER ROLE db_datawriter ADD MEMBER {user};
""")
conn.close()

# Check the new user can log in to its own database, the way the service will
conn = pymssql.connect(server=e["SERVER"], user=user, password=password, database=e["DATABASE"],
                       encryption="require", login_timeout=60)
cur = conn.cursor()
cur.execute("SELECT IS_ROLEMEMBER('db_ddladmin'), IS_ROLEMEMBER('db_datareader'), IS_ROLEMEMBER('db_datawriter')")
assert cur.fetchone() == (1, 1, 1)
conn.close()
PY
  SECRET_NAME="$(echo "$svc" | tr '[:lower:]' '[:upper:]')_DB_PASSWORD"
  printf '%s' "$USER_PASSWORD" | gh secret set "$SECRET_NAME" -R "$REPO"
  echo "    ${svc}_user can log in; its password is in the GitHub secret $SECRET_NAME"
done
