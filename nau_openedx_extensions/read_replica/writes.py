"""
Detecting writes at the SQL level.

The ORM calls the database router for the *intent* to write: ``get_or_create`` asks the router for the writer
before its first SELECT, and so does assigning a foreign key to an unsaved instance. The JWT authentication of the
MFE APIs calls ``get_or_create`` for the user on every request, so a router that counted those calls would send
every MFE request to the writer even though nothing is written. The SQL that really runs does not have that
problem, which is why the statements are inspected as they are executed.
"""
_DATA_CHANGING = ("INSERT", "UPDATE", "DELETE", "REPLACE")
_ROW_LOCKS = ("FOR UPDATE", "FOR SHARE", "LOCK IN SHARE MODE")


def is_write(sql):
    """
    Return whether ``sql`` changes data or takes row locks, so it must be seen by the writer.

    ``SELECT ... FOR UPDATE`` counts: a locking read on the replica would lock nothing that matters. SAVEPOINT,
    RELEASE, SET and COMMIT do not count.
    """
    statement = sql.lstrip()
    keyword = statement[:7].upper()
    if keyword.startswith(_DATA_CHANGING):
        return True
    if keyword.startswith("SELECT"):
        tail = statement[-80:].upper()
        return any(lock in tail for lock in _ROW_LOCKS)
    return False


class WriteDetector:
    """
    A Django ``execute_wrapper`` that records the first write of the request.

    It is installed on the writer connection for the duration of a routed request. The flag is set before the
    statement runs, so nothing that follows it can read from the replica.
    """

    def __init__(self, state):
        self.state = state

    def __call__(self, execute, sql, params, many, context):
        if not self.state.wrote and is_write(sql):
            self.state.wrote = True
        return execute(sql, params, many, context)
