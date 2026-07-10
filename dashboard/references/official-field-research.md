# Official Field Research

This reference defines a research method only. It must not become a built-in data dictionary for any cloud vendor or product. Reconfirm semantics for the current service, interface version, and first-party documentation during every Dashboard task.

## 1. When Research Is Required

Research is mandatory when any of the following applies:

- An object field is a low-cardinality number or boolean that users cannot interpret directly.
- A field name contains `status`, `state`, `mode`, `type`, `arch`, `edition`, `bill`, `enabled`, or `supported`.
- A metrics CSV or object schema has no unit, or bits versus bytes, ratio versus percentage, or instance versus shard scope is ambiguous.
- A manually edited Dashboard contains mappings whose source or applicable version is unclear.
- The same field name can have different meanings across vendors, services, or API versions.

## 2. Establish the Research Context

Record:

- cloud vendor or component
- product or service name and version
- API action, namespace, measurement, or object class
- API version, collector version, or documentation update date
- original field name in snake_case and its camelCase or PascalCase API form
- real sample values and field types
- the planned Dashboard column or metric

Do not guess mappings when this context is missing.

## 3. Consult First-Party Sources

Use only first-party sources to confirm technical fields:

1. current official API documentation, data dictionaries, or API Explorer
2. current official metric, product specification, billing, and status documentation
3. official SDK models, enum constants, or generated code
4. official release notes and API change history

Useful searches combine:

- product name, API action, and original field name
- product name and candidate enum values
- product name, field meaning, and terms such as data dictionary, unit, billing, or status
- snake_case, camelCase, and PascalCase variants

When the user supplies a documentation site, search that official site first. Do not substitute forums, reposted articles, or another vendor's similarly named field for technical evidence.

Internet research may confirm the semantics and unit of a field that exists in the user's input. It must never add metrics that are absent from the user's CSV.

## 4. Build an Evidence Table

Maintain a research record or delivery note:

| Field | Original value | Display value/unit | Source URL | API/doc version | Evidence level |
|---|---|---|---|---|---|
| `status` | `2` | `Running` | official link | `YYYY-MM-DD` | Confirmed |

Evidence levels:

- **Confirmed**: an official API dictionary, API Explorer, or official SDK explicitly defines the field and value.
- **Cross-confirmed**: official product documentation supplies the business label and a real object sample or console view confirms the numeric relationship.
- **Observed only**: the value appears only in a sample or manually edited JSON and has no first-party confirmation.
- **Unknown**: no reliable mapping can be established.

Only Confirmed values and Cross-confirmed values with a complete evidence chain may be written to `valMappings` by default. Preserve all other original values and list them in the delivery notes.

## 5. Confirm Units

Unit research must answer:

- whether the value is bytes or bits, such as `GB` versus `Gb`
- whether capacity is decimal or binary; if the source only says `G`, record that wording and choose the closest platform unit
- whether a ratio is `0..1` or a percentage is `0..100`
- whether a value is cumulative, per-second, or averaged over a sampling window
- whether it represents an instance total, node value, shard value, or replica value
- whether time is seconds, milliseconds, microseconds, or a timestamp

If the unit cannot be confirmed, use a custom raw display and mark it `UNVERIFIED`. Do not fill in a plausible standard unit merely for visual polish.

## 6. Generate Configuration

- Convert field names into readable labels with `fieldMapping` or `alias`.
- Use `valMappings` only for confirmed enums.
- Treat `*_enabled` and `*_supported` separately: the first usually describes current state and the second capability, but the official field definition remains authoritative.
- Keep unit configuration aligned with official scope. A field alias may clarify scope, such as `Capacity (GB)` or `Capacity per Shard (GB)`.
- Create `valColorMappings` only when status coloring is useful; do not create placeholder entries whose colors are all empty.

## 7. Validate and Deliver

- Verify that every sampled enum value is either confirmed or explicitly listed as unknown.
- Verify that the same field and original value do not have conflicting mappings.
- Verify that units, aliases, and DQL return fields use the same scope.
- Verify that the sources apply to the current product and API version rather than a deprecated interface.
- Include first-party links, confirmation date, and unresolved values in the final delivery.
- Do not hard-code task-specific vendor enums back into the generic skill. Only reusable research methods and cross-product rules belong here.
