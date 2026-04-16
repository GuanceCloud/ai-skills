#!/usr/bin/env node
import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';
import Ajv from 'ajv';
import { convertDashboard } from './convert-grafana-dashboard-core.js';
const SCRIPT_DIRECTORY = path.dirname(new URL(import.meta.url).pathname);
const SKILL_ROOT = path.resolve(SCRIPT_DIRECTORY, '..');
if (isDirectExecution()) {
    main();
}
function isDirectExecution() {
    if (!process.argv[1])
        return false;
    return import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
}
export function main() {
    const { inputPath, outputPath, validateOutput, schemaId, guancePromqlCompatible, keepGrafanaMeta } = parseArgs(process.argv.slice(2));
    const grafanaDashboard = readJson(inputPath);
    const guanceDashboard = convertDashboard(grafanaDashboard, { guancePromqlCompatible, keepGrafanaMeta });
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, `${JSON.stringify(guanceDashboard, null, 2)}\n`, 'utf8');
    console.log(`Converted ${inputPath} -> ${outputPath}`);
    if (validateOutput) {
        validateDashboardFile(outputPath, schemaId);
    }
}
function parseArgs(args) {
    let inputPath = '';
    let outputPath = '';
    let validateOutput = false;
    let schemaId = 'dashboard-schema.json';
    let guancePromqlCompatible = false;
    let keepGrafanaMeta = false;
    for (let index = 0; index < args.length; index++) {
        const value = args[index];
        if ((value === '-i' || value === '--input') && args[index + 1]) {
            inputPath = path.resolve(args[++index]);
            continue;
        }
        if ((value === '-o' || value === '--output') && args[index + 1]) {
            outputPath = path.resolve(args[++index]);
            continue;
        }
        if (value === '--validate') {
            validateOutput = true;
            continue;
        }
        if (value === '--schema' && args[index + 1]) {
            schemaId = args[++index];
            continue;
        }
        if (value === '--guance-promql-compatible') {
            guancePromqlCompatible = true;
            continue;
        }
        if (value === '--keep-grafana-meta') {
            keepGrafanaMeta = true;
            continue;
        }
        if (value === '-h' || value === '--help') {
            printHelp();
            process.exit(0);
        }
    }
    if (!inputPath) {
        printHelp();
        process.exit(1);
    }
    if (!outputPath) {
        const parsed = path.parse(inputPath);
        outputPath = path.join(parsed.dir, `${parsed.name}.guance.json`);
    }
    return { inputPath, outputPath, validateOutput, schemaId, guancePromqlCompatible, keepGrafanaMeta };
}
function printHelp() {
    console.error('Usage: node convert-grafana-dashboard.mjs --input <grafana.json> [--output <guance.json>] [--validate] [--schema <schema-id>] [--guance-promql-compatible] [--keep-grafana-meta]');
}
export function validateDashboardFile(filePath, schemaId) {
    const schemasDirectory = resolveSchemasDirectory();
    const ajv = new Ajv({ allErrors: true });
    forEachFile(schemasDirectory, (schemaPath) => {
        if (!schemaPath.endsWith('.json'))
            return;
        ajv.addSchema(readJson(schemaPath));
    });
    const valid = ajv.validate(schemaId, readJson(filePath));
    if (valid) {
        console.log(`Validated ${filePath} against ${schemaId}`);
        return;
    }
    console.error(`Validation failed for ${filePath} against ${schemaId}:`);
    for (const error of ajv.errors || []) {
        const instancePath = error.instancePath || '/';
        console.error(`- ${instancePath} ${error.message}`);
    }
    process.exit(1);
}
function resolveSchemasDirectory() {
    const skillSchemasDirectory = path.join(SKILL_ROOT, 'schemas');
    if (fs.existsSync(path.join(skillSchemasDirectory, 'dashboard-schema.json'))) {
        return skillSchemasDirectory;
    }
    throw new Error(`Could not locate standalone schemas at ${skillSchemasDirectory}`);
}
function readJson(filePath) {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}
function forEachFile(directoryPath, visitor) {
    const entries = fs.readdirSync(directoryPath, { withFileTypes: true });
    for (const entry of entries) {
        const entryPath = path.join(directoryPath, entry.name);
        if (entry.isDirectory()) {
            forEachFile(entryPath, visitor);
            continue;
        }
        visitor(entryPath);
    }
}
export { convertDashboard };
