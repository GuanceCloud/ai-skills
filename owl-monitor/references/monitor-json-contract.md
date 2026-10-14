# Monitor JSON contract

## Import envelope

The import file is a JSON object whose only required top-level payload is:

```json
{"checkers": []}
```

Each array item is one trigger checker. Evidence belongs in a separate file.

## Required checker invariants

For a metric `simpleCheck` checker:

- `type` is `trigger` and `jsonScript.type` is `simpleCheck`.
- `is_disable` is `true` by default.
- `jsonScript.channels` and `alertPolicyNames` are empty by default.
- `jsonScript.targets` contains one DQL target for the ordinary single-value threshold pattern.
- `extend.querylist` contains the matching editable query representation.
- `jsonScript.targets[0].dql == extend.querylist[0].query.q`.
- `jsonScript.targets[0].alias == extend.querylist[0].query.code`.
- `jsonScript.groupBy == extend.querylist[0].query.groupBy`.
- `jsonScript.checkerOpt.rules == extend.rules`.
- `query.namespace` is `metric`; `query.dataSource`, `query.field`, and `query.fieldFunc` describe the DQL truthfully.
- Every rule condition aliases a declared target and uses numeric operands encoded as strings.
- The final DQL includes an explicit duration and passes both local and Owl validation.

## Minimal canonical shape

```json
{
  "checkers": [
    {
      "jsonScript": {
        "type": "simpleCheck",
        "every": "1m",
        "title": "资源 {{ resource_name }} 使用率过高",
        "groupBy": ["resource_name", "resource_id"],
        "message": ">等级：{{ df_status | to_status_human }}\n>当前值：{{ Result | to_fixed(2) }}%",
        "targets": [
          {
            "dql": "M::`real_source`:(last(`real_percent_field`) AS `Result`) [5m] BY `resource_name`, `resource_id`",
            "alias": "Result",
            "qtype": "dql"
          }
        ],
        "channels": [],
        "interval": 60,
        "atAccounts": [],
        "checkerOpt": {
          "rules": [
            {
              "status": "critical",
              "conditions": [
                {"alias": "Result", "operands": ["90"], "operator": ">="}
              ],
              "matchTimes": 5,
              "conditionLogic": "and"
            }
          ],
          "infoEvent": false,
          "openMatchTimes": true,
          "openOkConditions": false,
          "disableLargeScaleEventProtect": false
        },
        "noDataTitle": "",
        "noDataMessage": "",
        "atNoDataAccounts": [],
        "eventCharts": [],
        "eventChartEnable": false,
        "disableCheckEndTime": false,
        "recoverNeedPeriodCount": 3
      },
      "extend": {
        "rules": [
          {
            "status": "critical",
            "conditions": [
              {"alias": "Result", "operands": ["90"], "operator": ">="}
            ],
            "matchTimes": 5,
            "conditionLogic": "and"
          }
        ],
        "manager": [],
        "funcName": "",
        "querylist": [
          {
            "uuid": "stable-unique-uuid",
            "qtype": "dql",
            "query": {
              "q": "same final DQL as the target",
              "code": "Result",
              "fill": null,
              "type": "simple",
              "alias": "",
              "field": "real_percent_field",
              "fillNum": null,
              "filters": [],
              "groupBy": ["resource_name", "resource_id"],
              "labelOp": "",
              "funcList": [],
              "fieldFunc": "last",
              "fieldType": "float",
              "namespace": "metric",
              "dataSource": "real_source",
              "queryFuncs": [],
              "withLabels": [],
              "groupByTime": ""
            },
            "disabled": false,
            "datasource": "dataflux"
          }
        ],
        "issueLevelUUID": "",
        "needRecoverIssue": false,
        "isNeedCreateIssue": false,
        "issueDfStatus": []
      },
      "is_disable": true,
      "tagInfo": [],
      "secret": "",
      "type": "trigger",
      "monitorName": "监控器名称",
      "alertPolicyNames": []
    }
  ]
}
```

## Message quality

Include severity, stable identifying dimensions, current value and unit, recovery wording, and one concrete first-response action. Use only variables present in the query grouping or platform-provided event context.
