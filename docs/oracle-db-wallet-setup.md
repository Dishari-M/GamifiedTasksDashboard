# Oracle ATP Wallet Setup

Use this guide when Oracle Autonomous Transaction Processing has Mutual TLS
authentication set to Required. In this mode the backend must connect with the
Oracle wallet downloaded from the database.

Do not commit wallet files, database passwords, or `.env` files containing
secrets.

## 1. Download The Wallet

1. Open the Oracle Cloud Console.
2. Go to Oracle Database, then Autonomous Database.
3. Open the ATP database, for example `TASKSDB`.
4. Click Database connection.
5. Click Download wallet.
6. Choose Instance wallet if available.
7. Enter a wallet password and download the zip file.

The wallet zip contains connection files such as `tnsnames.ora` and
`ewallet.pem`. The backend uses those files for mTLS connections.

## 2. Store The Wallet Outside The Repo

Create a local folder outside this repository, then unzip the wallet there.

Example on Windows:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.oracle\wallet_tasksdb"
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Wallet_TASKSDB.zip" -DestinationPath "$env:USERPROFILE\.oracle\wallet_tasksdb" -Force
```

Expected important files:

```text
C:\Users\Dishari\.oracle\wallet_tasksdb\tnsnames.ora
C:\Users\Dishari\.oracle\wallet_tasksdb\ewallet.pem
```

## 3. Pick The TNS Alias

Open the wallet folder and inspect `tnsnames.ora`. It contains aliases like:

```text
tasksdb_high
tasksdb_medium
tasksdb_low
tasksdb_tp
tasksdb_tpurgent
```

Use `tasksdb_tp` for normal transaction-processing app traffic if it exists.
Use `tasksdb_low` for light local development. `tasksdb_high` works, but it is
usually more aggressive than this app needs.

For your current connection string, the matching alias is likely:

```text
tasksdb_tp
```

## 4. Set Backend Environment Variables

Set these in the same PowerShell window before starting the backend:

```powershell
$env:DB_USER="DEVQUEST_APP"
$env:DB_PASSWORD="<your_database_user_password>"
$env:DB_DSN="tasksdb_tp"
$env:DB_WALLET_DIR="$env:USERPROFILE\.oracle\wallet_tasksdb"
$env:DB_WALLET_PASSWORD="<wallet_password_used_when_downloading_wallet>"
```

If the wallet was downloaded without a password requirement for your driver
setup, leave `DB_WALLET_PASSWORD` unset:

```powershell
Remove-Item Env:\DB_WALLET_PASSWORD -ErrorAction SilentlyContinue
```

## 5. Confirm Backend Wallet Support

The backend connection helper supports both wallet and no-wallet connections.
When `DB_WALLET_DIR` is set, it passes wallet options to `python-oracledb`:

```python
oracledb.connect(
    user=...,
    password=...,
    dsn=...,
    config_dir=...,
    wallet_location=...,
    wallet_password=...,
)
```

`config_dir` points to the folder containing `tnsnames.ora`, and
`wallet_location` points to the folder containing `ewallet.pem`.

## 6. Test The Database Connection

From the project root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -c "import os, oracledb; c=oracledb.connect(user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], dsn=os.environ['DB_DSN'], config_dir=os.environ['DB_WALLET_DIR'], wallet_location=os.environ['DB_WALLET_DIR'], wallet_password=os.environ.get('DB_WALLET_PASSWORD')); print('Connected:', c.version); c.close()"
```

Expected output:

```text
Connected: <oracle_version>
```

## 7. Start The Backend

After the connection test works:

```powershell
cd C:\Users\Dishari\Downloads\Tasks-Gamified-Dashboard-main\Tasks-Gamified-Dashboard-main\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

DB-backed endpoints such as `/tasks` and `/quests` will use the Oracle wallet
connection.

## Troubleshooting

`ORA-01017: invalid username/password`

Check `DB_USER` and `DB_PASSWORD`. This is the database app user password, not
the wallet password.

`ORA-12154` or alias not found

Check that `DB_DSN` matches an alias in `tnsnames.ora`, and that
`DB_WALLET_DIR` points to the unzipped wallet folder.

`DPY-4011`, TLS, certificate, or mTLS errors

Check that `ewallet.pem` exists in `DB_WALLET_DIR`, the wallet password is
correct, and the ATP database still has the wallet enabled.

Connection hangs or times out

Check local firewall/VPN settings and confirm that outbound `tcps` traffic to
port `1522` is allowed.

## Security Notes

- Keep wallet files outside the repository.
- Never commit wallet zip files, `ewallet.pem`, database passwords, or local
  `.env` files.
- Prefer an application database user such as `DEVQUEST_APP` instead of using
  `ADMIN`.
- Rotate the wallet if it is accidentally shared.
- Use a compartment, VCN, or allowed IP setup appropriate for the environment.
