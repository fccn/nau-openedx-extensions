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

A switch that does not exist counts as off. Turning a switch off sends the next report back to the writer.

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

Rollout and validation
----------------------

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

Limits
------

* Only the Celery tasks listed in ``NAU_READ_REPLICA_REPORT_TASKS`` are routed. The Studio (CMS) has no replica
  router and is not affected.
* The replica can be a few milliseconds behind the writer. A report is a snapshot in time, so this does not change
  what it means, but it is why tasks that write or read their own writes must not be listed.
* The NAU certificate export command and the partner REST API call ``use_read_replica_if_available`` themselves
  and do not depend on this routing.
