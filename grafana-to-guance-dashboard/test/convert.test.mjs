import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { convertDashboard } from '../scripts/convert-grafana-dashboard-core.js';

const TEST_DIRECTORY = path.dirname(new URL(import.meta.url).pathname);
const SKILL_ROOT = path.resolve(TEST_DIRECTORY, '..');
const FIXTURE_INPUT = path.join(SKILL_ROOT, 'fixtures', 'grafana-dashboard.json');
const FIXTURE_DASHBOARD = JSON.parse(fs.readFileSync(FIXTURE_INPUT, 'utf8'));
const GUANCE_ALL_CHARTS_INPUT = path.join(SKILL_ROOT, 'test', 'guance-all-charts.json');

test('standalone converter produces schema-valid dashboard output', () => {
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'grafana-to-guance-skill-'));
  const outputPath = path.join(tempDirectory, 'dashboard.guance.json');

  execFileSync(
    process.execPath,
    ['scripts/convert-grafana-dashboard.mjs', '--input', FIXTURE_INPUT, '--output', outputPath, '--validate'],
    {
      cwd: SKILL_ROOT,
      stdio: 'pipe',
    }
  );

  const output = JSON.parse(fs.readFileSync(outputPath, 'utf8'));
  assert.equal(output.title, FIXTURE_DASHBOARD.title);
  assert.equal(output.main.type, 'template');
  assert.ok(Array.isArray(output.main.charts));
  assert.ok(output.main.charts.length > 0);
});

test('standalone validator accepts generated dashboard output', () => {
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'grafana-to-guance-skill-'));
  const outputPath = path.join(tempDirectory, 'dashboard.guance.json');

  execFileSync(
    process.execPath,
    ['scripts/convert-grafana-dashboard.mjs', '--input', FIXTURE_INPUT, '--output', outputPath],
    {
      cwd: SKILL_ROOT,
      stdio: 'pipe',
    }
  );

  execFileSync(
    process.execPath,
    ['scripts/validate-file.mjs', outputPath],
    {
      cwd: SKILL_ROOT,
      stdio: 'pipe',
    }
  );
});

test('converter skips datasource vars and drops job filters by default', () => {
  const output = convertDashboard(createPrometheusDashboardFixture());

  assert.deepEqual(
    output.main.vars.map((item) => item.code),
    ['instance']
  );
  assert.deepEqual(
    output.main.vars.map((item) => item.type),
    ['PROMQL_QUERY']
  );
  assert.equal(output.main.vars[0].definition.value, 'label_values(up, instance)');
  assert.equal(
    output.main.charts[0].queries[0].query.q,
    'sum(rate(http_requests_total{instance=~"#{instance}"}[5m]))'
  );
});

test('converter keeps job vars and filters when explicitly enabled', () => {
  const output = convertDashboard(createPrometheusDashboardFixture(), { keepJobVariable: true });

  assert.deepEqual(
    output.main.vars.map((item) => item.code),
    ['job', 'instance']
  );
  assert.deepEqual(
    output.main.vars.map((item) => item.type),
    ['PROMQL_QUERY', 'PROMQL_QUERY']
  );
  assert.equal(output.main.vars[0].definition.value, 'label_values(up, job)');
  assert.equal(output.main.vars[1].definition.value, 'label_values(up{job=~"#{job}"}, instance)');
  assert.equal(
    output.main.charts[0].queries[0].query.q,
    'sum(rate(http_requests_total{job=~"#{job}",instance=~"#{instance}"}[5m]))'
  );
});

test('converter maps mysql query variables to outer datasource vars', () => {
  const output = convertDashboard({
    title: 'MySQL Variable',
    templating: {
      list: [
        {
          type: 'query',
          name: 'coin-copy-trade-standard-host',
          label: 'coin-copy-trade-standard-host',
          datasource: { type: 'mysql', uid: 'mysql-1' },
          query: "select f_server_name  from t_app_detail where f_app_name = 'coin-copy-trade-standard'",
          multi: true,
          includeAll: true,
          current: {
            text: '',
            value: '',
          },
        },
      ],
    },
    panels: [],
  });

  assert.deepEqual(output.main.vars, [
    {
      name: 'coin-copy-trade-standard-host',
      seq: 0,
      datasource: 'outer_datasource',
      code: 'coin-copy-trade-standard-host',
      type: 'OUTER_DATASOURCE',
      definition: {
        tag: '',
        field: '',
        value: "select f_server_name  from t_app_detail where f_app_name = 'coin-copy-trade-standard'",
        metric: 'DFF672F02CAD7D94CA1ABA9B6213537875C.syn_huoshan_mysql',
        object: '',
        defaultVal: {
          label: '',
          value: '',
        },
      },
      valueSort: 'asc',
      hide: 0,
      isHiddenAsterisk: 0,
      multiple: true,
      includeStar: true,
      extend: {
        starMeaning: '*',
      },
    },
  ]);
});

test('converter normalizes mysql outer datasource vars to guance sample shape', () => {
  const output = convertDashboard({
    title: 'MySQL Variable',
    templating: {
      list: [
        {
          current: {
            selected: false,
            text: 'All',
            value: '$__all',
          },
          datasource: { type: 'mysql', uid: 'mysql-1' },
          hide: 2,
          includeAll: true,
          multi: true,
          name: 'coin-copy-trade-standard-host',
          options: [],
          query: "select f_server_name  from t_app_detail where f_app_name = 'coin-copy-trade-standard'",
          refresh: 1,
          skipUrlSync: false,
          sort: 0,
          type: 'query',
        },
      ],
    },
    panels: [],
  });

  assert.deepEqual(output.main.vars[0], {
    name: 'coin-copy-trade-standard-host',
    seq: 0,
    datasource: 'outer_datasource',
    code: 'coin-copy-trade-standard-host',
    type: 'OUTER_DATASOURCE',
    definition: {
      tag: '',
      field: '',
      value: "select f_server_name  from t_app_detail where f_app_name = 'coin-copy-trade-standard'",
      metric: 'DFF672F02CAD7D94CA1ABA9B6213537875C.syn_huoshan_mysql',
      object: '',
      defaultVal: {
        label: '',
        value: '',
      },
    },
    valueSort: 'asc',
    hide: 0,
    isHiddenAsterisk: 0,
    multiple: true,
    includeStar: true,
    extend: {
      starMeaning: '*',
    },
  });
});

test('converter preserves concrete mysql outer datasource defaults when current value is not all', () => {
  const output = convertDashboard({
    title: 'MySQL Variable',
    templating: {
      list: [
        {
          current: {
            selected: true,
            text: 'cswap-match-0',
            value: 'cswap-match-0',
          },
          datasource: { type: 'mysql', uid: 'mysql-1' },
          hide: 2,
          includeAll: true,
          multi: true,
          name: 'match_app_name',
          query: 'select f_app_name from t_app',
          type: 'query',
        },
      ],
    },
    panels: [],
  });

  assert.deepEqual(output.main.vars[0].definition.defaultVal, {
    label: 'cswap-match-0',
    value: 'cswap-match-0',
  });
  assert.deepEqual(output.main.vars[0].extend, {
    starMeaning: '*',
  });
});

test('converter classifies non-cloudwatch-metric cloudwatch targets as promql and preserves the raw query', () => {
  const output = convertDashboard({
    title: 'CloudWatch',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'ELB Requests',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'cloudwatch' },
            query: 'aws_elb_request_count_sum',
          },
        ],
      },
    ],
  }, { guancePromqlCompatible: true });

  assert.equal(output.main.charts[0].queries[0].qtype, 'promql');
  assert.equal(output.main.charts[0].queries[0].query.type, 'promql');
  assert.equal(output.main.charts[0].queries[0].query.q, 'aws_elb_request_count_sum');
});

test('converter rewrites cloudwatch rds metrics to guance promql', () => {
  const output = convertDashboard({
    title: 'CloudWatch RDS',
    templating: {
      list: [
        {
          type: 'query',
          name: 'rds_instance',
          label: 'RDS Instance',
          datasource: { type: 'prometheus' },
          query: 'label_values(up, instance)',
          current: {
            text: 'prod-cswap-0',
            value: 'prod-cswap-0',
          },
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'RDS CPU',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'cloudwatch' },
            expr: 'cloudwatch_metric_rds{metric_name="CPUUtilization", instance_name=~"prod-cswap.*", instance_name!~".*match.*", instance_name!~".*market.*", env="$env"}',
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].queries[0].qtype, 'promql');
  assert.equal(output.main.charts[0].queries[0].query.type, 'promql');
  assert.equal(
    output.main.charts[0].queries[0].query.q,
    'CPUUtilization_Average{M="aws_AWS/RDS",Dimensions="DBInstanceIdentifier",DBInstanceIdentifier=~"#{rds_instance}"}'
  );
});

test('converter rewrites cloudwatch metric selectors even when datasource is prometheus', () => {
  const output = convertDashboard({
    title: 'CloudWatch via Prometheus',
    templating: {
      list: [
        {
          type: 'query',
          name: 'load_balancer_name',
          label: 'Load Balancer',
          datasource: { type: 'prometheus' },
          query: 'label_values(up, instance)',
          current: {
            text: 'alb-prod',
            value: 'alb-prod',
          },
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'ALB RT',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'topk(20, cloudwatch_metric_elb{metric_name="TargetResponseTime", instance_name=~"$load_balancer_name"})',
          },
        ],
      },
    ],
  });

  assert.equal(
    output.main.charts[0].queries[0].query.q,
    'topk(20, TargetResponseTime_Average{M="aws_AWS/ApplicationELB",Dimensions="LoadBalancer",LoadBalancer=~"#{load_balancer_name}"})'
  );
});

test('converter rewrites nested cloudwatch metric selectors with single-quoted values', () => {
  const output = convertDashboard({
    title: 'Nested CloudWatch',
    templating: {
      list: [
        {
          type: 'query',
          name: 'rds_instance',
          label: 'RDS Instance',
          datasource: { type: 'prometheus' },
          query: 'label_values(up, instance)',
          current: {
            text: 'prod-cswap-0',
            value: 'prod-cswap-0',
          },
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'DB Load',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: '((sum(cloudwatch_metric_rds{instance_name=~\'$rds_instance\', metric_name=~"DBLoad"}) by (instance_name))) / sum(cloudwatch_metric_rds{instance_name=~\'$rds_instance\', metric_name=~"cpu"}) by (instance_name)*100',
          },
        ],
      },
    ],
  });

  assert.equal(
    output.main.charts[0].queries[0].query.q,
    '((sum(DBLoad_Average{M="aws_AWS/RDS",Dimensions="DBInstanceIdentifier",DBInstanceIdentifier=~"#{rds_instance}"}) by (instance_name))) / sum(cpu_Average{M="aws_AWS/RDS",Dimensions="DBInstanceIdentifier",DBInstanceIdentifier=~"#{rds_instance}"}) by (instance_name)*100'
  );
});

test('converter rewrites cloudwatch alias templates to mapped guance dimensions', () => {
  const output = convertDashboard({
    title: 'CloudWatch Alias',
    templating: {
      list: [
        {
          type: 'query',
          name: 'redis_instance',
          label: 'Redis Instance',
          datasource: { type: 'prometheus' },
          query: 'label_values(up, instance)',
          current: {
            text: 'redis-prod',
            value: 'redis-prod',
          },
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Redis Memory',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            legendFormat: '{{instance_name}}',
            expr: 'cloudwatch_metric_redis{metric_name="DatabaseMemoryUsagePercentage", instance_name=~"$redis_instance"}',
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].queries[0].name, '{{CacheClusterId}}');
  assert.deepEqual(output.main.charts[0].extend.settings.alias, [
    { alias: '{{CacheClusterId}}', key: 'promql_1', name: 'promql_1', queryCode: 'A' },
  ]);
});

test('converter builds promql from structured cloudwatch targets', () => {
  const output = convertDashboard({
    title: 'Structured CloudWatch',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'RDS CPU',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'cloudwatch' },
            namespace: 'AWS/RDS',
            metricName: 'CPUUtilization',
            dimensions: {
              DBInstanceIdentifier: '$mysql_instance',
            },
            statistic: 'Average',
            queryMode: 'Metrics',
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].queries[0].qtype, 'promql');
  assert.equal(
    output.main.charts[0].queries[0].query.q,
    'CPUUtilization_Average{M="aws_AWS/RDS",Dimensions="DBInstanceIdentifier",DBInstanceIdentifier=~"#{rds_instance}"}'
  );
});

test('converter strips grafana $__rate_interval macro from promql queries', () => {
  const output = convertDashboard({
    title: 'Rate Interval',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Errors',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'rate(performance_interface_error_count[$__rate_interval])',
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].queries[0].query.q, 'rate(performance_interface_error_count)');
});

test('converter normalizes grafana variable time intervals to auto', () => {
  const output = convertDashboard({
    title: 'Variable Interval',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Errors',
        interval: '$interval',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'errors_total',
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].extend.settings.timeInterval, 'auto');
});

test('converter normalizes barchart settings for guance schema', () => {
  const output = convertDashboard({
    title: 'Bar Direction',
    panels: [
      {
        id: 1,
        type: 'barchart',
        title: 'Top Errors',
        interval: '$interval',
        options: {
          orientation: 'auto',
        },
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'topk(10, errors_total)',
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].type, 'bar');
  assert.equal(output.main.charts[0].extend.settings.timeInterval, 'auto');
  assert.equal(output.main.charts[0].extend.settings.xAxisShowType, 'groupBy');
  assert.equal(output.main.charts[0].extend.settings.direction, undefined);
});

test('converter keeps promql metric names unchanged even with guance promql compatibility enabled', () => {
  const output = convertDashboard({
    title: 'Keep Metric Name',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Interface Errors',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'sum(rate(performance_interface_error_count[5m]))',
          },
        ],
      },
    ],
  }, { guancePromqlCompatible: true });

  assert.equal(output.main.charts[0].queries[0].query.q, 'sum(rate(performance_interface_error_count[5m]))');
});

test('converter maps elasticsearch downstream error filters to dql trace query', () => {
  const output = convertDashboard({
    title: 'Elasticsearch Trace',
    templating: {
      list: [
        {
          name: 'url',
          type: 'custom',
          query: 'example.internal',
          current: { text: 'example.internal', value: 'example.internal' },
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Downstream Errors',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'elasticsearch', uid: 'es-1' },
            query: 'tag.otel@library@name:"io.opentelemetry.okhttp-3.0" AND tag.net@peer@name: $url AND tag.error:true',
            bucketAggs: [
              {
                field: 'process.serviceName',
                id: '2',
                settings: { min_doc_count: '1', order: 'desc', orderBy: '_term', size: '0' },
                type: 'terms',
              },
              {
                field: 'startTimeMillis',
                id: '3',
                settings: { interval: '1s', min_doc_count: '0', timeZone: 'utc', trimEdges: '0' },
                type: 'date_histogram',
              },
            ],
            metrics: [
              { id: '1', type: 'count' },
            ],
            timeField: 'startTimeMillis',
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].queries[0].qtype, 'dql');
  assert.equal(
    output.main.charts[0].queries[0].query.q,
    "T::RE(`.*`):(count(`*`)) { `status` = 'error' and `otel_library_name` = 'io.opentelemetry.okhttp-3.0' and `net_peer_name` = '#{url}' } BY `service`"
  );
  assert.equal(output.main.charts[0].queries[0].extend?.elasticsearchConversion, undefined);
});

test('converter maps elasticsearch top terms queries to slimit dql', () => {
  const output = convertDashboard({
    title: 'Elasticsearch Top Terms',
    templating: {
      list: [
        {
          name: 'bzi_server',
          type: 'custom',
          query: 'bon-gateway-svr',
          current: { text: 'bon-gateway-svr', value: 'bon-gateway-svr' },
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'bargauge',
        title: 'Slow Downstream APIs',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'elasticsearch', uid: 'es-1' },
            query: 'process.serviceName:$bzi_server AND tag.otel@library@name:"io.opentelemetry.okhttp-3.0" AND duration:>100000',
            bucketAggs: [
              {
                field: 'tag.http@url',
                id: '2',
                settings: { min_doc_count: '1', order: 'desc', orderBy: '1', size: '10' },
                type: 'terms',
              },
            ],
            metrics: [
              { id: '1', type: 'count' },
            ],
          },
        ],
      },
    ],
  });

  assert.equal(
    output.main.charts[0].queries[0].query.q,
    "T::RE(`.*`):(count(`*`)) { `service` = '#{bzi_server}' and `otel_library_name` = 'io.opentelemetry.okhttp-3.0' and `duration` > 100000 } BY `http_url` SORDER BY count(`*`) DESC SLIMIT 10"
  );
});

test('converter maps elasticsearch raw_data queries to trace record dql', () => {
  const output = convertDashboard({
    title: 'Elasticsearch Raw Data',
    templating: {
      list: [
        {
          name: 'bzi_server',
          type: 'custom',
          query: 'bon-gateway-svr',
          current: { text: 'bon-gateway-svr', value: 'bon-gateway-svr' },
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'table',
        title: 'Internal Errors',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'elasticsearch', uid: 'es-1' },
            query: 'process.serviceName:$bzi_server AND -tag.span@kind:server AND tag.otel@status_code:ERROR',
            bucketAggs: [],
            metrics: [
              { id: '1', settings: { size: '500' }, type: 'raw_data' },
            ],
          },
        ],
      },
    ],
  });

  assert.equal(output.main.charts[0].queries[0].qtype, 'dql');
  assert.equal(
    output.main.charts[0].queries[0].query.q,
    "T::RE(`.*`):(traces) { `status` = 'error' and `service` = '#{bzi_server}' and `span_kind` != 'server' } LIMIT 500"
  );
});

test('converter routes aliyun sls sql queries through local sls2dql', () => {
  const output = convertDashboard({
    title: 'SLS SQL',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Access Count',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'aliyun-log-service-datasource' },
            query: 'SELECT count(*) AS pv FROM access_log',
          },
        ],
      },
    ],
  }, { slsNamespace: 'L' });

  assert.equal(output.main.charts[0].queries[0].qtype, 'dql');
  assert.equal(output.main.charts[0].queries[0].query.type, 'dql');
  assert.equal(output.main.charts[0].queries[0].query.q, 'L::`access_log`:(count(*) AS `pv`)');
  assert.equal(output.main.charts[0].queries[0].extend?.slsConversion, undefined);
});

test('converter uses target logstore as sls source for search-only queries', () => {
  const output = convertDashboard({
    title: 'SLS Search Only',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Errors',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'aliyun-log-service-datasource' },
            logstore: 'access_log',
            query: 'status:500 AND service:api',
          },
        ],
      },
    ],
  }, { slsNamespace: 'L' });

  assert.equal(output.main.charts[0].queries[0].qtype, 'dql');
  assert.equal(output.main.charts[0].queries[0].query.q, 'L::`access_log`:(*){ (`status` = 500) , (`service` = "api") }');
  assert.equal(output.main.charts[0].queries[0].extend?.slsConversion, undefined);
});

test('converter does not emit approximate sls conversion metadata', () => {
  const output = convertDashboard({
    title: 'SLS Approximate',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Time Bucket',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'aliyun-log-service-datasource' },
            query: "* | select date_trunc('minute', __time__) as ts, count(*) as pv from access_log group by ts",
          },
        ],
      },
    ],
  }, { slsNamespace: 'L' });

  assert.equal(output.main.charts[0].queries[0].query.q, 'L::`access_log`:(count(*) AS `pv`)[::1m0s]');
  assert.equal(output.main.charts[0].queries[0].extend?.slsConversion, undefined);
});

test('converter does not emit unsupported sls conversion metadata', () => {
  const output = convertDashboard({
    title: 'SLS Unsupported',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Case Expr',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'aliyun-log-service-datasource' },
            query: '* | select case when status=200 then 1 else 0 end as ok from access_log',
          },
        ],
      },
    ],
  }, { slsNamespace: 'L' });

  assert.equal(output.main.charts[0].queries[0].query.q, '* | select case when status=200 then 1 else 0 end as ok from access_log');
  assert.equal(output.main.charts[0].queries[0].extend?.slsConversion, undefined);
});

test('converter maps mysql table panels to native outer datasource queries', () => {
  const output = convertDashboard({
    title: 'MySQL Raw SQL',
    panels: [
      {
        id: 1,
        type: 'table',
        title: 'Big Tables',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        datasource: { type: 'mysql', uid: 'mysql-1' },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'mysql', uid: 'mysql-1' },
            rawSql: "select cluster_name '实例名',schema_name '库名', table_name '表名',table_rows '行数' from t_big_table_infos where cluster_name like '%prod-cswap-%' order by table_rows desc;",
            format: 'table',
            editorMode: 'code',
          },
        ],
      },
    ],
  });

  assert.deepEqual(output.main.charts[0].queries[0], {
    name: '',
    type: 'table',
    unit: '',
    color: '',
    qtype: 'outer_datasource',
    datasource: 'dataflux',
    disabled: false,
    query: {
      q: `SELECT
    CAST(UNIX_TIMESTAMP(create_time) * 1000 AS SIGNED) AS time,
    cluster_name AS tag_实例名,
    schema_name AS tag_库名,
    table_name AS tag_表名,
    table_rows AS 行数
FROM t_big_table_infos
WHERE
    cluster_name LIKE '%prod-cswap-%'
ORDER BY
    table_rows DESC
LIMIT 5000;
`,
      code: 'B',
      type: 'func',
      funcList: [],
      funcName: 'DFF672F02CAD7D94CA1ABA9B6213537875C.syn_huoshan_mysql',
      funcType: 'datasource',
      funcSourceType: 'mysql',
    },
  });
});

test('converter allows overriding mysql external datasource mapping by uid', () => {
  const output = convertDashboard({
    title: 'MySQL Raw SQL',
    panels: [
      {
        id: 1,
        type: 'table',
        title: 'Big Tables',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        datasource: { type: 'mysql', uid: 'mysql-1' },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'mysql', uid: 'mysql-1' },
            rawSql: 'select table_name, table_rows from t_big_table_infos order by table_rows desc',
            format: 'table',
            editorMode: 'code',
          },
        ],
      },
    ],
  }, {
    sqlDatasourceMappings: {
      byUid: {
        'mysql-1': 'custom.mysql.datasource',
      },
    },
  });

  assert.equal(output.main.charts[0].queries[0].qtype, 'outer_datasource');
  assert.equal(output.main.charts[0].queries[0].query.type, 'func');
  assert.equal(output.main.charts[0].queries[0].query.q, 'select table_name, table_rows from t_big_table_infos order by table_rows desc;\n');
  assert.equal(output.main.charts[0].queries[0].query.funcName, 'custom.mysql.datasource');
  assert.equal(output.main.charts[0].queries[0].query.funcSourceType, 'mysql');
});

test('standalone converter accepts mysql external datasource override from cli', () => {
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'grafana-to-guance-skill-'));
  const inputPath = path.join(tempDirectory, 'mysql-dashboard.json');
  const outputPath = path.join(tempDirectory, 'mysql-dashboard.guance.json');

  fs.writeFileSync(inputPath, JSON.stringify({
    title: 'MySQL CLI',
    panels: [
      {
        id: 1,
        type: 'table',
        title: 'Big Tables',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'mysql', uid: 'mysql-1' },
            rawSql: 'select 1',
          },
        ],
      },
    ],
  }), 'utf8');

  execFileSync(
    process.execPath,
    [
      'scripts/convert-grafana-dashboard.mjs',
      '--input',
      inputPath,
      '--output',
      outputPath,
      '--mysql-external-datasource',
      'cli.mysql.datasource',
      '--validate',
    ],
    {
      cwd: SKILL_ROOT,
      stdio: 'pipe',
    }
  );

  const output = JSON.parse(fs.readFileSync(outputPath, 'utf8'));
  assert.equal(output.main.charts[0].queries[0].qtype, 'outer_datasource');
  assert.equal(output.main.charts[0].queries[0].query.type, 'func');
  assert.equal(output.main.charts[0].queries[0].query.q, 'select 1;\n');
  assert.equal(output.main.charts[0].queries[0].query.funcName, 'cli.mysql.datasource');
});

test('validator accepts generated dashboards with outer datasource vars', () => {
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'grafana-to-guance-skill-'));
  const inputPath = path.join(tempDirectory, 'mysql-vars-dashboard.json');
  const outputPath = path.join(tempDirectory, 'mysql-vars-dashboard.guance.json');

  fs.writeFileSync(inputPath, JSON.stringify({
    title: 'MySQL Variable',
    templating: {
      list: [
        {
          type: 'query',
          name: 'coin-copy-trade-standard-host',
          label: 'coin-copy-trade-standard-host',
          datasource: { type: 'mysql', uid: 'mysql-1' },
          query: "select f_server_name  from t_app_detail where f_app_name = 'coin-copy-trade-standard'",
          multi: true,
          includeAll: true,
        },
      ],
    },
    panels: [],
  }), 'utf8');

  execFileSync(
    process.execPath,
    ['scripts/convert-grafana-dashboard.mjs', '--input', inputPath, '--output', outputPath, '--validate'],
    {
      cwd: SKILL_ROOT,
      stdio: 'pipe',
    }
  );

  const output = JSON.parse(fs.readFileSync(outputPath, 'utf8'));
  assert.equal(output.main.vars[0].type, 'OUTER_DATASOURCE');
  assert.equal(output.main.vars[0].datasource, 'outer_datasource');
});

test('converter emits schema-specific levels for gauge and singlestat charts', () => {
  const output = convertDashboard(createThresholdDashboardFixture());
  const gaugeChart = output.main.charts.find((chart) => chart.type === 'gauge');
  const singlestatChart = output.main.charts.find((chart) => chart.type === 'singlestat');

  assert.deepEqual(gaugeChart.extend.settings.levels, [
    { value: [85], lineColor: 'green', operation: '<=' },
    { value: [95], lineColor: 'orange', operation: '<=' },
    { value: [100], lineColor: 'red', operation: '<=' },
  ]);
  assert.deepEqual(singlestatChart.extend.settings.levels, [
    { value: [80], bgColor: 'green', fontColor: '#5794F2', operation: '<' },
    { value: [80, 95], bgColor: 'orange', fontColor: '#5794F2', operation: 'between' },
    { value: [95], bgColor: 'red', fontColor: '#5794F2', operation: '>=' },
  ]);
});

test('validator rejects generic levels on gauge charts once chart type is enforced', () => {
  const output = convertDashboard(createThresholdDashboardFixture());
  const gaugeChart = output.main.charts.find((chart) => chart.type === 'gauge');
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'grafana-to-guance-skill-'));
  const outputPath = path.join(tempDirectory, 'invalid-dashboard.guance.json');

  gaugeChart.extend.settings.levels = [
    { title: 'Level 1', value: 0, bgColor: 'green' },
  ];
  fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, 'utf8');

  assert.throws(
    () =>
      execFileSync(
        process.execPath,
        ['scripts/validate-file.mjs', outputPath],
        {
          cwd: SKILL_ROOT,
          stdio: 'pipe',
        }
      ),
    /Validation failed/
  );
});

test('validator accepts real exported guance dashboard sample', () => {
  execFileSync(
    process.execPath,
    ['scripts/validate-file.mjs', GUANCE_ALL_CHARTS_INPUT],
    {
      cwd: SKILL_ROOT,
      stdio: 'pipe',
    }
  );
});

test('validator requires content queries for text-like charts', () => {
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'grafana-to-guance-skill-'));
  const outputPath = path.join(tempDirectory, 'invalid-text-dashboard.guance.json');
  const invalidDashboard = {
    title: 'Invalid Text Dashboard',
    main: {
      vars: [],
      charts: [
        {
          name: 'Text Panel',
          type: 'text',
          group: { name: null },
          pos: { x: 0, y: 0, w: 8, h: 8 },
          extend: {
            settings: {
              showTitle: true,
              titleDesc: '',
            },
          },
          queries: [
            {
              name: '',
              query: {},
            },
          ],
        },
      ],
      groups: [],
      type: 'template',
    },
  };

  fs.writeFileSync(outputPath, `${JSON.stringify(invalidDashboard, null, 2)}\n`, 'utf8');

  assert.throws(
    () =>
      execFileSync(
        process.execPath,
        ['scripts/validate-file.mjs', outputPath],
        {
          cwd: SKILL_ROOT,
          stdio: 'pipe',
        }
      ),
    /Validation failed/
  );
});

test('converter maps grafana field displayName overrides into guance aliases', () => {
  const output = convertDashboard(createAliasOverrideDashboardFixture());
  const aliasItems = output.main.charts[0].extend.settings.alias;

  assert.deepEqual(aliasItems, [
    { alias: '{{ state }}', key: 'promql_1', name: 'promql_1', queryCode: 'A' },
    { alias: 'Running', key: 'R', name: 'R' },
    { alias: 'Sleeping', key: 'S', name: 'S' },
  ]);
});

test('converter drops grafana __auto aliases from guance output', () => {
  const output = convertDashboard({
    title: 'Auto Alias',
    panels: [
      {
        id: 1,
        type: 'stat',
        title: 'CPU Cores',
        gridPos: { h: 8, w: 8, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            legendFormat: '__auto',
            expr: 'count(count(node_cpu_seconds_total) by (cpu))',
          },
        ],
      },
    ],
  });

  const chart = output.main.charts[0];
  assert.equal(chart.queries[0].name, undefined);
  assert.deepEqual(chart.extend.settings.alias, undefined);
});

test('converter maps query aliases to guance promql series keys', () => {
  const output = convertDashboard({
    title: 'CPU Basic',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'CPU Basic',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          { refId: 'A', datasource: { type: 'prometheus' }, legendFormat: 'Busy System', expr: 'avg(rate(node_cpu_seconds_total{mode="system"}[5m]))' },
          { refId: 'B', datasource: { type: 'prometheus' }, legendFormat: 'Busy User', expr: 'avg(rate(node_cpu_seconds_total{mode="user"}[5m]))' },
        ],
      },
    ],
  });

  assert.deepEqual(output.main.charts[0].extend.settings.alias, [
    { alias: 'Busy System', key: 'promql_1', name: 'promql_1', queryCode: 'A' },
    { alias: 'Busy User', key: 'promql_2', name: 'promql_2', queryCode: 'B' },
  ]);
});

test('converter maps grafana percentunit to guance percent unit', () => {
  const output = convertDashboard({
    title: 'Percent Unit',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'CPU Basic',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        fieldConfig: {
          defaults: {
            unit: 'percentunit',
          },
        },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'avg(rate(node_cpu_seconds_total{mode="system"}[5m]))',
          },
        ],
      },
    ],
  });

  assert.deepEqual(output.main.charts[0].extend.settings.globalUnit, ['percent', 'percent_decimal']);
});

test('converter maps grafana reqps to guance throughput unit', () => {
  const output = convertDashboard({
    title: 'Reqps Unit',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Request Rate',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        fieldConfig: {
          defaults: {
            unit: 'reqps',
          },
        },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'rate(http_requests_total[5m])',
          },
        ],
      },
    ],
  });

  assert.deepEqual(output.main.charts[0].extend.settings.globalUnit, ['throughput', 'reqps']);
});

test('converter maps grafana units to documented guance measure pairs', () => {
  const units = [
    ['ops', ['throughput', 'ops']],
    ['iops', ['throughput', 'iops']],
    ['bps', ['bandWidth', 'bps']],
    ['Bps', ['traffic', 'B/S']],
    ['hertz', ['frequency', 'Hz']],
    ['rotrpm', ['frequency', 'rpm']],
    ['celsius', ['temperature', 'C']],
    ['short', ['number', 'short_scale']],
    ['decbits', ['digital', 'b']],
  ];

  for (const [unit, expected] of units) {
    const output = convertDashboard({
      title: `${unit} Unit`,
      panels: [
        {
          id: 1,
          type: 'timeseries',
          title: String(unit),
          gridPos: { h: 8, w: 12, x: 0, y: 0 },
          fieldConfig: {
            defaults: {
              unit,
            },
          },
          targets: [
            {
              refId: 'A',
              datasource: { type: 'prometheus' },
              expr: 'metric_name',
            },
          ],
        },
      ],
    });

    assert.deepEqual(output.main.charts[0].extend.settings.globalUnit, expected);
  }
});

test('converter classifies alias templates for guance compatibility review', () => {
  const fixture = {
    title: 'Alias Template Review',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Templates',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            legendFormat: '{{host}}',
            expr: 'sum(node_load1)',
          },
          {
            refId: 'B',
            datasource: { type: 'prometheus' },
            legendFormat: '{{device}} - Read',
            expr: 'sum(node_disk_reads_completed_total)',
          },
        ],
      },
    ],
  };
  const output = convertDashboard(fixture, { keepGrafanaMeta: true });

  assert.deepEqual(output.main.charts[0].extend.settings.extend.aliasReview, [
    { alias: '{{host}}', key: 'promql_1', classification: 'safe_guance' },
    { alias: '{{device}} - Read', key: 'promql_2', classification: 'compat_grafana_template' },
  ]);
});

test('converter omits grafana-only settings metadata by default', () => {
  const output = convertDashboard(createAliasOverrideDashboardFixture());
  const chartExtend = output.main.charts[0].extend.settings.extend;

  assert.equal(chartExtend, undefined);
});

test('converter keeps grafana-only settings metadata when explicitly enabled', () => {
  const output = convertDashboard(createAliasOverrideDashboardFixture(), { keepGrafanaMeta: true });
  const chartExtend = output.main.charts[0].extend.settings.extend;

  assert.ok(Array.isArray(chartExtend.fieldOverrides));
  assert.ok(chartExtend.fieldOverrides.length > 0);
});

function createPrometheusDashboardFixture() {
  return {
    title: 'Prometheus Variables',
    templating: {
      list: [
        {
          name: 'ds_prometheus',
          label: 'Prometheus',
          type: 'datasource',
          query: 'prometheus',
          current: { text: 'Prometheus', value: 'prometheus' },
          hide: 0,
          includeAll: false,
          multi: false,
          options: [],
        },
        {
          name: 'job',
          label: 'Job',
          type: 'query',
          datasource: { type: 'prometheus' },
          query: { qtype: 'promql', rawQuery: 'label_values(up, job)' },
          current: { text: 'api', value: 'api' },
          hide: 0,
          includeAll: false,
          multi: false,
          options: [],
        },
        {
          name: 'instance',
          label: 'Instance',
          type: 'query',
          datasource: { type: 'prometheus' },
          query: { qtype: 'promql', rawQuery: 'label_values(up{job=~"$job"}, instance)' },
          current: { text: 'demo', value: 'demo' },
          hide: 0,
          includeAll: false,
          multi: false,
          options: [],
        },
      ],
    },
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Requests',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'sum(rate(http_requests_total{job=~"$job",instance=~"$instance"}[5m]))',
          },
        ],
      },
    ],
  };
}

function createThresholdDashboardFixture() {
  return {
    title: 'Thresholds',
    panels: [
      {
        id: 1,
        type: 'gauge',
        title: 'CPU Busy',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        fieldConfig: {
          defaults: {
            min: 0,
            max: 100,
            unit: 'percent',
            thresholds: {
              mode: 'absolute',
              steps: [
                { color: 'green', value: null },
                { color: 'orange', value: 85 },
                { color: 'red', value: 95 },
              ],
            },
          },
        },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'avg(rate(node_cpu_seconds_total[5m])) * 100',
          },
        ],
      },
      {
        id: 2,
        type: 'stat',
        title: 'Error Rate',
        gridPos: { h: 8, w: 12, x: 12, y: 0 },
        fieldConfig: {
          defaults: {
            color: {
              mode: 'fixed',
              fixedColor: '#5794F2',
            },
            thresholds: {
              mode: 'absolute',
              steps: [
                { color: 'green', value: null },
                { color: 'orange', value: 80 },
                { color: 'red', value: 95 },
              ],
            },
          },
        },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            expr: 'sum(rate(http_requests_total[5m]))',
          },
        ],
      },
    ],
  };
}

function createAliasOverrideDashboardFixture() {
  return {
    title: 'Alias Overrides',
    panels: [
      {
        id: 1,
        type: 'timeseries',
        title: 'Processes',
        gridPos: { h: 8, w: 12, x: 0, y: 0 },
        fieldConfig: {
          overrides: [
            {
              matcher: { id: 'byName', options: 'R' },
              properties: [{ id: 'displayName', value: 'Running' }],
            },
            {
              matcher: { id: 'byName', options: 'S' },
              properties: [{ id: 'displayName', value: 'Sleeping' }],
            },
          ],
        },
        targets: [
          {
            refId: 'A',
            datasource: { type: 'prometheus' },
            legendFormat: '{{ state }}',
            expr: 'sum by (state) (node_processes_state)',
          },
        ],
      },
    ],
  };
}
