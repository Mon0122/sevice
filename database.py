"""Small MySQL helper used by app.py."""

import pymysql

DB_SETTINGS = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "serviceflow_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def connect():
    return pymysql.connect(**DB_SETTINGS)


def fetch_all(sql, values=()):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, values)
            return cursor.fetchall()


def fetch_one(sql, values=()):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, values)
            return cursor.fetchone()


def execute(sql, values=()):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, values)
            return cursor.lastrowid
