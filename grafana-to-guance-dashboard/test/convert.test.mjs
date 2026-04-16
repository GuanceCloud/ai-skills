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
