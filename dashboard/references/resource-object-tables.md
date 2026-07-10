# Resource Object Tables

## Contents

- [Data Responsibilities](#1-data-responsibilities)
- [Input Acceptance](#2-input-acceptance)
- [Field Selection](#3-field-selection)
- [Enum Candidate Detection](#4-enum-candidate-detection)
- [Value Mappings](#5-value-mappings)
- [Boolean Fields](#6-boolean-fields)
- [Units and Special Values](#7-units-and-special-values)
- [Validation](#8-validation)

## 1. Data Responsibilities

An instance list answers "what is this resource?" while telemetry charts answer "how is this resource operating?"

When resource-catalog or custom-object data exists, the instance list must prefer an object query:

```dql
CO::service_object:(last(`instance_name`), last(`region_id`), last(`status`), last(`size`)) { `account_name` = '#{account_name}' and `instance_id` = '#{instance_id}' } BY `instance_id`
```

Corresponding query metadata:

```json
{
  "namespace": "custom_object",
  "dataSource": "service_object",
  "groupBy": ["instance_id"]
}
```

Do not construct an instance table with `M::... BY node_id, shard_id`. Metric families can use different tag granularities, and instance-level series may produce `<nil>` for node or shard tags.

## 2. Input Acceptance

Before generating an instance-property table, obtain object JSON or CSV and verify:

- the object measurement or class is explicit
- at least one real resource record exists rather than only a field template
- platform metadata, object top-level fields, and a nested `message` payload can be distinguished
- top-level fields include real values and types
- required account, readable instance name, and stable instance ID fields exist
- unit metadata, API version, and update time are retained when available

If this input is missing, stop instance-table generation and request an object export. Do not substitute metric tags, invented sample fields, or an official documentation example for an object sample from the user's environment.

## 3. Field Selection

Order columns as follows:

1. account, cloud vendor, region, and project
2. instance name and instance ID
3. architecture, version, protocol, and specification
4. resource status, service status, and billing type
5. private address, port, VPC, and subnet
6. capacity, shard count, and per-shard capacity
7. feature switches, creation time, and update time

Query only top-level fields that exist in the real object sample. Do not treat node arrays inside a nested JSON string as top-level fields; create a separate node or shard detail table when that level is required.

## 4. Detect Enum Candidates

Pay particular attention when:

- a field name contains `status`, `state`, `mode`, `type`, `arch`, `edition`, or `bill`
- a field name contains `enabled`, `supported`, or `protection`
- numeric or boolean samples contain only a few discrete values
- a raw number is unreadable while the product console displays a business label

Low cardinality is a reason to research an enum, not evidence from which to infer its meaning automatically.

## 5. Generate Value Mappings

Confirm value semantics with the SKILL's Official Field Research route. Do not maintain vendor-specific data dictionaries in this generic reference.

Use the exact query result field, such as `last(status)`:

```json
{
  "field": "last(status)",
  "operation": "=",
  "queryCode": "A",
  "mappingVal": "Running",
  "originalVal": ["2"]
}
```

Requirements:

- `field` must exactly match the DQL return field.
- `queryCode` must match the query.
- `originalVal` must use the UI string representation of the real return type.
- One field and original value may have only one `mappingVal`.
- Prefer the complete official data dictionary rather than mapping only values observed in the sample.
- Do not mix unconfirmed values into confirmed mappings.
- Generate `valColorMappings` only when status coloring is useful; do not create redundant entries whose colors are all empty.

## 6. Boolean Fields

Distinguish current state from capability:

- `*_enabled`: `Enabled` / `Disabled`
- `*_supported`: `Supported` / `Unsupported`

Check the real type and cover `0/1`, `true/false`, or string representations when appropriate. Do not label "supported" as though a feature were currently enabled.

## 7. Units and Special Values

- Obtain units from the object schema or current first-party API and specification documentation; do not guess from field names.
- Distinguish `GB` from `Gb` and `MB` from `Mb`.
- `0` may be a valid capacity or may mean not applicable; only official documentation and architecture context can decide.
- When a condition cannot be represented accurately by static `valMappings`, use a conservative label such as `Not Sharded` or `Not Applicable`, or preserve the original value and document the limitation.

## 8. Validation

- The instance-table DQL begins with `CO::`.
- The object input source is recorded and contains at least one real object record.
- `namespace` is `custom_object`.
- `dataSource` is the real object measurement or class.
- `BY` uses a stable resource ID and does not mix in metric-granularity tags.
- Every queried field exists in the object sample.
- Headers are readable through `alias` or `fieldMapping`.
- Unit settings match object semantics.
- Every displayed enum candidate is mapped or has a documented reason for preserving the original value.
- `valMappings` contains no duplicate conflicts and covers observed values where evidence is sufficient.
