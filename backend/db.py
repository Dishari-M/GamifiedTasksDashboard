import os

import oracledb

def get_connection():
    wallet_dir = os.getenv("DB_WALLET_DIR")
    connection_args = {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "dsn": os.getenv("DB_DSN"),
    }

    if wallet_dir:
        connection_args["config_dir"] = wallet_dir
        connection_args["wallet_location"] = wallet_dir
        wallet_password = os.getenv("DB_WALLET_PASSWORD")
        if wallet_password:
            connection_args["wallet_password"] = wallet_password

    return oracledb.connect(**connection_args)
