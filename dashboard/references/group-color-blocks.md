# Custom Group Color Blocks

Read this reference when generating or repairing Guance Dashboard group-header colors.

## JSON contract

A portable custom group color uses a solid hexadecimal value:

```json
{
  "name": "Overview",
  "extend": {
    "bgColor": "#60A5FA",
    "isExpanded": true
  }
}
```

Rules:

- serialize portable import colors as uppercase `#RRGGBB`
- choose a lighter solid hue instead of pre-applying RGBA transparency
- keep `isExpanded` consistent with `dashboardExtend.groupUnfoldStatus[group.name]`
- omit `colorKey` when `bgColor` is custom; do not combine the built-in and custom color domains
- assign colors by operational meaning, not solely by array position
- use one color consistently for groups with the same meaning across related dashboards
- do not use pink, magenta, fuchsia, or rose hues in the group-header palette

The editor may normalize a saved group color to `rgba(...)` in a round-trip export. That saved representation is not necessarily portable on re-import: observed imports can render RGBA group headers without a visible color block. Keep the solid HEX form in generated import artifacts unless an imported-and-rendered test proves another form in the target workspace.

## Recommended 10-color operations palette

| Operational role | Color | Recommended use |
|---|---|---|
| Overview | `#60A5FA` | Executive or service-wide overview |
| Compute | `#38BDF8` | CPU, compute, scheduling |
| Inventory | `#94A3B8` | Resource lists and metadata |
| Healthy capacity | `#4ADE80` | Capacity, availability, healthy utilization |
| Pressure | `#FBBF24` | CPU/memory pressure and warning states |
| Network and I/O | `#22D3EE` | Network, disk, throughput |
| Dependency | `#818CF8` | Workloads, services, dependencies |
| Risk | `#F87171` | SRE risk, failures, urgent hotspots |
| Change | `#FB923C` | Deployments, restarts, configuration changes |
| Runtime | `#2DD4BF` | Runtime, containers, processes |

Use only as many colors as the Dashboard has groups. For example, two related Kubernetes dashboards should map Overview, Inventory, Network/I/O, and Risk to the same colors even if their remaining group names differ.

## Validation

For every group:

1. `bgColor` matches `^#[0-9A-F]{6}$`, comes from the light operations palette, and is not pink or magenta.
2. `isExpanded` is boolean and agrees with `groupUnfoldStatus`.
3. `colorKey` is absent in custom-color mode.
4. The same operational role does not change color across sibling dashboards without an explicit user preference.
5. A portable import artifact contains no `rgba(...)` group color unless that exact form has passed an import-and-render test in the target workspace.
