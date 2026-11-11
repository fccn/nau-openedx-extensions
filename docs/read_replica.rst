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

The grade report, the problem responses report and the student profile, may-enroll and course survey CSVs scan
every learner of a course, for minutes, on the writer. They only read, so their queries run on the replica (the
problem responses report only when its requester has staff access, see below).

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
       that writes (grading, certificates, cohorts, bulk e-mail), nor the problem grade report.

**Reports that are not routed.** The problem grade report (``calculate_problem_grade_report``) writes whoever
requests it, so it stays on the writer and must not be added to ``NAU_READ_REPLICA_REPORT_TASKS``. For every
learner it builds the course blocks, and the block transformers write while they do: the library content
transformer saves the learner's random selection in ``courseware_studentmodule``, and the cohort partition scheme
assigns a learner without a cohort to a random-assignment cohort, creating the default cohort if the course has
none, which also triggers a grade recalculation for that learner. A lab run with 37 learners made 257 writes,
215 of them locking reads. The router sends them to the writer, but the task then reads back rows it has just
written, and a replica that lags does not have them yet: one run failed because the default cohort it had just
created was missing on the replica. The five routed reports were run with every SQL statement recorded and, for a
requester with staff access, write nothing besides the ``InstructorTask`` row, and their files are identical with
the routing on and off.

**Problem responses report.** The report builds the course blocks for the user who requested it, so it is routed
only when that user has staff access to the course. The user partition transformer skips the group checks for staff.
For any other requester, a data researcher for example, in a course whose content groups use the cohort scheme, it
assigns the requester to a cohort, creating the default cohort if the course has none, and the report then reads
that cohort back from a replica that does not have it yet, so the report fails. The wrapper makes the same
``has_access(requester, "staff", course_key)`` check as the transformer, on the writer, before the report starts.
It is not configurable: it applies whenever the report is listed in ``NAU_READ_REPLICA_REPORT_TASKS``. If the check
fails, a warning is logged and the report stays on the writer.

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
2. As a user with staff access, generate a grade report and a problem responses report for a course with the
   switch **off**, then **on**, and compare the two files. They must match, apart from rows that changed in between.
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
