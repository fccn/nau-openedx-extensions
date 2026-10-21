"""
Run time switches of the read replica routing.

The environment settings install a feature, the switches turn it on and off without a restart. A switch that does
not exist counts as off, so nothing is routed until an operator creates it in the Django admin
(``/admin/waffle/switch/``). Turning a switch off is the fast way out if the replica misbehaves: the next report
or request goes back to the writer.
"""
from edx_toggles.toggles import WaffleSwitch

# .. toggle_name: nau_read_replica.reports
# .. toggle_implementation: WaffleSwitch
# .. toggle_default: False
# .. toggle_description: Run the queries of the heavy instructor report tasks (grade report, problem grade report,
#   problem responses, student profile information, may-enroll and course survey reports) on the read replica
#   instead of the writer. Only has an effect when NAU_READ_REPLICA_REPORTS_ENABLED is true.
# .. toggle_use_cases: circuit_breaker
# .. toggle_creation_date: 2026-10-21
# .. toggle_tickets: https://github.com/fccn/nau-technical/issues/1091
REPORTS = WaffleSwitch("nau_read_replica.reports", __name__)
