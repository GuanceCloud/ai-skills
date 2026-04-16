import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

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
