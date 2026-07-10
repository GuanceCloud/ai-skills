#!/usr/bin/env node
import Ajv from 'ajv';
import fs from 'fs';
import path from 'path';

const SCRIPT_DIRECTORY = path.dirname(new URL(import.meta.url).pathname);
const SKILL_ROOT = path.resolve(SCRIPT_DIRECTORY, '..');
const SCHEMAS_DIRECTORY = path.join(SKILL_ROOT, 'schemas');

const args = process.argv.slice(2);
const schemaFlagIndex = args.indexOf('--schema');
const schemaId = schemaFlagIndex >= 0 ? args[schemaFlagIndex + 1] : 'dashboard-schema.json';
const jsonPaths = schemaFlagIndex >= 0 ? args.filter((_, index) => index !== schemaFlagIndex && index !== schemaFlagIndex + 1) : args;

if (jsonPaths.length === 0) {
    console.error('Usage: node scripts/validate-file.mjs <json-path...> [--schema <schema-id>]');
    process.exit(1);
}
if (!fs.existsSync(path.join(SCHEMAS_DIRECTORY, 'dashboard-schema.json'))) {
    console.error(`Could not locate standalone schemas at ${SCHEMAS_DIRECTORY}`);
    process.exit(1);
}

const ajv = new Ajv({ allErrors: true });
forEachFile(SCHEMAS_DIRECTORY, (schemaPath) => {
    if (!schemaPath.endsWith('.json'))
        return;
    ajv.addSchema(readJson(schemaPath));
});

let hasError = false;
for (const jsonPath of jsonPaths) {
    const valid = ajv.validate(schemaId, readJson(jsonPath));
    if (valid) {
        console.log(`Validated ${jsonPath} against ${schemaId}`);
        continue;
    }
    hasError = true;
    console.error(`Validation failed for ${jsonPath} against ${schemaId}:`);
    for (const error of ajv.errors || []) {
        const instancePath = error.instancePath || '/';
        console.error(`- ${instancePath} ${error.message}`);
    }
}

process.exit(hasError ? 1 : 0);

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

function readJson(filePath) {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}
