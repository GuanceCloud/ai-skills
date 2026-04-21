# CloudWatch PromQL Mapping

编辑下面这张表就能新增或修改 `cloudwatch_metric_<service>{...}` 到观测云 PromQL 的转换规则。

字段说明：

- `service`: `cloudwatch_metric_` 后面的服务名
- `namespace`: Grafana CloudWatch 插件里的 AWS namespace
- `measurement`: 观测云 `M` 标签值
- `dimension`: 观测云 `Dimensions` 标签值
- `source_label`: Grafana CloudWatch 查询里代表实例维度的标签名
- `variable_name`: 如果命中了 `source_label`，输出时改写成的观测云变量名
- `statistic`: 指标后缀，默认可填 `Average`
- `alias_token`: CloudWatch 转换后建议使用的别名 token，默认可填目标维度名

| service | namespace | measurement | dimension | source_label | variable_name | statistic | alias_token |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elb | AWS/ApplicationELB | aws_AWS/ApplicationELB | LoadBalancer | instance_name | load_balancer_name | Average | LoadBalancer |
| rds | AWS/RDS | aws_AWS/RDS | DBInstanceIdentifier | instance_name | rds_instance | Average | DBInstanceIdentifier |
| dynamo_db | AWS/DynamoDB | aws_AWS/DynamoDB | TableName | instance_name | dynamodb_instance | Average | TableName |
| redis | AWS/ElastiCache | aws_AWS/ElastiCache | CacheClusterId | instance_name | redis_instance | Average | CacheClusterId |
| es | AWS/ES | aws_AWS/ES | DomainName | instance_name | es_instance | Average | DomainName |
| kafka | AWS/Kafka | aws_AWS/Kafka | Cluster Name | instance_name | kafka_instance | Average | Cluster Name |
| sqs | AWS/SQS | aws_AWS/SQS | QueueName | instance_name | kafka_instance | Average | QueueName |
