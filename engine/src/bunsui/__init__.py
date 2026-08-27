"""bunsui engine — local data platform control plane + warehouse helpers.

Product rules (keep later phases consistent):
- Job = execution unit (dbt command or arbitrary Python). Jobs may have ordered
  dependencies; chaining can be sync or async; async completion is detected by
  polling SQLite status writes.
- Asset = Dagster-style unit of status in SQLite. dbt assets come from
  run_results.json (all nodes). Tests attached to a model are children of that
  model; a test error is an error on the parent model asset.
- Final dbt ingest is run_results.json; retain those files for a period; store
  stdout logs with the run for the UI.
"""

__version__ = "2.0.0a0"
