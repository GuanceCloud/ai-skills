# CloudWatch PromQL Mapping

`cloudwatch_metric_<service>{...}`  PromQL convert。

Notes：

- `service`: `cloudwatch_metric_`
- `namespace`: Grafana CloudWatch  AWS namespace
- `measurement`:  `M`
- `dimension`:  `Dimensions`
- `source_label`: Grafana CloudWatch query
- `variable_name`:  `source_label`，Output
- `statistic`: metrics， `Average`
- `alias_token`: CloudWatch convertUse token，

| service | namespace | measurement | dimension | source_label | variable_name | statistic | alias_token |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elb | AWS/ApplicationELB | aws_AWS/ApplicationELB | LoadBalancer | instance_name | load_balancer_name | Average | LoadBalancer |
| rds | AWS/RDS | aws_AWS/RDS | DBInstanceIdentifier | instance_name | rds_instance | Average | DBInstanceIdentifier |
| dynamo_db | AWS/DynamoDB | aws_AWS/DynamoDB | TableName | instance_name | dynamodb_instance | Average | TableName |
| redis | AWS/ElastiCache | aws_AWS/ElastiCache | CacheClusterId | instance_name | redis_instance | Average | CacheClusterId |
| es | AWS/ES | aws_AWS/ES | DomainName | instance_name | es_instance | Average | DomainName |
| kafka | AWS/Kafka | aws_AWS/Kafka | Cluster Name | instance_name | kafka_instance | Average | Cluster Name |
| sqs | AWS/SQS | aws_AWS/SQS | QueueName | instance_name | kafka_instance | Average | QueueName |
