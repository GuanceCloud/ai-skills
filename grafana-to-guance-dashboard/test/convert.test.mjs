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
