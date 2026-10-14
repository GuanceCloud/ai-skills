# Live monitor contract

## Discovery order

Use a single absolute observation interval throughout one generation run.

1. `owl.data.show_dql_namespace`: confirm `M` and its query rules.
2. `owl.metric.list`: enumerate candidate measurement sources, then inspect their fields and tags.
3. `owl.data.check_dql`: validate each representative probe.
4. `owl.data.query`: execute each probe with the chosen absolute start and end timestamps.
5. Inspect the returned file. Require `success: true`, `data_state: present`, and usable numeric data for a simple threshold monitor.

Never accept only a plausible name, syntactically valid DQL, or a zero CLI exit status as proof that a metric is usable.

## Sufficiency gate

A monitor is supported only when all of these are true:

- the measurement exists in the current workspace;
- the chosen field exists and its type is compatible with the aggregation and rule;
- every grouping and filter tag exists on that measurement;
- the final DQL passes local `dqlcheck` and Owl validation;
- the final DQL returns numeric series in the observation interval;
- the field's unit or status semantics are known well enough to define a meaningful rule.

Retry once over 24 hours when an otherwise credible metric is sparse. If it remains empty, exclude it and record the gap. Do not substitute another metric silently.

## Threshold evidence

For each monitor, record:

- source, field, aggregation, grouping tags, and final DQL;
- metric unit and semantic interpretation;
- warning/error/critical operands and operators;
- evaluation interval, `matchTimes`, and recovery periods;
- threshold provenance: user SLO, first-party semantics, or conservative SRE default;
- observed series count, minimum, maximum, and number currently matching each severity.

Observed values help detect unit mistakes and obviously bad defaults. They are not a sufficient reason to place a threshold just above today's maximum.

## Missing-series boundary

Metric absence has several meanings: telemetry failure, stopped resources, unsupported dimensions, or a resource that never emitted the metric. A checker-level no-data rule does not reliably identify an individual resource omitted from a grouped result. Examples include Pods without CPU or memory Request ratio series.

Record this gap explicitly. Recommend a Kubernetes object/configuration check or inventory-based policy when the operational question is “which resource lacks configuration?” rather than “which emitted metric crossed a threshold?”

## Operational safety

Generated artifacts are drafts until imported, reviewed, bound to notification policy, and enabled. Therefore the default artifact must be disabled and unbound. Proof-query threshold matches are reported only as aggregate counts and must not be described as active alerts.

Retry transient Owl execution failures up to three times. Do not weaken semantic or data sufficiency checks after a retry.
