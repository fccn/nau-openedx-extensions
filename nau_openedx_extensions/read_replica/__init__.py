"""
Move read-only work off the MySQL writer and onto the read replica
(fccn/nau-technical#1091).

The LMS already registers ``edx_django_utils.db.read_replica.ReadReplicaRouter`` but, by design, it sends every
read to the writer unless a ``read_queries_only()`` block is active, and nothing opens one. This package opens
that block for the work that is safe to serve from a replica that can be a few milliseconds behind the writer.

Everything here is inert by default. Each feature has two gates, so it can be shipped dark and then turned on
and, above all, turned off again quickly:

- an environment setting, read once at start-up, that installs the feature (it needs a restart);
- a waffle switch, checked at run time, that turns it on and off from the Django admin without a deploy.

========================  ==========================================  ===================================
Feature                   Environment setting (default ``False``)     Waffle switch (default off)
========================  ==========================================  ===================================
Heavy instructor reports  ``NAU_READ_REPLICA_REPORTS_ENABLED``        ``nau_read_replica.reports``
========================  ==========================================  ===================================

See ``docs/read_replica.rst`` for the rollout, the validation steps and the stop conditions.
"""
