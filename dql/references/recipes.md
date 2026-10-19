# DQL Recipes

Curated AST recipes for common DQL query patterns. All examples validate via `./bin/dqlcheck --in ast` with
exact output shown in the `Builds` section. Replace placeholder sources, fields, and windows with real workspace values.

Compile recipes via:

```bash
./bin/dqlcheck --in ast -f /tmp/dql-query.json --out build --format json --pretty
```

> Version bound: see `SKILL.md`.

## Index (Partition) Configuration

`indices` configures the data partition / table. By default use `[{"namespace": "<M/L/T/O>", "index_name": ""}]`, where `""` represents the default partition.
To query across specific partitions, specify multiple index entries (e.g. `M("prod", "staging")::cpu`).

## Duration Syntax

`DurationExpr.duration` directly accepts human-readable duration strings (e.g. `"1s"`, `"10s"`, `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"6h"`, `"1d"`).

Numeric nanoseconds are also supported for backwards compatibility.

*Note for absolute timestamps:* When using absolute timestamps, use `TimeExpr` whose `time` field is **Unix milliseconds** (e.g. `1726800000000`).

## Pick a recipe

### 1. Metric Queries (`M::`)

| Your request looks like | Start from |
| --- | --- |
| Aggregated over a window, grouped by a dimension | [metric-windowed-avg](#metric-windowed-avg) |
| Prometheus-style Counter rate or rollup (`rate`, `last`, `max`) | [metric-rollup-rate](#metric-rollup-rate) |
| Tag filter plus a numeric threshold | [metric-filtered](#metric-filtered) |
| Absolute time window (fixed start and end timestamps) | [metric-absolute-window](#metric-absolute-window) |
| Paging inside each group (the second page of points, …) | [metric-paging](#metric-paging) |
| Ranking groups (top N / most frequent first) | [metric-topn](#metric-topn) |
| Filtering on an aggregate result (`HAVING`) | [metric-having](#metric-having) |
| Comparing with an earlier period (`SHIFT`) | [metric-shift](#metric-shift) |
| Raw metric points, to troubleshoot a series | [metric-raw-points](#metric-raw-points) |

### 2. Log, Event & Trace Queries (`L::`, `T::`, `O::`)

| Your request looks like | Start from |
| --- | --- |
| Listing raw rows (logs, events, traces) | [log-detail](#log-detail) |
| Querying across all sources when source name is unknown (`*`) | [log-wildcard-detail](#log-wildcard-detail) |
| Filtering by a set of values (`IN`) | [log-in-filter](#log-in-filter) |
| Combining filters with AND and OR logic | [log-complex-filter](#log-complex-filter) |
| Filtering on a field inside a JSON message | [log-json-field](#log-json-field) |
| Counting by a field | [log-count-by-field](#log-count-by-field) |
| The distinct values of a field | [log-distinct-values](#log-distinct-values) |
| Full-text search (`search()`) | [log-fulltext](#log-fulltext) |
| Paginating large list queries with a cursor | [log-cursor-paging](#log-cursor-paging) |

### 3. Multi-Query Math & Subqueries

| Your request looks like | Start from |
| --- | --- |
| Computing multi-metric ratios / arithmetic (Eval: $A/B \times 100$) | [metric-ratio-eval](#metric-ratio-eval) |
| Aggregating the result of another query | [subquery](#subquery) |
| Keeping only the rows another query lists | [where-subquery](#where-subquery) |

## metric-windowed-avg

### Metric: windowed average per host

**Ask**: Average CPU per host over the last hour, 5-minute points, restricted to two hosts, newest points first.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "M", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "cpu"}
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "avg_usage",
      "value": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [
          {
            "name": "",
            "value": {"type": "IdentExpr", "value": "usage_user"}
          }
        ]
      }
    }
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "host"},
      "op": "IN",
      "right": {
        "type": "ArrayExpr",
        "values": [
          {"type": "StringExpr", "value": "web-01"},
          {"type": "StringExpr", "value": "web-02"}
        ]
      }
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"},
    "step": {"type": "DurationExpr", "duration": "5m"}
  },
  "groups": [
    {"type": "IdentExpr", "value": "host"}
  ],
  "having": null,
  "order_by": [
    {
      "column": {"type": "IdentExpr", "value": "time"},
      "order": "DESC"
    }
  ],
  "limit": 100,
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`){ (`host` IN ["web-01", "web-02"]) }[1h0m0s::5m0s] BY (`host`) ORDER BY `time` DESC LIMIT 100 SLIMIT 100``

**Note**: `step` is what makes this a time series; drop it and the window collapses to a single point per group. `order_by` sorts inside a group, so `time` here means the points of each host, not the hosts.

## metric-rollup-rate

### Metric: Prometheus Counter rate preprocessing (Rollup)

**Ask**: Calculate per-second request rate (QPS) from cumulative `request_count` Counter per service over the last hour, 5-minute points.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "M", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "http_requests"}
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "qps",
      "value": {
        "type": "FunctionExpr",
        "name": "sum",
        "args": [{"name": "", "value": {"type": "IdentExpr", "value": "request_count"}}]
      }
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"},
    "step": {"type": "DurationExpr", "duration": "5m"},
    "rollup": "rate",
    "rollup_args": null
  },
  "groups": [{"type": "IdentExpr", "value": "service"}],
  "having": null,
  "slimit": 100
}
```

**Builds**:

``M::`http_requests`:(sum(`request_count`) AS `qps`)[1h0m0s::5m0s:rate] BY (`service`) SLIMIT 100``

**Note**: For Prometheus cumulative Counter metrics, compute per-series `rate` before aggregating across dimensions (`[1h::5m:rate]`). Common rollups include `rate`, `last`, `min`, `max`, `avg`, `sum`.

## metric-filtered

### Metric: tag filter plus a numeric threshold

**Ask**: Average CPU per host for one host, keeping only samples above 50.

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "M",
      "index_name": ""
    }
  ],
  "sources": [
    {
      "type": "IdentExpr",
      "value": "cpu"
    }
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "avg_usage",
      "value": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [
          {
            "name": "",
            "value": {
              "type": "IdentExpr",
              "value": "usage_user"
            }
          }
        ]
      }
    }
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {
        "type": "IdentExpr",
        "value": "host"
      },
      "op": "=",
      "right": {
        "type": "StringExpr",
        "value": "web-01"
      }
    },
    {
      "type": "BinaryExpr",
      "left": {
        "type": "IdentExpr",
        "value": "usage_user"
      },
      "op": ">",
      "right": {
        "type": "Int64Expr",
        "value": 50
      }
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {
      "type": "DurationExpr",
      "duration": "1h"
    },
    "step": {
      "type": "DurationExpr",
      "duration": "5m"
    }
  },
  "groups": [
    {
      "type": "IdentExpr",
      "value": "host"
    }
  ],
  "having": null,
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`){ (`host` = "web-01") , (`usage_user` > 50) }[1h0m0s::5m0s] BY (`host`) SLIMIT 100``

**Note**: A tag filter and a numeric threshold are the same node — `BinaryExpr` — and only the right-hand value differs: `StringExpr` for a tag, `Int64Expr` for a number. Both are listed as separate `wheres` entries.

## metric-absolute-window

### Metric: absolute time window (fixed start and end timestamps)

**Ask**: Average CPU per host between Unix timestamp 1726800000000 and 1726803600000, 5-minute points.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "M", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "cpu"}
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "avg_usage",
      "value": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [{"name": "", "value": {"type": "IdentExpr", "value": "usage_user"}}]
      }
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {"type": "TimeExpr", "time": 1726800000000},
    "to": {"type": "TimeExpr", "time": 1726803600000},
    "step": {"type": "DurationExpr", "duration": "5m"}
  },
  "groups": [{"type": "IdentExpr", "value": "host"}],
  "having": null,
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[1726800000000000000:1726803600000000000:5m0s] BY (`host`) SLIMIT 100``

**Note**: Absolute time windows use `TimeExpr` for `from` and `to`. The `time` field in AST JSON accepts **Unix milliseconds**, and `dqlcheck` automatically builds the nanosecond timestamp literal.

## metric-ratio-eval

### Metric: multi-query ratio / arithmetic (Eval)

**Ask**: Calculate error rate percentage (`sum(error_count) / sum(req_count) * 100`) per service over the last hour.

```json
{
  "type": "SelectExpr",
  "indices": [{"namespace": "M", "index_name": ""}],
  "sources": [
    {
      "type": "SelectExpr",
      "indices": [{"namespace": "M", "index_name": ""}],
      "sources": [{"type": "IdentExpr", "value": "http"}],
      "projections": [
        {
          "type": "AliasExpr",
          "name": "errors",
          "value": {
            "type": "FunctionExpr",
            "name": "sum",
            "args": [{"name": "", "value": {"type": "IdentExpr", "value": "error_count"}}]
          }
        }
      ],
      "wheres": null,
      "window": {
        "type": "TimeWindow",
        "from": {"type": "DurationExpr", "duration": "1h"},
        "step": {"type": "DurationExpr", "duration": "5m"}
      },
      "having": null,
      "groups": [{"type": "IdentExpr", "value": "service"}],
      "slimit": 100
    },
    {
      "type": "SelectExpr",
      "indices": [{"namespace": "M", "index_name": ""}],
      "sources": [{"type": "IdentExpr", "value": "http"}],
      "projections": [
        {
          "type": "AliasExpr",
          "name": "total",
          "value": {
            "type": "FunctionExpr",
            "name": "sum",
            "args": [{"name": "", "value": {"type": "IdentExpr", "value": "req_count"}}]
          }
        }
      ],
      "wheres": null,
      "window": {
        "type": "TimeWindow",
        "from": {"type": "DurationExpr", "duration": "1h"},
        "step": {"type": "DurationExpr", "duration": "5m"}
      },
      "having": null,
      "groups": [{"type": "IdentExpr", "value": "service"}],
      "slimit": 100
    }
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "error_rate_pct",
      "value": {
        "type": "BinaryExpr",
        "left": {
          "type": "BinaryExpr",
          "left": {"type": "IdentExpr", "value": "errors"},
          "op": "/",
          "right": {"type": "IdentExpr", "value": "total"}
        },
        "op": "*",
        "right": {"type": "Int64Expr", "value": 100}
      }
    }
  ],
  "wheres": null,
  "having": null,
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"},
    "step": {"type": "DurationExpr", "duration": "5m"}
  },
  "limit": 100
}
```

**Builds**:

``M::(M::`http`:(sum(`error_count`) AS `errors`)[1h0m0s::5m0s] BY (`service`) SLIMIT 100), (M::`http`:(sum(`req_count`) AS `total`)[1h0m0s::5m0s] BY (`service`) SLIMIT 100):(((`errors` / `total`) * 100) AS `error_rate_pct`)[1h0m0s::5m0s] LIMIT 100``

**Note**: Multi-query arithmetic (formerly written as outer `eval(...)`) is expressed in AST by nesting named subqueries in `sources` and computing the arithmetic in top-level `projections`.

## metric-paging

### Metric: paging inside each group

**Ask**: Per host, the second page of the newest 5-minute peaks: skip the two most recent points, then take three.

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "M",
      "index_name": ""
    }
  ],
  "sources": [
    {
      "type": "IdentExpr",
      "value": "cpu"
    }
  ],
  "projections": [
    {
      "type": "FunctionExpr",
      "name": "max",
      "args": [
        {
          "name": "",
          "value": {
            "type": "IdentExpr",
            "value": "usage_user"
          }
        }
      ]
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {
      "type": "DurationExpr",
      "duration": "1h"
    },
    "step": {
      "type": "DurationExpr",
      "duration": "10m"
    }
  },
  "groups": [
    {
      "type": "IdentExpr",
      "value": "host"
    }
  ],
  "having": null,
  "order_by": [
    {
      "column": {
        "type": "IdentExpr",
        "value": "time"
      },
      "order": "DESC"
    }
  ],
  "limit": 3,
  "offset": 2,
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(max(`usage_user`))[1h0m0s::10m0s] BY (`host`) ORDER BY `time` DESC LIMIT 3 OFFSET 2 SLIMIT 100``

**Note**: `offset` is a sibling of `limit` on the `SelectExpr`, applied after `order_by`, and it skips rows **inside every group** — here each host returns points 3 to 5, newest first. Paging groups instead of rows is `slimit` / `soffset`.

## metric-topn

### Metric: TopN across groups

**Ask**: Top 10 hosts by average CPU over the last hour.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "M", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "cpu"}
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "avg_usage",
      "value": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [
          {
            "name": "",
            "value": {"type": "IdentExpr", "value": "usage_user"}
          }
        ]
      }
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"},
    "step": {"type": "DurationExpr", "duration": "1h"}
  },
  "groups": [
    {"type": "IdentExpr", "value": "host"}
  ],
  "having": null,
  "sorder_by": {
    "value": {"type": "IdentExpr", "value": "avg_usage"},
    "order": "DESC"
  },
  "slimit": 10
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[1h0m0s::1h0m0s] BY (`host`) SORDER BY `avg_usage` DESC SLIMIT 10``

**Note**: Ranking groups is `sorder_by` + `slimit`, not `order_by` + `limit`. The sort key is the projection alias; for an unaliased aggregate, repeat the aggregate expression itself.

## metric-having

### Metric: several aggregates with HAVING

**Ask**: Per host: average, max and count, keeping only groups whose average exceeds 60.

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "M",
      "index_name": ""
    }
  ],
  "sources": [
    {
      "type": "IdentExpr",
      "value": "cpu"
    }
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "avg_usage",
      "value": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [
          {
            "name": "",
            "value": {
              "type": "IdentExpr",
              "value": "usage_user"
            }
          }
        ]
      }
    },
    {
      "type": "AliasExpr",
      "name": "max_usage",
      "value": {
        "type": "FunctionExpr",
        "name": "max",
        "args": [
          {
            "name": "",
            "value": {
              "type": "IdentExpr",
              "value": "usage_user"
            }
          }
        ]
      }
    },
    {
      "type": "AliasExpr",
      "name": "n",
      "value": {
        "type": "FunctionExpr",
        "name": "count",
        "args": [
          {
            "name": "",
            "value": {
              "type": "IdentExpr",
              "value": "usage_user"
            }
          }
        ]
      }
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {
      "type": "DurationExpr",
      "duration": "1h"
    },
    "step": {
      "type": "DurationExpr",
      "duration": "1h"
    }
  },
  "groups": [
    {
      "type": "IdentExpr",
      "value": "host"
    }
  ],
  "having": [
    {
      "type": "BinaryExpr",
      "left": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [
          {
            "name": "",
            "value": {
              "type": "IdentExpr",
              "value": "usage_user"
            }
          }
        ]
      },
      "op": ">",
      "right": {
        "type": "Int64Expr",
        "value": 60
      }
    }
  ],
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`, max(`usage_user`) AS `max_usage`, count(`usage_user`) AS `n`)[1h0m0s::1h0m0s] BY (`host`) HAVING ((avg(`usage_user`) > 60))  SLIMIT 100``

**Note**: `having` is a list of `BinaryExpr` like `wheres`, but it filters groups after aggregation instead of rows before it. Either repeat the aggregate expression, as here, or use the projection alias — the alias form builds to `HAVING ((\`n\` > 1000))`. On a metric source `count(*)` is a bind error, so name a field.

## metric-shift

### Metric: compare with the previous day (SHIFT)

**Ask**: Average CPU per host now, shifted back one day for a period-over-period comparison.

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "M",
      "index_name": ""
    }
  ],
  "sources": [
    {
      "type": "IdentExpr",
      "value": "cpu"
    }
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "avg_usage",
      "value": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [
          {
            "name": "",
            "value": {
              "type": "IdentExpr",
              "value": "usage_user"
            }
          }
        ]
      }
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {
      "type": "DurationExpr",
      "duration": "1h"
    },
    "step": {
      "type": "DurationExpr",
      "duration": "1h"
    }
  },
  "groups": [
    {
      "type": "IdentExpr",
      "value": "host"
    }
  ],
  "having": null,
  "shift": {
    "type": "DurationExpr",
    "duration": "1d"
  },
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[1h0m0s::1h0m0s] SHIFT 24h0m0s BY (`host`) SLIMIT 100``

**Note**: `shift` is a `DurationExpr` on the `SelectExpr`, beside `window`. Human-readable strings such as `"1d"` or `"24h"` are preferred.

## subquery

### Subquery: aggregate a subquery

**Ask**: Average of the per-host 5-minute averages — the inner query is the data source of the outer one.

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "M",
      "index_name": ""
    }
  ],
  "sources": [
    {
      "type": "SelectExpr",
      "indices": [
        {
          "namespace": "M",
          "index_name": ""
        }
      ],
      "sources": [
        {
          "type": "IdentExpr",
          "value": "cpu"
        }
      ],
      "projections": [
        {
          "type": "AliasExpr",
          "name": "avg_usage",
          "value": {
            "type": "FunctionExpr",
            "name": "avg",
            "args": [
              {
                "name": "",
                "value": {
                  "type": "IdentExpr",
                  "value": "usage_user"
                }
              }
            ]
          }
        }
      ],
      "wheres": null,
      "window": {
        "type": "TimeWindow",
        "from": {
          "type": "DurationExpr",
          "duration": "1h"
        },
        "step": {
          "type": "DurationExpr",
          "duration": "5m"
        }
      },
      "groups": [
        {
          "type": "IdentExpr",
          "value": "host"
        }
      ],
      "having": null
    }
  ],
  "projections": [
    {
      "type": "AliasExpr",
      "name": "avg_of_avg",
      "value": {
        "type": "FunctionExpr",
        "name": "avg",
        "args": [
          {
            "name": "",
            "value": {
              "type": "IdentExpr",
              "value": "avg_usage"
            }
          }
        ]
      }
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {
      "type": "DurationExpr",
      "duration": "1h"
    },
    "step": {
      "type": "DurationExpr",
      "duration": "1h"
    }
  },
  "groups": [
    {
      "type": "IdentExpr",
      "value": "host"
    }
  ],
  "having": null,
  "slimit": 100
}
```

**Builds**:

``M::(M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[1h0m0s::5m0s] BY (`host`)):(avg(`avg_usage`) AS `avg_of_avg`)[1h0m0s::1h0m0s] BY (`host`) SLIMIT 100``

**Note**: A nested `SelectExpr` inside `sources` is the subquery. It carries its own `indices` and `window`, and the outer query reads its columns by name (`avg_usage`), so the inner projections must be aliased.

## where-subquery

### Subquery: keep only the rows another query lists

**Ask**: Average CPU per host, but only for hosts whose provider is cloud-a — the host list comes from a query against object data, not from a fixed list.

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "M",
      "index_name": ""
    }
  ],
  "sources": [
    {
      "type": "IdentExpr",
      "value": "cpu"
    },
    {
      "type": "SelectExpr",
      "indices": [
        {
          "namespace": "O",
          "index_name": ""
        }
      ],
      "sources": [
        {
          "type": "IdentExpr",
          "value": "HOST"
        }
      ],
      "projections": [
        {
          "type": "AliasExpr",
          "name": "@__sub_cloud_a",
          "value": {
            "type": "FunctionExpr",
            "name": "collect_distinct",
            "args": [
              {
                "name": "",
                "value": {
                  "type": "IdentExpr",
                  "value": "hostname"
                }
              },
              {
                "name": "",
                "value": {
                  "type": "Int64Expr",
                  "value": 5000
                }
              }
            ]
          }
        }
      ],
      "wheres": [
        {
          "type": "BinaryExpr",
          "left": {
            "type": "IdentExpr",
            "value": "provider"
          },
          "op": "=",
          "right": {
            "type": "StringExpr",
            "value": "cloud-a"
          }
        }
      ],
      "window": {
        "type": "TimeWindow",
        "from": {
          "type": "DurationExpr",
          "duration": "1h"
        }
      },
      "groups": null,
      "having": null
    }
  ],
  "projections": [
    {
      "type": "FunctionExpr",
      "name": "avg",
      "args": [
        {
          "name": "",
          "value": {
            "type": "IdentExpr",
            "value": "usage_user"
          }
        }
      ]
    }
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {
        "type": "IdentExpr",
        "value": "host"
      },
      "op": "IN",
      "right": {
        "type": "IdentExpr",
        "value": "@__sub_cloud_a"
      }
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {
      "type": "DurationExpr",
      "duration": "1h"
    }
  },
  "groups": [
    {
      "type": "IdentExpr",
      "value": "host"
    }
  ],
  "having": null,
  "slimit": 100
}
```

**Builds**:

``M::`cpu`, (O::`HOST`:(collect_distinct(`hostname`, 5000) AS `@__sub_cloud_a`){ (`provider` = "cloud-a") }[1h0m0s::]):(avg(`usage_user`)){ (`host` IN `@__sub_cloud_a`) }[1h0m0s::] BY (`host`) SLIMIT 100``

**Note**: The subquery is a **second entry in `sources`**, beside the main source — it is not a node inside `wheres`. Its projection is one aliased value list (`collect_distinct(field, cap)`), and `wheres` compares the outer field to that alias name with `IN` (or `NOT IN`); the alias name is yours to choose. Note the namespace switch: the subquery reads `O`, the outer query reads `M`.

## log-detail

### Log: detail list

**Ask**: Recent nginx log lines with status >= 400, newest first.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "nginx"}
  ],
  "projections": [
    {"type": "IdentExpr", "value": "time"},
    {"type": "IdentExpr", "value": "status"},
    {"type": "IdentExpr", "value": "message"}
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "status"},
      "op": ">=",
      "right": {"type": "Int64Expr", "value": 400}
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"}
  },
  "groups": null,
  "having": null,
  "order_by": [
    {
      "column": {"type": "IdentExpr", "value": "time"},
      "order": "DESC"
    }
  ],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `status`, `message`){ (`status` >= 400) }[1h0m0s::] ORDER BY `time` DESC LIMIT 100``

**Note**: A detail query has no aggregate and no `groups`, but it still needs a window. Its `projections` is a plain list of `IdentExpr`; include `time` when the user needs to see when each row happened.

## log-wildcard-detail

### Log: query across all sources (wildcard fallback)

**Ask**: Recent log lines across all sources when the exact source name is unknown.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "WildcardExpr"}
  ],
  "projections": [
    {"type": "WildcardExpr"}
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "15m"}
  },
  "groups": null,
  "having": null,
  "order_by": [
    {"column": {"type": "IdentExpr", "value": "time"}, "order": "DESC"}
  ],
  "limit": 100
}
```

**Builds**:

``L::*:(*)[15m0s::] ORDER BY `time` DESC LIMIT 100``

**Note**: A wildcard source (`WildcardExpr`) reads all sources in the index. Use it as a fallback when the source name is unknown, and replace it with a named source once discovered via `show_logging_source()`.

## log-in-filter

### Log: multi-value filter

**Ask**: Lines from a set of services.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "nginx"}
  ],
  "projections": [
    {"type": "IdentExpr", "value": "time"},
    {"type": "IdentExpr", "value": "service"},
    {"type": "IdentExpr", "value": "message"}
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "service"},
      "op": "IN",
      "right": {
        "type": "ArrayExpr",
        "values": [
          {"type": "StringExpr", "value": "api"},
          {"type": "StringExpr", "value": "auth"}
        ]
      }
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"}
  },
  "groups": null,
  "having": null,
  "order_by": [
    {
      "column": {"type": "IdentExpr", "value": "time"},
      "order": "DESC"
    }
  ],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `service`, `message`){ (`service` IN ["api", "auth"]) }[1h0m0s::] ORDER BY `time` DESC LIMIT 100``

**Note**: A set of values is `IN` with an `ArrayExpr` on the right; the same node with `op` set to `NOT IN` excludes the set instead. Each element is a full value node — `StringExpr`, `Int64Expr`, and so on — one per element.

## log-complex-filter

### Log: combining filters with AND and OR logic

**Ask**: Find nginx logs where status is 500 or 400, AND service is 'order'.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "nginx"}
  ],
  "projections": [{"type": "WildcardExpr"}],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {
        "type": "BinaryExpr",
        "left": {"type": "IdentExpr", "value": "status"},
        "op": ">=",
        "right": {"type": "Int64Expr", "value": 500}
      },
      "op": "OR",
      "right": {
        "type": "BinaryExpr",
        "left": {"type": "IdentExpr", "value": "status"},
        "op": "=",
        "right": {"type": "Int64Expr", "value": 400}
      }
    },
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "service"},
      "op": "=",
      "right": {"type": "StringExpr", "value": "order"}
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "15m"},
    "step": null
  },
  "groups": null,
  "having": null,
  "order_by": null,
  "limit": 100,
  "offset": null,
  "sorder_by": null,
  "slimit": null,
  "soffset": null
}
```

**Builds**:

``L::`nginx`:(*){ ((`status` >= 500) OR (`status` = 400)) , (`service` = "order") }[15m0s::] LIMIT 100``

**Note**: `wheres` elements are joined by `AND`. To nest an `OR`, nest two `BinaryExpr` nodes under a parent `BinaryExpr` with `"op": "OR"`.

## log-json-field

### Log: filter on a field inside a JSON message

**Ask**: nginx lines whose JSON body reports a failure, showing the request path and the status it reported.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "nginx"}
  ],
  "projections": [
    {"type": "IdentExpr", "value": "time"},
    {"type": "IdentExpr", "value": "message@request.path"},
    {"type": "IdentExpr", "value": "message@response.status"}
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "message@response.status"},
      "op": ">=",
      "right": {"type": "Int64Expr", "value": 400}
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"}
  },
  "groups": null,
  "having": null,
  "order_by": [
    {
      "column": {"type": "IdentExpr", "value": "time"},
      "order": "DESC"
    }
  ],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `message@request.path`, `message@response.status`){ (`message@response.status` >= 400) }[1h0m0s::] ORDER BY `time` DESC LIMIT 100``

**Note**: There is no node for JSON extraction — `message@response.status` is the entire `IdentExpr` value, and it is used in `wheres` and `groups` exactly like any other field name. The path subset is `.key`, `["key"]` when the key holds spaces or punctuation, and `[index]` for an array position.

## log-count-by-field

### Log: count by field, most frequent first

**Ask**: Count 5xx entries per status code over the last hour, highest count first.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "nginx"}
  ],
  "projections": [
    {
      "type": "FunctionExpr",
      "name": "count",
      "args": [
        {
          "name": "",
          "value": {"type": "WildcardExpr"}
        }
      ]
    }
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "status"},
      "op": ">=",
      "right": {"type": "Int64Expr", "value": 500}
    },
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "status"},
      "op": "<",
      "right": {"type": "Int64Expr", "value": 600}
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"},
    "step": {"type": "DurationExpr", "duration": "1h"}
  },
  "groups": [
    {"type": "IdentExpr", "value": "status"}
  ],
  "having": null,
  "sorder_by": {
    "value": {
      "type": "FunctionExpr",
      "name": "count",
      "args": [
        {
          "name": "",
          "value": {"type": "WildcardExpr"}
        }
      ]
    },
    "order": "DESC"
  },
  "slimit": 100
}
```

**Builds**:

``L::`nginx`:(count(*)){ (`status` >= 500) , (`status` < 600) }[1h0m0s::1h0m0s] BY (`status`) SORDER BY count(*) DESC SLIMIT 100``

**Note**: There is no `BETWEEN`: a 5xx range is two `wheres` entries, `>= 500` and `< 600`. The projection is unaliased, so `sorder_by` repeats the aggregate expression — `WildcardExpr` and all.

## log-distinct-values

### Log: the distinct values of a field

**Ask**: Which status codes each service has returned in the last hour.

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "L",
      "index_name": ""
    }
  ],
  "sources": [
    {
      "type": "IdentExpr",
      "value": "nginx"
    }
  ],
  "projections": [
    {
      "type": "FunctionExpr",
      "name": "distinct",
      "args": [
        {
          "name": "",
          "value": {
            "type": "IdentExpr",
            "value": "status"
          }
        }
      ]
    }
  ],
  "wheres": null,
  "window": {
    "type": "TimeWindow",
    "from": {
      "type": "DurationExpr",
      "duration": "1h"
    }
  },
  "groups": [
    {
      "type": "IdentExpr",
      "value": "service"
    }
  ],
  "having": null,
  "limit": 100,
  "slimit": 100
}
```

**Builds**:

``L::`nginx`:(distinct(`status`))[1h0m0s::] BY (`service`) LIMIT 100 SLIMIT 100``

**Note**: `distinct(x)` returns **one row per distinct value**, so `limit` bounds how many values come back — there is no array to cap. With `BY` you get the group key plus one row per value inside it, which is why `limit` counts rows per group here. For a single array value per group instead of rows, see `collect_distinct` in `function-matrix.md`.

## log-fulltext

### Log: full-text search

**Ask**: nginx lines whose message contains the phrase "connection timeout".

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "nginx"}
  ],
  "projections": [
    {"type": "IdentExpr", "value": "time"},
    {"type": "IdentExpr", "value": "message"}
  ],
  "wheres": [
    {
      "type": "FunctionExpr",
      "name": "search",
      "args": [
        {
          "name": "",
          "value": {"type": "IdentExpr", "value": "message"}
        },
        {
          "name": "",
          "value": {"type": "StringExpr", "value": "connection timeout"}
        }
      ]
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"}
  },
  "groups": null,
  "having": null,
  "order_by": [
    {
      "column": {"type": "IdentExpr", "value": "time"},
      "order": "DESC"
    }
  ],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `message`){ search(`message`, "connection timeout") }[1h0m0s::] ORDER BY `time` DESC LIMIT 100``

**Note**: Full-text search is a `FunctionExpr` in `wheres`, not a `BinaryExpr` — the field is the first argument and the phrase the second. The field argument is optional: `search("connection timeout")` builds as written.

## log-cursor-paging

### Log: cursor-based pagination

**Ask**: Fetch the next page of Nginx logs after a specific timestamp, avoiding O(N) offset scanning.

```json
{
  "type": "SelectExpr",
  "indices": [
    {"namespace": "L", "index_name": ""}
  ],
  "sources": [
    {"type": "IdentExpr", "value": "nginx"}
  ],
  "projections": [
    {"type": "WildcardExpr"}
  ],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "time"},
      "op": "<",
      "right": {"type": "TimeExpr", "time": 1727000000000}
    }
  ],
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"}
  },
  "groups": null,
  "having": null,
  "order_by": [
    {"column": {"type": "IdentExpr", "value": "time"}, "order": "desc"}
  ],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(*){ (`time` < 1727000000000000000) }[1h0m0s::] ORDER BY `time` desc LIMIT 100``

**Note**: For high-volume log and trace list pagination, avoid `OFFSET 10000`. Use cursor pagination by passing the `time` timestamp from the last record of the previous page into a `{ time < <last_time> }` filter with `ORDER BY time DESC`. This achieves O(1) seek performance.

## metric-raw-points

### Metric: raw stored points, for troubleshooting

**Ask**: What did this metric actually report for one host over the last hour — raw points, newest first, not an average.

```json
{
  "type": "SelectExpr",
  "indices": [{"namespace": "M", "index_name": ""}],
  "sources": [{"type": "IdentExpr", "value": "cpu"}],
  "projections": [{"type": "IdentExpr", "value": "usage_user"}],
  "wheres": [
    {
      "type": "BinaryExpr",
      "left": {"type": "IdentExpr", "value": "host"},
      "op": "=",
      "right": {"type": "StringExpr", "value": "web-01"}
    }
  ],
  "groups": null,
  "having": null,
  "order_by": [{"column": {"type": "IdentExpr", "value": "time"}, "order": "desc"}],
  "limit": 100,
  "window": {
    "type": "TimeWindow",
    "from": {"type": "DurationExpr", "duration": "1h"}
  }
}
```

**Builds**:

``M::`cpu`:(`usage_user`){ (`host` = "web-01") }[1h0m0s::] ORDER BY `time` desc LIMIT 100``

**Note**: No aggregate and no `BY` means the raw stored points, which is the right shape for a gap, a spike, or a value that looks wrong. `LIMIT` is mandatory — without it the query returns every point in the range. The `ORDER BY` is optional (the server orders by time), and written out here because newest-first is the point of the query. See `metrics.md` for the other metric shapes.

## Global Query Invariants

1. **Time window required**: Every runnable query requires an explicit `window` (`DurationExpr` or `TimeExpr`).
2. **Result bounding**: Include `LIMIT` for row counts and `SLIMIT` for group counts to prevent driver memory overflow.
3. **Validation**: Validate built output with `dqlcheck` before delivery. Note that `--format json` escapes `<`, `>`, and `&` in the `build` string.
