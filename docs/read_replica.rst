Read replica routing
====================

The LMS database is a Percona XtraDB (Galera) cluster. The LMS has a ``read_replica`` database alias that points at
the read node, and registers ``edx_django_utils.db.read_replica.ReadReplicaRouter``, but that router sends every
read to the writer unless a ``read_queries_only()`` block is active, and nothing opens one. This package opens it
for the work that tolerates a replica that is a few milliseconds behind the writer, so the writer is left to
learners and writes (fccn/nau-technical#1091).

Everything is **off by default** and has two gates:

* an environment setting, read at start-up, that installs the feature (a restart is needed to change it);
* a waffle switch, checked at run time, that turns it on and off from the Django admin without a deploy.

A switch that does not exist counts as off. Turning a switch off sends the next report or request back to the writer.

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Feature
     - Environment setting (default ``false``)
     - Waffle switch (default off)
   * - Heavy instructor reports
     - ``NAU_READ_REPLICA_REPORTS_ENABLED``
     - ``nau_read_replica.reports``
   * - Allow-listed GET requests
     - ``NAU_READ_REPLICA_ROUTING_ENABLED``
     - ``nau_read_replica.get_routing``

Heavy instructor reports
------------------------

The grade report, the problem grade report, the problem responses report and the student profile, may-enroll
and course survey CSVs scan every learner of a course, for minutes, on the writer. They only read, so their
queries run on the replica.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Setting / switch
     - Meaning
   * - ``NAU_READ_REPLICA_REPORTS_ENABLED`` (default ``false``)
     - Installs the routing. Read from the Tutor ``lms-env`` patch like the other ``NAU_`` settings.
   * - ``nau_read_replica.reports`` (waffle switch, default off)
     - Turns the routing on and off at run time. Create it in ``/admin/waffle/switch/``.
   * - ``NAU_READ_REPLICA_REPORT_TASKS``
     - Registered names of the Celery tasks that are routed. The default list is in
       ``read_replica/conf.py``. Note the ``.v2`` suffix of ``calculate_problem_responses_csv``. Never list a task
       that writes (grading, certificates, cohorts, bulk e-mail).

How it works: every instructor task goes through ``run_main_task``. It loads the ``InstructorTask`` row, hands the
real work to ``task_fcn`` and, afterwards, ``BaseInstructorTask.on_success`` and ``on_failure`` load the row again
and ``save()`` it, which writes the whole row back. Those reads must see the row as the writer has it, so only
``task_fcn`` runs inside ``read_queries_only()``. The wrapper is installed from ``AppConfig.ready()`` and the
conformance tests in ``read_replica/tests/test_reports.py`` fail if an upgrade renames a task or stops resolving
``run_main_task`` from the tasks module.

Each routed run logs ``Task <name> runs its queries on the read replica.`` at INFO level.

Allow-listed GET requests
-------------------------

A request is served from the replica only if it is a GET or HEAD, its path matches an entry of
``NAU_READ_REPLICA_GET_ALLOWLIST`` (regular expressions matched from the start of the path, an empty list routes
nothing) and the ``nau_read_replica.get_routing`` switch is active. Installing it (``NAU_READ_REPLICA_ROUTING_ENABLED``)
replaces ``ReadReplicaRouter`` in ``DATABASE_ROUTERS`` by ``NauReadReplicaRouter`` and adds
``NauReadReplicaMiddleware`` before the site configuration middleware, so the session, authentication and language
middleware keep reading from the writer. The Studio registers no read replica router, so nothing is installed there.

A routed request goes through three steps:

1. **Causal barrier.** The replica applies the writes of the cluster asynchronously. Before the view runs, the
   request executes ``SET SESSION wsrep_sync_wait = 1; SELECT 1; SET SESSION wsrep_sync_wait = 0`` on the replica,
   which waits until the replica has applied everything the cluster had committed at that moment. This gives
   read-your-writes to every client, browsers, MFEs and bearer-token clients alike, which a cookie or a "was there a
   POST recently" rule cannot. It costs one round trip while the replica keeps up and as much as the replication
   lag when it does not (see below). If the barrier fails, the request is served by the writer.
2. **Reads from the replica.** The view runs inside ``read_queries_only()``.
3. **Back to the writer on the first write.** Many GET endpoints write now and then (user activity, last seen
   timezone, the first visit of the day). The first INSERT, UPDATE, DELETE, REPLACE or locking read sent to the
   writer moves the rest of the request to the writer. Writes are detected in the SQL that is executed, not in the
   router: ``get_or_create`` asks the router for the writer before its first SELECT, and the JWT authentication of
   the MFE APIs calls it on every request, so counting router calls would send every MFE request to the writer.

``wsrep_sync_wait`` is set only around the barrier statement. Setting it for the whole connection makes every query
of the request pay the wait, and a page issues many.

**Circuit breaker.** The barrier waits as long as the replica lags. When the writer is busy enough for Galera flow
control to throttle the replica, that is a second or more for every routed request, and each of them would pin a
worker. So when the barrier fails, or takes longer than ``NAU_READ_REPLICA_BARRIER_SLOW_MS``, the process skips the
replica for ``NAU_READ_REPLICA_BREAKER_SECONDS`` and serves the requests from the writer, which costs nothing
extra. The breaker is per process, with no shared state, and closes by itself.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Setting
     - Meaning
   * - ``NAU_READ_REPLICA_GET_ALLOWLIST`` (default ``[]``)
     - Regular expressions matched from the start of the request path, for example
       ``^/api/course_home/outline/``.
   * - ``NAU_READ_REPLICA_DEBUG_HEADER`` (default ``false``)
     - Adds ``X-NAU-DB-Route: replica`` or ``writer`` to routed responses. Use it on STAGE to validate, not in
       production.
   * - ``NAU_READ_REPLICA_BARRIER_SLOW_MS`` (default ``250``)
     - A barrier slower than this opens the circuit breaker. The request that was slow is still served from the
       replica, because it is consistent.
   * - ``NAU_READ_REPLICA_BREAKER_SECONDS`` (default ``10``)
     - For how long a process skips the replica after the barrier failed or was slow.

What to put in the allow-list: endpoints that read a lot and write nothing that the same request reads back.
An endpoint that does a read-modify-write on a row it loaded with a plain ``get()`` must stay out, because
``save()`` writes the whole row, including columns that were a few milliseconds stale. The router logs
``A <model> loaded from the read replica is being saved`` with the path when that happens, so run the candidates on
STAGE with the switch on and look for that line and for requests tagged ``writer``.

Rollout and validation
----------------------

For the reports:

1. Set ``NAU_READ_REPLICA_REPORTS_ENABLED: true`` on STAGE and roll the LMS and the report workers.
2. Generate a grade report and a problem responses report for a course with the switch **off**, then **on**, and
   compare the two files. They must match, apart from rows that changed in between.
3. With the switch on, check the log line above, and on the database nodes (for example with the
   ``xtradb-read-write-mix`` make target of the ``xtradb_docker_deploy`` role in nau_playbooks) that the SELECT rate
   grows on the read node while the report runs and drops on the writer.
4. Watch ``wsrep_flow_control_paused`` and ``wsrep_local_recv_queue_avg`` on the read node while reports run. A
   read node that cannot apply write-sets fast enough makes Galera pause writes on the whole cluster. Switch the
   routing off if ``wsrep_flow_control_paused`` stays above 0.01.
5. Avoid schema migrations while long reports are running on the replica: a DDL needs a metadata lock on every node
   and either waits for the report or aborts it.

For the GET requests:

1. Set ``NAU_READ_REPLICA_ROUTING_ENABLED: true``, ``NAU_READ_REPLICA_DEBUG_HEADER: true`` and a short allow-list on
   STAGE, roll the LMS, and create the ``nau_read_replica.get_routing`` switch.
2. With the switch off, record a baseline with the load test. With it on, repeat the same profile and compare the
   SELECT rate of the writer, the p95 of the routed endpoints, and ``wsrep_flow_control_paused``.
3. Check by hand that a learner who submits an answer and reloads sees it straight away, and that enrolling in a
   course and landing on its home works.
4. Look at the responses (``X-NAU-DB-Route``), at the logs of the router for read-modify-writes, and at the share of
   requests that fall back to the writer. A high share means the barrier fails or the endpoint writes.
5. Stop conditions, from the first minute: ``wsrep_flow_control_paused`` above 0.01 or a growing
   ``wsrep_local_recv_queue_avg`` on the read node, or p95 of the routed endpoints worse than the baseline. Switch
   the routing off first, investigate afterwards.

Operations
----------

* ``read_replica`` is the read VIP, one node. Every request already opens a connection to it, because the NAU
  ``read_replica`` alias sets ``ATOMIC_REQUESTS``; routing adds the queries, not the connection.
* If the writer fails, the write VIP moves to the node that also holds the read VIP. Routing then offloads
  nothing. Do not size the platform on the assumption that the offload is always there.
* The keepalived check of the VIPs is TCP only. A node that is a donor, desynced or not in the Primary component
  keeps its VIP. The barrier protects the request (it falls back to the writer), the VIP check should be made
  Galera aware before relying on this in production.
* Set ``repl.causal_read_timeout`` on the read node to about one second, so a node that cannot catch up fails the
  barrier quickly (error 1205) instead of holding the request for the default thirty seconds.
* When the applier of a node that stays ``Synced`` is blocked, Galera flow control stalls the writes of the whole
  cluster within about a second. That was measured with a ``LOCK TABLES`` (rejected while ``pxc_strict_mode`` is
  ``ENFORCING``, keep it so); a metadata lock held across a DDL, for example by a long report during a migration, is
  expected to do the same. A node that is a donor or desynced is not throttled and lags without limit, so the VIP
  check must eject nodes that are not ``Synced``. Switch the routing off while running schema migrations.
* Watch ``wsrep_flow_control_paused`` and ``wsrep_local_recv_queue_avg`` on the read node. The read node applies
  every write of the cluster with ``wsrep_applier_threads`` threads and serves the routed reads with the same CPU.

Limits
------

* Only the Celery tasks listed in ``NAU_READ_REPLICA_REPORT_TASKS`` and the paths in
  ``NAU_READ_REPLICA_GET_ALLOWLIST`` are routed. The Studio (CMS) has no replica router and is not affected.
* The replica can be a few milliseconds behind the writer. A report is a snapshot in time, so this does not change
  what it means, but it is why tasks that write or read their own writes must not be listed.
* The NAU certificate export command and the partner REST API call ``use_read_replica_if_available`` themselves
  and do not depend on this routing.
