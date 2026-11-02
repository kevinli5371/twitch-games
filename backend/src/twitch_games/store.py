"""Small parameterized SQL helpers; callers own transaction boundaries."""

from sqlalchemy import text


def run(connection, sql, **params):
    return connection.execute(text(sql), params)


def one(connection, sql, **params):
    return run(connection, sql, **params).mappings().first()


def rows(connection, sql, **params):
    return run(connection, sql, **params).mappings().all()
