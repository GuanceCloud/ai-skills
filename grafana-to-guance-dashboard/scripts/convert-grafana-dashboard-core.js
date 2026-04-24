import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    convertElasticsearchQueryToDql,
    isElasticsearchDatasource,
} from './elasticsearch-to-dql.js';

const SCRIPT_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const REPOSITORY_ROOT = path.resolve(SCRIPT_DIRECTORY, '..', '..');
const CLOUDWATCH_MAPPING_FILE = path.resolve(SCRIPT_DIRECTORY, '..', 'references', 'cloudwatch-promql-mapping.md');
const SLS2DQL_BINARY = path.resolve(REPOSITORY_ROOT, 'sls2dql', 'bin', 'sls2dql');
const DEFAULT_SLS_NAMESPACE = 'L';
const DEFAULT_EXTERNAL_DATASOURCE_MAPPINGS = {
    mysql: 'DFF672F02CAD7D94CA1ABA9B6213537875C.syn_huoshan_mysql',
};
const DEFAULT_MYSQL_OUTER_DATASOURCE_TIME_FIELD = 'create_time';
const SLS_CONVERSION_CACHE = new Map();
let CLOUDWATCH_SERVICE_MAPPINGS = null;

const PANEL_TYPE_MAP = {
    stat: 'singlestat',
    singlestat: 'singlestat',
    timeseries: 'sequence',
    graph: 'sequence',
    trend: 'sequence',
    bargauge: 'toplist',
    gauge: 'gauge',
    barchart: 'bar',
    piechart: 'pie',
    table: 'table',
    text: 'text',
    heatmap: 'heatmap',
    histogram: 'histogram',
    treemap: 'treemap',
    geomap: 'worldmap',
    logs: 'log',
};
const GRAFANA_BUILTIN_VARS = new Set([
    '__interval',
    '__interval_ms',
    '__rate_interval',
    '__range',
    '__range_s',
    '__range_ms',
    '__from',
    '__to',
    '__dashboard',
    '__name',
    '__org',
    '__user',
]);
const PROMQL_RESERVED_WORDS = new Set([
    'and',
    'or',
    'unless',
    'by',
    'without',
    'on',
    'ignoring',
    'group_left',
    'group_right',
    'bool',
    'offset',
]);
const UNIT_MAP = {
    percent: ['percent', 'percent'],
    percentunit: ['percent', 'percent_decimal'],
    bytes: ['digital', 'B'],
    decbytes: ['digital', 'B'],
    bits: ['digital', 'b'],
    decbits: ['digital', 'b'],
    deckbytes: ['digital', 'KB'],
    decgbytes: ['digital', 'GB'],
    ms: ['time', 'ms'],
    s: ['time', 's'],
    m: ['time', 'min'],
    h: ['time', 'h'],
    d: ['time', 'd'],
    short: ['number', 'short_scale'],
    none: ['custom', 'none'],
    reqps: ['throughput', 'reqps'],
    ops: ['throughput', 'ops'],
    iops: ['throughput', 'iops'],
    bps: ['bandWidth', 'bps'],
    Bps: ['traffic', 'B/S'],
    hertz: ['frequency', 'Hz'],
    rotrpm: ['frequency', 'rpm'],
    celsius: ['temperature', 'C'],
};
const COMPARE_OPTIONS = {
    hourCompare: { label: '小时同比', value: 'hourCompare' },
    dayCompare: { label: '日同比', value: 'dayCompare' },
    weekCompare: { label: '周同比', value: 'weekCompare' },
    monthCompare: { label: '月同比', value: 'monthCompare' },
    circleCompare: { label: '环比', value: 'circleCompare' },
};
export function convertDashboard(grafanaDashboard, options = {}) {
    var _a, _b;
    const variableContext = buildVariableContext((((_a = grafanaDashboard.templating) === null || _a === void 0 ? void 0 : _a.list) || []), options);
    const state = {
        groups: [],
        groupUnfoldStatus: {},
        charts: [],
    };
    const sortedPanels = sortPanels(grafanaDashboard.panels || []);
    collectPanels(sortedPanels, state, null, variableContext.variableNames, options);
    return pruneEmpty({
        title: grafanaDashboard.title || '',
        description: grafanaDashboard.description || undefined,
        tags: grafanaDashboard.tags || undefined,
        uid: grafanaDashboard.uid || undefined,
        dashboardExtend: {
            groupUnfoldStatus: state.groupUnfoldStatus,
        },
        main: {
            vars: convertVariables(variableContext.variables, variableContext.variableNames, options),
            charts: state.charts,
            groups: state.groups,
            type: 'template',
        },
    });
}
function buildVariableContext(variables, options = {}) {
    const keptVariables = [];
    const variableNames = new Set();
    for (const variable of Array.isArray(variables) ? variables : []) {
        if (shouldSkipVariable(variable, options)) {
            continue;
        }
        keptVariables.push(variable);
        if (variable === null || variable === void 0 ? void 0 : variable.name) {
            variableNames.add(variable.name);
        }
    }
    return {
        variables: keptVariables,
        variableNames,
    };
}
function shouldSkipVariable(variable, options = {}) {
    const variableType = String(variable === null || variable === void 0 ? void 0 : variable.type).toLowerCase();
    const variableName = normalizeVariableIdentifier(variable === null || variable === void 0 ? void 0 : variable.name);
    if (variableType === 'datasource' || variableName === 'ds_prometheus') {
        return true;
    }
    if (options.keepJobVariable === true) {
        return false;
    }
    return variableName === 'job';
}
function collectPanels(panels, state, inheritedGroup = null, variableNames = new Set(), options = {}) {
    let activeRow = inheritedGroup;
    let openRowPanel = null;
    for (const panel of panels) {
        if (panel.type === 'row') {
            const rowName = panel.title || '';
            if (rowName) {
                state.groups.push({ name: rowName });
                state.groupUnfoldStatus[rowName] = !panel.collapsed;
            }
            if (panel.collapsed) {
                collectPanels(sortPanels(panel.panels || []), state, rowName || null, variableNames, options);
                activeRow = inheritedGroup;
                openRowPanel = null;
            }
            else {
                activeRow = rowName || null;
                openRowPanel = panel;
            }
            continue;
        }
        const chart = convertPanel(panel, activeRow, openRowPanel, variableNames, options);
        if (chart) {
            state.charts.push(chart);
        }
    }
}
function sortPanels(panels) {
    return [...panels].sort((left, right) => {
        var _a, _b, _c, _d;
        const leftPos = left.gridPos || {};
        const rightPos = right.gridPos || {};
        const leftY = (_a = leftPos.y) !== null && _a !== void 0 ? _a : Number.MAX_SAFE_INTEGER;
        const rightY = (_b = rightPos.y) !== null && _b !== void 0 ? _b : Number.MAX_SAFE_INTEGER;
        if (leftY !== rightY)
            return leftY - rightY;
        const leftX = (_c = leftPos.x) !== null && _c !== void 0 ? _c : Number.MAX_SAFE_INTEGER;
        const rightX = (_d = rightPos.x) !== null && _d !== void 0 ? _d : Number.MAX_SAFE_INTEGER;
        if (leftX !== rightX)
            return leftX - rightX;
        return (left.id || 0) - (right.id || 0);
    });
}
function convertVariables(variables, variableNames, options = {}) {
    return variables
        .map((variable, index) => convertVariable(variable, index, variableNames, options))
        .filter(Boolean);
}
function convertVariable(variable, index, variableNames, options = {}) {
    const variableType = String(variable.type || '');
    const preparedQuery = prepareVariableQuery(variable, options);
    const queryString = preparedQuery.queryText;
    const queryKind = variableType === 'query' ? inferVariableQueryType(variable) : '';
    const current = variable.current || {};
    const currentText = stringifyCurrent(current.text);
    const currentValue = stringifyCurrent(current.value);
    const includeAll = Boolean(variable.includeAll);
    const defaultVal = {
        label: normalizeAllValue(currentText, variable.allValue),
        value: normalizeAllValue(currentValue, variable.allValue, true),
    };
    const outerDatasourceDefaultVal = normalizeOuterDatasourceDefaultVal(defaultVal, includeAll);
    const outerDatasourceExtend = pruneEmpty({
        starMeaning: includeAll ? '*' : undefined,
    });
    const base = {
        name: variable.label || variable.name || '',
        seq: index,
        code: variable.name || `var_${index}`,
        hide: variable.hide && variable.hide !== 0 ? 1 : 0,
        multiple: Boolean(variable.multi),
        includeStar: includeAll,
        isHiddenAsterisk: includeAll ? 0 : undefined,
        valueSort: queryKind === 'OUTER_DATASOURCE' ? 'asc' : 'desc',
        extend: pruneEmpty({
            originalType: variableType,
            description: variable.description || undefined,
            starMeaning: includeAll ? '*' : undefined,
            options: Array.isArray(variable.options) ? variable.options : undefined,
            refresh: variable.refresh,
            skipUrlSync: variable.skipUrlSync,
            sort: variable.sort,
        }),
    };
    if (variableType === 'textbox' || variableType === 'constant' || variableType === 'interval') {
        return pruneEmpty({
            ...base,
            datasource: 'custom',
            type: 'CUSTOM_LIST',
            multiple: false,
            includeStar: false,
            definition: {
                value: variable.query || currentValue || '',
                defaultVal,
            },
        });
    }
    if (variableType === 'custom' || variableType === 'datasource') {
        return pruneEmpty({
            ...base,
            datasource: 'custom',
            type: 'CUSTOM_LIST',
            definition: {
                value: variable.query || extractCustomOptions(variable.options || []),
                defaultVal,
            },
        });
    }
    if (variableType === 'query') {
        if (queryKind === 'OUTER_DATASOURCE') {
            return pruneEmpty({
                ...base,
                hide: 0,
                extend: outerDatasourceExtend,
                datasource: 'outer_datasource',
                type: 'OUTER_DATASOURCE',
                definition: {
                    tag: '',
                    field: '',
                    value: replaceVariables(queryString || '', variableNames),
                    metric: resolveExternalDatasourceMetric(preparedQuery.externalDatasourceInfo),
                    object: '',
                    defaultVal: outerDatasourceDefaultVal,
                },
            });
        }
        return pruneEmpty({
            ...base,
            datasource: queryKind === 'FIELD' ? 'object' : 'dataflux',
            type: queryKind,
            definition: {
                tag: '',
                field: queryKind === 'FIELD' ? extractFieldName(queryString) : '',
                value: replaceVariables(queryString || '', variableNames),
                metric: extractMetricName(queryString, variableNames),
                object: queryKind === 'FIELD' ? 'HOST' : '',
                defaultVal,
            },
        });
    }
    return pruneEmpty({
        ...base,
        datasource: 'custom',
        type: 'CUSTOM_LIST',
        multiple: false,
        includeStar: false,
        definition: {
            value: variable.query || currentValue || '',
            defaultVal,
        },
    });
}
function convertPanel(panel, groupName, rowPanel, variableNames, options) {
    const chartType = inferChartType(panel);
    if (!chartType || !panel.gridPos) {
        return null;
    }
    const queries = buildQueries(panel, chartType, variableNames, options);
    const settings = buildSettings(panel, chartType, queries, variableNames, options);
    const links = extractPanelLinks(panel, variableNames);
    const group = groupName !== null && groupName !== void 0 ? groupName : null;
    const position = buildPosition(panel, rowPanel);
    const chart = pruneEmpty({
        name: replaceVariables(panel.title || '', variableNames),
        type: chartType,
        group: { name: group },
        pos: position,
        extend: {
            settings,
            links: links.length ? links : undefined,
            sourcePanelType: options.keepGrafanaMeta ? panel.type : undefined,
            sourcePanelId: options.keepGrafanaMeta ? panel.id : undefined,
            pluginVersion: options.keepGrafanaMeta ? panel.pluginVersion || undefined : undefined,
            grafana: options.keepGrafanaMeta
                ? pruneEmpty({
                    fieldConfig: panel.fieldConfig,
                    options: panel.options,
                    transformations: panel.transformations,
                    transparent: panel.transparent,
                    repeat: panel.repeat,
                    datasource: panel.datasource,
                })
                : undefined,
        },
        queries,
    });
    if (queries.length === 0) {
        chart.queries = [];
    }
    return chart;
}
function buildPosition(panel, rowPanel) {
    var _a, _b;
    const gridPos = panel.gridPos || {};
    const rowOffset = (_b = (_a = rowPanel === null || rowPanel === void 0 ? void 0 : rowPanel.gridPos) === null || _a === void 0 ? void 0 : _a.y) !== null && _b !== void 0 ? _b : 0;
    const rawY = typeof gridPos.y === 'number' ? gridPos.y - rowOffset : 0;
    return {
        x: numberOr(gridPos.x, 0),
        y: round1(rawY * 1.9 + 0.5),
        w: numberOr(gridPos.w, 12),
        h: round1(numberOr(gridPos.h, 8) * 1.9 + 0.1),
    };
}
function buildQueries(panel, chartType, variableNames, options = {}) {
    var _a;
    const queries = [];
    const targets = Array.isArray(panel.targets) ? panel.targets : [];
    for (let index = 0; index < targets.length; index++) {
        const target = targets[index];
        const preparedQuery = prepareTargetQuery(target, options);
        const queryText = preparedQuery.queryText;
        if (!queryText)
            continue;
        if (shouldUseMysqlOuterDatasourceQuery(chartType, target, preparedQuery)) {
            queries.push(buildMysqlOuterDatasourceQuery(chartType, target, index, preparedQuery, variableNames));
            continue;
        }
        const qtype = inferQueryLanguage(target, queryText);
        const targetAlias = normalizeTargetAlias(target.legendFormat || target.alias || '', queryText, qtype);
        const normalizedQueryText = normalizeTargetQuery(queryText, qtype, options, target);
        queries.push(pruneEmpty({
            name: targetAlias || undefined,
            type: chartType,
            qtype,
            datasource: 'dataflux',
            disabled: Boolean(target.hide),
            query: {
                q: replaceVariables(normalizedQueryText, variableNames),
                code: normalizeQueryCode(target.refId, index),
                type: qtype,
                promqlCode: qtype === 'promql' ? index + 1 : undefined,
                field: target.field || undefined,
                externalDatasource: buildExternalDatasourceQuery(preparedQuery.externalDatasourceInfo),
            },
            extend: pruneEmpty({
                refId: target.refId || undefined,
                datasource: target.datasource || undefined,
                editorMode: target.editorMode || undefined,
                queryMode: target.queryMode || undefined,
            }),
        }));
    }
    if (chartType === 'text' && ((_a = panel.options) === null || _a === void 0 ? void 0 : _a.content)) {
        queries.push({
            query: {
                content: replaceVariables(panel.options.content, variableNames),
            },
        });
    }
    return queries;
}
function shouldUseMysqlOuterDatasourceQuery(chartType, target, preparedQuery) {
    var _a;
    const datasourceType = getDatasourceType(target.datasource);
    return (chartType === 'table' &&
        isMysqlDatasource(datasourceType) &&
        (((_a = preparedQuery.externalDatasourceInfo) === null || _a === void 0 ? void 0 : _a.status) === 'mapped') &&
        Boolean(preparedQuery.externalDatasourceInfo.targetDatasource));
}
function buildMysqlOuterDatasourceQuery(chartType, target, index, preparedQuery, variableNames) {
    var _a, _b;
    return {
        name: '',
        type: chartType,
        unit: '',
        color: '',
        qtype: 'outer_datasource',
        datasource: 'dataflux',
        disabled: Boolean(target.hide),
        query: {
            q: replaceVariables(normalizeMysqlOuterDatasourceSql(preparedQuery.queryText), variableNames),
            code: normalizeOuterDatasourceQueryCode(index),
            type: 'func',
            funcList: [],
            funcName: preparedQuery.externalDatasourceInfo.targetDatasource,
            funcType: 'datasource',
            funcSourceType: (_b = (_a = preparedQuery.externalDatasourceInfo) === null || _a === void 0 ? void 0 : _a.datasourceType) !== null && _b !== void 0 ? _b : 'mysql',
        },
    };
}
function buildSettings(panel, chartType, queries, variableNames, converterOptions = {}) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w, _x, _y;
    const defaults = ((_a = panel.fieldConfig) === null || _a === void 0 ? void 0 : _a.defaults) || {};
    const custom = defaults.custom || {};
    const options = panel.options || {};
    const legend = options.legend || panel.legend || {};
    const transformationInfo = parseTransformations(panel.transformations || []);
    const aliasInfo = buildAliases(queries, panel.fieldConfig, variableNames);
    const aliases = aliasInfo.items;
    const tableColumns = buildTableColumns(panel.fieldConfig, transformationInfo.organize, variableNames);
    const fieldOverrides = buildFieldOverrides(panel.fieldConfig, variableNames);
    const legacyGauge = panel.gauge || {};
    const valueMappings = buildLegacyValueMappings(panel.valueMaps);
    const rangeMappings = buildLegacyRangeMappings(panel.rangeMaps);
    const mappingItems = [...buildMappings(defaults.mappings), ...valueMappings, ...rangeMappings];
    const explicitUnit = firstDefined(defaults.unit, panel.format, (_c = (_b = panel.yaxes) === null || _b === void 0 ? void 0 : _b[0]) === null || _c === void 0 ? void 0 : _c.format);
    const unit = explicitUnit || inferUnitFromQueries(queries, chartType);
    const precision = firstDefinedNumber(defaults.decimals, panel.decimals);
    const min = firstDefinedNumber(defaults.min, legacyGauge.minValue, (_e = (_d = panel.yaxes) === null || _d === void 0 ? void 0 : _d[0]) === null || _e === void 0 ? void 0 : _e.min);
    const max = firstDefinedNumber(defaults.max, legacyGauge.maxValue, (_g = (_f = panel.yaxes) === null || _f === void 0 ? void 0 : _f[0]) === null || _g === void 0 ? void 0 : _g.max);
    const lineWidth = firstDefinedNumber(custom.lineWidth, panel.linewidth);
    const fillOpacity = firstDefinedNumber(custom.fillOpacity, normalizeLegacyFill(panel.fill));
    const reduceOptions = options.reduceOptions || {};
    const legendValues = mapLegendCalcs(((_h = legend.calcs) === null || _h === void 0 ? void 0 : _h.length) ? legend.calcs : extractLegacyLegendCalcs(legend));
    const connectNulls = normalizeConnectNulls(firstDefined(custom.spanNulls, panel.nullPointMode));
    const pointMode = firstDefined(custom.showPoints, panel.points === true ? 'always' : panel.points === false ? 'never' : undefined);
    const graphMode = options.graphMode || undefined;
    const legacyTextMode = panel.valueName || undefined;
    const workspaceInfo = extractWorkspaceInfo(panel.targets || []);
    const tooltip = options.tooltip || panel.tooltip || {};
    const statText = options.text || {};
    const textInfo = chartType === 'text' ? analyzeTextPanel(options.content, options.mode) : null;
    const tableFooter = options.footer || {};
    const tableSortBy = Array.isArray(options.sortBy) ? options.sortBy : [];
    const tableCustom = chartType === 'table' ? custom : {};
    const compareInfo = inferCompareSettings(queries, chartType);
    const sortInfo = inferSortSettings(chartType, legend, tableSortBy);
    const customUnits = buildCustomUnits(panel.fieldConfig);
    const customColors = buildCustomColors(panel.fieldConfig);
    const colorMappings = buildColorMappings(panel.fieldConfig, chartType);
    const valColorMappings = buildValColorMappings(panel.fieldConfig, transformationInfo.organize);
    const effectiveUnitType = customUnits.length ? 'custom' : unit ? 'global' : undefined;
    const slimit = inferSeriesLimit(queries, options, chartType);
    const levelFontColor = normalizeColor(firstDefined((_q = defaults.color) === null || _q === void 0 ? void 0 : _q.fixedColor, ''));
    const levels = buildLevels(defaults.thresholds, chartType, {
        min,
        max,
        fontColor: levelFontColor,
    });
    const settings = {
        showTitle: true,
        titleDesc: panel.description || '',
        isSampling: true,
        changeWorkspace: workspaceInfo.changeWorkspace,
        workspaceUUID: workspaceInfo.workspaceUUID,
        workspaceName: workspaceInfo.workspaceName,
        showFieldMapping: false,
        openThousandsSeparator: true,
        precision: typeof precision === 'number' ? String(precision) : '2',
        timeInterval: normalizeTimeInterval(firstDefined(panel.interval, (_k = (_j = panel.targets) === null || _j === void 0 ? void 0 : _j.find((item) => item.interval)) === null || _k === void 0 ? void 0 : _k.interval, 'auto')),
        fixedTime: panel.timeFrom || '',
        maxPointCount: (_l = panel.maxDataPoints) !== null && _l !== void 0 ? _l : undefined,
        showLegend: legend.showLegend,
        legendPostion: mapLegendPlacement(legend.placement),
        legendValues,
        showLegend: firstDefined(legend.showLegend, legend.show),
        showLine: chartType === 'sequence' ? inferShowLine(panel, custom) : undefined,
        lineType: mapLineInterpolation(custom.lineInterpolation),
        connectNulls,
        openStack: inferOpenStack(panel, custom),
        stackType: mapStackType(firstDefined((_m = custom.stacking) === null || _m === void 0 ? void 0 : _m.mode, panel.stack ? 'normal' : 'none')),
        chartType: inferDisplayChartType(panel, chartType),
        isTimeInterval: chartType === 'sequence' || chartType === 'bar' || chartType === 'heatmap' || chartType === 'histogram',
        xAxisShowType: chartType === 'sequence' ? 'time' : chartType === 'bar' ? 'groupBy' : undefined,
        unitType: effectiveUnitType,
        globalUnit: customUnits.length ? undefined : mapUnit(unit),
        units: customUnits.length ? customUnits : undefined,
        colors: customColors.length ? customColors : undefined,
        colorMappings: colorMappings.length ? colorMappings : undefined,
        levels,
        slimit,
        mappings: mappingItems,
        alias: aliases,
        min,
        max,
        showPercent: Array.isArray(options.displayLabels) ? options.displayLabels.includes('percent') : undefined,
        showLabel: chartType === 'pie' ? Array.isArray(options.displayLabels) && options.displayLabels.length > 0 : undefined,
        showLabelValue: Array.isArray(options.displayLabels)
            ? options.displayLabels.includes('value') || options.displayLabels.includes('name')
            : undefined,
        direction: normalizeChartDirection(options.orientation, chartType),
        queryMode: chartType === 'table' ? 'toGroupColumn' : undefined,
        showTableHead: chartType === 'table' ? options.showHeader !== false : undefined,
        pageEnable: chartType === 'table' ? false : undefined,
        pageSize: chartType === 'table' ? 20 : undefined,
        showColumns: chartType === 'table' ? tableColumns.map((column) => column.title || column.field) : undefined,
        valMappings: chartType === 'table' ? buildTableMappings(panel.fieldConfig, transformationInfo.organize) : undefined,
        valColorMappings: chartType === 'table' && valColorMappings.length ? valColorMappings : undefined,
        legendValueOpen: Array.isArray(legend.values) ? legend.values.includes('value') : undefined,
        legendValuePercentOpen: Array.isArray(legend.values) ? legend.values.includes('percent') : undefined,
        showTopSize: chartType === 'toplist' ? true : undefined,
        topSize: chartType === 'toplist' ? extractReduceLimit(options) : undefined,
        scientificNotation: unit === 'short' ? true : undefined,
        mainMeasurementQueryCode: ((_p = (_o = queries[0]) === null || _o === void 0 ? void 0 : _o.query) === null || _p === void 0 ? void 0 : _p.code) || undefined,
        mainMeasurementLimit: chartType === 'pie' ? extractReduceLimit(options) : undefined,
        color: ((_r = defaults.color) === null || _r === void 0 ? void 0 : _r.fixedColor) || undefined,
        fontColor: options.colorMode === 'value' ? (_s = defaults.color) === null || _s === void 0 ? void 0 : _s.fixedColor : undefined,
        bgColor: options.colorMode === 'background' ? (_t = defaults.color) === null || _t === void 0 ? void 0 : _t.fixedColor : undefined,
        sequenceChartType: chartType === 'singlestat' && graphMode ? inferSequenceChartType(panel, graphMode) : undefined,
        showLineAxis: chartType === 'singlestat' ? graphMode !== 'none' : undefined,
        repeatChartVariable: typeof panel.repeat === 'string' && panel.repeat && variableNames.has(panel.repeat) ? panel.repeat : undefined,
        repeatChartRowLimit: typeof panel.maxPerRow === 'number' ? panel.maxPerRow : undefined,
        compares: compareInfo.compares,
        compareType: compareInfo.compareType,
        openCompare: compareInfo.openCompare,
        compareChartType: compareInfo.compareChartType,
        mainMeasurementSort: sortInfo.mainMeasurementSort,
        sorderByOrder: sortInfo.sorderByOrder,
    };
    const links = extractPanelLinks(panel);
    if (links.length) {
        settings.queryCodes = queries.map((query) => { var _a; return (_a = query.query) === null || _a === void 0 ? void 0 : _a.code; }).filter(Boolean);
    }
    settings.extend = pruneEmpty({
        appearance: pruneEmpty({
            lineWidth,
            fillOpacity,
            gradientMode: custom.gradientMode || undefined,
            pointMode,
            pointSize: firstDefinedNumber(custom.pointSize, panel.pointradius),
            axisPlacement: custom.axisPlacement || undefined,
            axisLabel: custom.axisLabel || undefined,
            axisColorMode: custom.axisColorMode || undefined,
            axisCenteredZero: typeof custom.axisCenteredZero === 'boolean' ? custom.axisCenteredZero : undefined,
            axisSoftMin: numberOrUndefined(custom.axisSoftMin),
            axisSoftMax: numberOrUndefined(custom.axisSoftMax),
            barAlignment: numberOrUndefined(custom.barAlignment),
            scaleDistribution: custom.scaleDistribution || undefined,
            drawStyle: custom.drawStyle || undefined,
            lineStyle: custom.lineStyle || undefined,
            spanNulls: custom.spanNulls,
            stackingGroup: ((_u = custom.stacking) === null || _u === void 0 ? void 0 : _u.group) || undefined,
            graphMode,
            colorMode: options.colorMode || undefined,
            fieldColorMode: ((_v = defaults.color) === null || _v === void 0 ? void 0 : _v.mode) || undefined,
            fixedColor: ((_w = defaults.color) === null || _w === void 0 ? void 0 : _w.fixedColor) || undefined,
            thresholdsMode: ((_x = defaults.thresholds) === null || _x === void 0 ? void 0 : _x.mode) || undefined,
            thresholdsStyleMode: ((_y = custom.thresholdsStyle) === null || _y === void 0 ? void 0 : _y.mode) || undefined,
            textMode: options.textMode || legacyTextMode,
            reduceCalcs: Array.isArray(reduceOptions.calcs) ? reduceOptions.calcs : undefined,
            reduceFields: reduceOptions.fields || undefined,
            reduceValues: typeof reduceOptions.values === 'boolean' ? reduceOptions.values : undefined,
            pieType: options.pieType || undefined,
            gaugeMode: chartType === 'gauge' || panel.type === 'singlestat' ? inferGaugeMode(panel, options, legacyGauge) : undefined,
            thresholdMarkers: typeof legacyGauge.thresholdMarkers === 'boolean' ? legacyGauge.thresholdMarkers : undefined,
            thresholdLabels: typeof legacyGauge.thresholdLabels === 'boolean' ? legacyGauge.thresholdLabels : undefined,
            hideFrom: custom.hideFrom || undefined,
            justifyMode: options.justifyMode || undefined,
            titleSize: typeof statText.titleSize === 'number' ? statText.titleSize : undefined,
            valueSize: typeof statText.valueSize === 'number' ? statText.valueSize : undefined,
        }),
        legend: pruneEmpty({
            displayMode: legend.displayMode || undefined,
            sortBy: legend.sortBy || legend.sort || undefined,
            sortDesc: typeof legend.sortDesc === 'boolean' ? legend.sortDesc : undefined,
            width: firstDefinedNumber(legend.width, legend.sideWidth),
        }),
        tooltip: pruneEmpty({
            mode: tooltip.mode || tooltip.sharedMode || undefined,
            sort: tooltip.sort || tooltip.value_type || undefined,
        }),
        table: chartType === 'table'
            ? pruneEmpty({
                align: tableCustom.align || undefined,
                displayMode: tableCustom.displayMode || undefined,
                sortBy: tableSortBy,
                footer: pruneEmpty({
                    fields: tableFooter.fields || undefined,
                    reducer: Array.isArray(tableFooter.reducer) ? tableFooter.reducer : undefined,
                    show: typeof tableFooter.show === 'boolean' ? tableFooter.show : undefined,
                }),
            })
            : undefined,
        text: textInfo || undefined,
        tableColumns: chartType === 'table' && tableColumns.length ? tableColumns : undefined,
        fieldOverrides: converterOptions.keepGrafanaMeta && fieldOverrides.length ? fieldOverrides : undefined,
        transformations: converterOptions.keepGrafanaMeta && transformationInfo.normalized.length ? transformationInfo.normalized : undefined,
        fieldFilterPattern: converterOptions.keepGrafanaMeta ? transformationInfo.fieldFilterPattern || undefined : undefined,
        valueFilters: converterOptions.keepGrafanaMeta && transformationInfo.valueFilters.length ? transformationInfo.valueFilters : undefined,
        layout: pruneEmpty({
            repeatDirection: panel.repeatDirection || undefined,
        }),
        aliasReview: converterOptions.keepGrafanaMeta ? aliasInfo.review : undefined,
    });
    return pruneEmpty(settings);
}
function buildLevels(thresholds, chartType, options = {}) {
    if (chartType === 'gauge') {
        return buildGaugeLevels(thresholds, options.max);
    }
    if (chartType === 'singlestat') {
        return buildSinglestatLevels(thresholds, options.fontColor);
    }
    return buildGenericLevels(thresholds);
}
function buildGenericLevels(thresholds) {
    const steps = Array.isArray(thresholds === null || thresholds === void 0 ? void 0 : thresholds.steps) ? thresholds.steps : [];
    return steps
        .filter((step) => typeof normalizeLevelNumber(step.value) === 'number' || typeof step.color === 'string')
        .map((step, index) => ({
        title: `Level ${index + 1}`,
        value: normalizeLevelNumber(step.value) !== undefined ? normalizeLevelNumber(step.value) : 0,
        bgColor: normalizeColor(step.color),
    }));
}
function buildGaugeLevels(thresholds, max) {
    const steps = Array.isArray(thresholds === null || thresholds === void 0 ? void 0 : thresholds.steps) ? thresholds.steps : [];
    const levels = [];
    for (let index = 0; index < steps.length; index++) {
        const current = steps[index];
        const next = steps[index + 1];
        const nextValue = normalizeLevelNumber(next === null || next === void 0 ? void 0 : next.value);
        const fallbackMax = normalizeLevelNumber(max);
        const currentValue = normalizeLevelNumber(current === null || current === void 0 ? void 0 : current.value);
        const upperBound = nextValue !== undefined ? nextValue : fallbackMax !== undefined ? fallbackMax : currentValue;
        if (upperBound === undefined)
            continue;
        levels.push(pruneEmpty({
            value: [upperBound],
            lineColor: normalizeColor(current === null || current === void 0 ? void 0 : current.color),
            operation: '<=',
        }));
    }
    return levels;
}
function buildSinglestatLevels(thresholds, fontColor) {
    const steps = Array.isArray(thresholds === null || thresholds === void 0 ? void 0 : thresholds.steps) ? thresholds.steps : [];
    const levels = [];
    for (let index = 0; index < steps.length; index++) {
        const current = steps[index];
        const next = steps[index + 1];
        const currentValue = normalizeLevelNumber(current === null || current === void 0 ? void 0 : current.value);
        const nextValue = normalizeLevelNumber(next === null || next === void 0 ? void 0 : next.value);
        const color = normalizeColor(current === null || current === void 0 ? void 0 : current.color);
        if (currentValue === undefined && nextValue === undefined)
            continue;
        if (currentValue === undefined && nextValue !== undefined) {
            levels.push({
                value: [nextValue],
                bgColor: color,
                fontColor: fontColor || color,
                operation: '<',
            });
            continue;
        }
        if (currentValue !== undefined && nextValue !== undefined) {
            levels.push({
                value: [currentValue, nextValue],
                bgColor: color,
                fontColor: fontColor || color,
                operation: 'between',
            });
            continue;
        }
        levels.push({
            value: [currentValue],
            bgColor: color,
            fontColor: fontColor || color,
            operation: '>=',
        });
    }
    return levels;
}
function normalizeLevelNumber(value) {
    if (typeof value !== 'number' || !Number.isFinite(value))
        return undefined;
    return Math.round(value);
}
function buildMappings(mappings) {
    var _a;
    if (!Array.isArray(mappings))
        return [];
    const result = [];
    for (const mapping of mappings) {
        if (mapping.type === 'value' && mapping.options && typeof mapping.options === 'object') {
            for (const [rawValue, item] of Object.entries(mapping.options)) {
                result.push({
                    originalVal: [rawValue],
                    operation: '=',
                    mappingVal: item.text || rawValue,
                });
            }
        }
        if (mapping.type === 'range' && mapping.options) {
            const from = mapping.options.from;
            const to = mapping.options.to;
            result.push({
                originalVal: [String(from !== null && from !== void 0 ? from : ''), String(to !== null && to !== void 0 ? to : '')],
                operation: 'between',
                mappingVal: ((_a = mapping.options.result) === null || _a === void 0 ? void 0 : _a.text) || '',
            });
        }
    }
    return result;
}
function buildTableMappings(fieldConfig, organize) {
    var _a;
    const overrideMappings = [];
    const overrides = Array.isArray(fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.overrides) ? fieldConfig.overrides : [];
    const organizeMaps = createOrganizeMaps(organize);
    for (const override of overrides) {
        const field = (_a = override.matcher) === null || _a === void 0 ? void 0 : _a.options;
        if (!field)
            continue;
        const displayField = resolveDisplayFieldName(field, organizeMaps);
        const properties = Array.isArray(override.properties) ? override.properties : [];
        for (const property of properties) {
            if (property.id !== 'mappings')
                continue;
            const mappings = buildMappings(property.value);
            for (const mapping of mappings) {
                overrideMappings.push({
                    field: displayField,
                    ...mapping,
                });
            }
        }
    }
    return overrideMappings;
}
function buildTableColumns(fieldConfig, organize, variableNames = new Set()) {
    var _a, _b;
    const columns = new Map();
    const defaultCustom = ((_a = fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.defaults) === null || _a === void 0 ? void 0 : _a.custom) || {};
    const overrides = Array.isArray(fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.overrides) ? fieldConfig.overrides : [];
    const organizeMaps = createOrganizeMaps(organize);
    const { renamedFields, excludedFields, indexedFields } = organizeMaps;
    for (const override of overrides) {
        const rawField = (_b = override.matcher) === null || _b === void 0 ? void 0 : _b.options;
        if (!rawField)
            continue;
        const field = resolveRawFieldName(rawField, organizeMaps);
        if (excludedFields[field] === true || excludedFields[rawField] === true)
            continue;
        const columnKey = resolveDisplayFieldName(field, organizeMaps);
        const currentColumn = columns.get(columnKey) || {
            field,
            title: columnKey,
            order: typeof indexedFields[field] === 'number' ? indexedFields[field] : undefined,
            align: defaultCustom.align || undefined,
            displayMode: defaultCustom.displayMode || undefined,
        };
        for (const property of override.properties || []) {
            if (property.id === 'custom.width') {
                currentColumn.width = property.value;
            }
            if (property.id === 'custom.align') {
                currentColumn.align = property.value;
            }
            if (property.id === 'custom.displayMode') {
                currentColumn.displayMode = property.value;
            }
            if (property.id === 'links') {
                currentColumn.links = Array.isArray(property.value)
                    ? property.value.map((link) => normalizeGuanceLinkItem(link, variableNames))
                    : undefined;
            }
            if (property.id === 'mappings') {
                currentColumn.mappings = buildMappings(property.value);
            }
        }
        columns.set(columnKey, pruneEmpty(currentColumn));
    }
    if (organize) {
        for (const [field, order] of Object.entries(indexedFields)) {
            if (excludedFields[field] === true)
                continue;
            const columnKey = resolveDisplayFieldName(field, organizeMaps);
            if (columns.has(columnKey)) {
                const currentColumn = columns.get(columnKey);
                currentColumn.field = field;
                currentColumn.order = typeof order === 'number' ? order : currentColumn.order;
                currentColumn.title = columnKey;
                columns.set(columnKey, pruneEmpty(currentColumn));
                continue;
            }
            columns.set(columnKey, pruneEmpty({
                field,
                title: columnKey,
                order: typeof order === 'number' ? order : undefined,
            }));
        }
    }
    return finalizeTableColumns([...columns.values()]);
}
function buildAliases(queries, fieldConfig, variableNames = new Set()) {
    const aliases = [];
    const seen = new Set();
    const review = [];
    const queryAliasTargets = buildQueryAliasTargets(queries);
    for (const queryAliasTarget of queryAliasTargets) {
        if (!queryAliasTarget.alias)
            continue;
        const aliasItem = pruneEmpty({
            alias: queryAliasTarget.alias,
            key: queryAliasTarget.key,
            name: queryAliasTarget.name,
            queryCode: queryAliasTarget.queryCode,
        });
        pushAliasItem(aliases, seen, aliasItem);
        pushAliasReviewItem(review, aliasItem.alias, aliasItem.key);
    }
    const overrides = Array.isArray(fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.overrides) ? fieldConfig.overrides : [];
    for (const override of overrides) {
        const matcherId = String((override === null || override === void 0 ? void 0 : override.matcher) && override.matcher.id || '');
        const matcherOptions = String((override === null || override === void 0 ? void 0 : override.matcher) && override.matcher.options || '').trim();
        if (matcherId !== 'byName' || !matcherOptions)
            continue;
        for (const property of Array.isArray(override === null || override === void 0 ? void 0 : override.properties) ? override.properties : []) {
            if (!['displayName', 'displayNameFromDS'].includes(property === null || property === void 0 ? void 0 : property.id))
                continue;
            if (typeof property.value !== 'string' || !property.value.trim())
                continue;
            const aliasItem = {
                alias: replaceVariables(property.value, variableNames),
                key: matcherOptions,
                name: matcherOptions,
            };
            pushAliasItem(aliases, seen, aliasItem);
            pushAliasReviewItem(review, aliasItem.alias, aliasItem.key);
        }
    }
    return {
        items: aliases,
        review: review.length ? review : undefined,
    };
}
function pushAliasItem(aliases, seen, aliasItem) {
    const normalized = pruneEmpty(aliasItem);
    if (!(normalized === null || normalized === void 0 ? void 0 : normalized.alias) || !(normalized === null || normalized === void 0 ? void 0 : normalized.key) || !(normalized === null || normalized === void 0 ? void 0 : normalized.name))
        return;
    const key = JSON.stringify(normalized);
    if (seen.has(key))
        return;
    seen.add(key);
    aliases.push(normalized);
}
function buildQueryAliasTargets(queries) {
    const targets = [];
    for (let index = 0; index < (Array.isArray(queries) ? queries : []).length; index++) {
        const query = queries[index];
        const alias = normalizeQueryAlias((query === null || query === void 0 ? void 0 : query.name) || '');
        if (!alias)
            continue;
        const queryInfo = (query === null || query === void 0 ? void 0 : query.query) || {};
        const qtype = typeof (query === null || query === void 0 ? void 0 : query.qtype) === 'string' ? query.qtype : 'query';
        const queryCode = typeof queryInfo.code === 'string' ? queryInfo.code : '';
        const key = buildAliasSeriesKey(qtype, queryInfo, index);
        targets.push({
            alias,
            key,
            name: key,
            queryCode: queryCode || undefined,
        });
    }
    return targets;
}
function buildAliasSeriesKey(qtype, queryInfo, index) {
    const normalizedType = typeof qtype === 'string' && qtype.trim() ? qtype.trim() : 'query';
    if (normalizedType === 'promql') {
        const promqlCode = Number.isInteger(queryInfo === null || queryInfo === void 0 ? void 0 : queryInfo.promqlCode) ? queryInfo.promqlCode : index + 1;
        return `promql_${promqlCode}`;
    }
    return `${normalizedType}_${index + 1}`;
}
function normalizeQueryAlias(value) {
    const alias = String(value || '').trim();
    if (!alias || alias === '__auto')
        return '';
    return alias;
}
function pushAliasReviewItem(review, alias, key) {
    const normalizedAlias = String(alias || '').trim();
    const normalizedKey = String(key || '').trim();
    if (!normalizedAlias || !normalizedKey)
        return;
    const classification = classifyAliasTemplate(normalizedAlias);
    if (classification === 'safe_fixed')
        return;
    const item = {
        alias: normalizedAlias,
        key: normalizedKey,
        classification,
    };
    const serialized = JSON.stringify(item);
    if (review.some((current) => JSON.stringify(current) === serialized))
        return;
    review.push(item);
}
function classifyAliasTemplate(alias) {
    if (!alias.includes('{{'))
        return 'safe_fixed';
    const tokens = [...alias.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)].map((match) => match[1].trim());
    if (tokens.length === 0)
        return 'safe_fixed';
    if (tokens.every((token) => token === 'host' || token === 'tags'))
        return 'safe_guance';
    return 'compat_grafana_template';
}
function buildCustomUnits(fieldConfig) {
    var _a;
    const overrides = Array.isArray(fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.overrides) ? fieldConfig.overrides : [];
    const units = [];
    for (const override of overrides) {
        const rawKey = String(((_a = override === null || override === void 0 ? void 0 : override.matcher) === null || _a === void 0 ? void 0 : _a.options) || '').trim();
        if (!rawKey)
            continue;
        const unitProperty = Array.isArray(override === null || override === void 0 ? void 0 : override.properties)
            ? override.properties.find((property) => (property === null || property === void 0 ? void 0 : property.id) === 'unit')
            : undefined;
        if (!unitProperty || typeof unitProperty.value !== 'string')
            continue;
        const unit = unitProperty.value;
        units.push(pruneEmpty({
            key: rawKey,
            name: rawKey,
            unit,
            units: mapUnit(unit),
        }));
    }
    return units;
}
function buildCustomColors(fieldConfig) {
    var _a, _b, _c;
    const overrides = Array.isArray(fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.overrides) ? fieldConfig.overrides : [];
    const colors = [];
    for (const override of overrides) {
        const rawKey = String(((_a = override === null || override === void 0 ? void 0 : override.matcher) === null || _a === void 0 ? void 0 : _a.options) || '').trim();
        if (!rawKey)
            continue;
        const colorProperty = Array.isArray(override === null || override === void 0 ? void 0 : override.properties)
            ? override.properties.find((property) => (property === null || property === void 0 ? void 0 : property.id) === 'color')
            : undefined;
        const fixedColor = (_b = colorProperty === null || colorProperty === void 0 ? void 0 : colorProperty.value) === null || _b === void 0 ? void 0 : _b.fixedColor;
        const colorMode = (_c = colorProperty === null || colorProperty === void 0 ? void 0 : colorProperty.value) === null || _c === void 0 ? void 0 : _c.mode;
        if (typeof fixedColor !== 'string' || !fixedColor)
            continue;
        if (colorMode && colorMode !== 'fixed')
            continue;
        colors.push(pruneEmpty({
            key: rawKey,
            name: rawKey,
            color: normalizeColor(fixedColor),
        }));
    }
    return colors;
}
function buildColorMappings(fieldConfig, chartType) {
    var _a, _b;
    if (chartType !== 'toplist')
        return [];
    const steps = Array.isArray((_b = (_a = fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.defaults) === null || _a === void 0 ? void 0 : _a.thresholds) === null || _b === void 0 ? void 0 : _b.steps) ? fieldConfig.defaults.thresholds.steps : [];
    if (steps.length === 0)
        return [];
    const mappings = [];
    for (let index = 0; index < steps.length; index++) {
        const current = steps[index];
        const next = steps[index + 1];
        const bgColor = normalizeColor(current === null || current === void 0 ? void 0 : current.color);
        const start = current === null || current === void 0 ? void 0 : current.value;
        const end = next === null || next === void 0 ? void 0 : next.value;
        if (typeof start === 'number' && typeof end === 'number') {
            mappings.push({
                value: [start, end],
                bgColor,
                operation: 'between',
            });
            continue;
        }
        if (typeof start === 'number') {
            mappings.push({
                value: [start],
                bgColor,
                operation: '>=',
            });
            continue;
        }
        if (typeof end === 'number') {
            mappings.push({
                value: [end],
                bgColor,
                operation: '<',
            });
        }
    }
    return mappings;
}
function buildValColorMappings(fieldConfig, organize) {
    var _a, _b;
    const overrides = Array.isArray(fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.overrides) ? fieldConfig.overrides : [];
    const organizeMaps = createOrganizeMaps(organize);
    const mappings = [];
    for (const override of overrides) {
        const rawField = (_a = override === null || override === void 0 ? void 0 : override.matcher) === null || _a === void 0 ? void 0 : _a.options;
        if (!rawField)
            continue;
        const field = resolveDisplayFieldName(resolveRawFieldName(rawField, organizeMaps), organizeMaps);
        const properties = Array.isArray(override === null || override === void 0 ? void 0 : override.properties) ? override.properties : [];
        const mappingProperty = properties.find((property) => (property === null || property === void 0 ? void 0 : property.id) === 'mappings');
        if (!mappingProperty)
            continue;
        const colorProperty = properties.find((property) => (property === null || property === void 0 ? void 0 : property.id) === 'color');
        const fixedColor = typeof ((_b = colorProperty === null || colorProperty === void 0 ? void 0 : colorProperty.value) === null || _b === void 0 ? void 0 : _b.fixedColor) === 'string' ? normalizeColor(colorProperty.value.fixedColor) : '';
        const tableMappings = buildMappings(mappingProperty.value);
        for (const mapping of tableMappings) {
            mappings.push(pruneEmpty({
                field,
                value: mapping.originalVal,
                bgColor: '',
                fontColor: fixedColor,
                lineColor: '',
                operation: mapping.operation,
            }));
        }
    }
    return mappings;
}
function buildFieldOverrides(fieldConfig, variableNames = new Set()) {
    var _a, _b;
    const overrides = Array.isArray(fieldConfig === null || fieldConfig === void 0 ? void 0 : fieldConfig.overrides) ? fieldConfig.overrides : [];
    const normalized = [];
    for (const override of overrides) {
        const properties = Array.isArray(override.properties) ? override.properties : [];
        const normalizedProperties = properties
            .map((property) => normalizeOverrideProperty(property, variableNames))
            .filter(Boolean);
        if (normalizedProperties.length === 0)
            continue;
        normalized.push(pruneEmpty({
            matcher: pruneEmpty({
                id: ((_a = override.matcher) === null || _a === void 0 ? void 0 : _a.id) || undefined,
                options: (_b = override.matcher) === null || _b === void 0 ? void 0 : _b.options,
            }),
            properties: normalizedProperties,
        }));
    }
    return normalized;
}
function normalizeOverrideProperty(property, variableNames = new Set()) {
    if (!(property === null || property === void 0 ? void 0 : property.id))
        return undefined;
    if (property.id === 'links') {
        return pruneEmpty({
            id: property.id,
            value: Array.isArray(property.value)
                ? property.value.map((link) => normalizeGuanceLinkItem(link, variableNames))
                : undefined,
        });
    }
    return pruneEmpty({
        id: property.id,
        value: property.value,
    });
}
function analyzeTextPanel(content, mode) {
    if (typeof content !== 'string' || !content.trim())
        return undefined;
    const normalizedMode = typeof mode === 'string' ? mode : undefined;
    const containsScript = /<script\b/i.test(content);
    const containsHtml = /<[a-z][\s\S]*>/i.test(content);
    const contentKind = containsScript ? 'interactive_html' : containsHtml ? 'html' : 'markdown';
    const actions = extractTextActions(content);
    return pruneEmpty({
        mode: normalizedMode,
        contentKind,
        containsScript: containsScript || undefined,
        actions: actions.length ? actions : undefined,
    });
}
function extractTextActions(content) {
    var _a, _b;
    const actions = [];
    const seen = new Set();
    const anchorRegex = /<a\b[^>]*href=(['"])(.*?)\1[^>]*>([\s\S]*?)<\/a>/gi;
    for (const match of content.matchAll(anchorRegex)) {
        const url = (match[2] || '').trim();
        const label = stripHtmlTags(match[3] || '').trim();
        pushTextAction(actions, seen, {
            title: label || undefined,
            url: url || undefined,
            open: url === '#' ? 'curWin' : 'newWin',
            type: inferGuanceLinkType({ title: label, url }),
            show: true,
            showChanged: false,
        });
    }
    const constUrlRegex = /\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*([`'"])([\s\S]*?)\2\s*;/g;
    const constantUrls = new Map();
    for (const match of content.matchAll(constUrlRegex)) {
        constantUrls.set(match[1], match[3]);
    }
    const windowOpenRegex = /window\.open\(\s*([A-Za-z_$][A-Za-z0-9_$]*|[`'"][\s\S]*?[`'"])\s*(?:,\s*([`'"][\s\S]*?[`'"]))?\s*\)/g;
    for (const match of content.matchAll(windowOpenRegex)) {
        const rawTarget = ((_a = match[1]) === null || _a === void 0 ? void 0 : _a.trim()) || '';
        const rawBlank = ((_b = match[2]) === null || _b === void 0 ? void 0 : _b.trim()) || '';
        const directUrl = unwrapQuoted(rawTarget);
        const variableUrl = constantUrls.get(rawTarget);
        const url = directUrl || variableUrl;
        pushTextAction(actions, seen, {
            title: inferActionTitle(content, url),
            url: url || undefined,
            open: rawBlank.includes('_blank') ? 'newWin' : 'curWin',
            type: inferGuanceLinkType({ title: inferActionTitle(content, url), url }),
            show: true,
            showChanged: false,
        });
    }
    return actions;
}
function pushTextAction(actions, seen, action) {
    const normalized = pruneEmpty(action);
    const key = JSON.stringify(normalized);
    if (!key || seen.has(key) || Object.keys(normalized).length === 0)
        return;
    seen.add(key);
    actions.push(normalized);
}
function inferActionTitle(content, url) {
    if (typeof url !== 'string' || !url)
        return undefined;
    if (content.includes('HotCall') || url.includes('hotcall'))
        return 'HotCall';
    if (content.includes('业务大盘'))
        return '业务大盘';
    if (content.includes('拓扑图') || content.includes('traceLink'))
        return '跳转观测云';
    return undefined;
}
function unwrapQuoted(value) {
    if (typeof value !== 'string')
        return '';
    const trimmed = value.trim();
    if (trimmed.length < 2)
        return '';
    const quote = trimmed[0];
    if ((quote === '"' || quote === "'" || quote === '`') && trimmed.at(-1) === quote) {
        return trimmed.slice(1, -1);
    }
    return '';
}
function stripHtmlTags(value) {
    return String(value).replace(/<[^>]+>/g, ' ');
}
function normalizeColumnTitle(field, renamedField) {
    if (typeof renamedField === 'string' && renamedField.trim())
        return renamedField.trim();
    return field;
}
function finalizeTableColumns(columns) {
    const mergedColumns = new Map();
    for (const column of columns) {
        const key = column.title || column.field;
        const existing = mergedColumns.get(key);
        if (!existing) {
            mergedColumns.set(key, { ...column });
            continue;
        }
        mergedColumns.set(key, pruneEmpty({
            ...existing,
            ...column,
            field: existing.field || column.field,
            title: key,
            order: Math.min(numberOr(existing.order, Number.MAX_SAFE_INTEGER), numberOr(column.order, Number.MAX_SAFE_INTEGER)),
            width: firstDefined(existing.width, column.width),
            align: firstDefined(existing.align, column.align),
            displayMode: firstDefined(existing.displayMode, column.displayMode),
            links: existing.links || column.links,
            mappings: existing.mappings || column.mappings,
        }));
    }
    return [...mergedColumns.values()].sort((left, right) => numberOr(left.order, Number.MAX_SAFE_INTEGER) - numberOr(right.order, Number.MAX_SAFE_INTEGER));
}
function createOrganizeMaps(organize) {
    const renamedFields = (organize === null || organize === void 0 ? void 0 : organize.renameByName) || {};
    const excludedFields = (organize === null || organize === void 0 ? void 0 : organize.excludeByName) || {};
    const indexedFields = (organize === null || organize === void 0 ? void 0 : organize.indexByName) || {};
    const displayToRaw = {};
    for (const [rawField, renamedField] of Object.entries(renamedFields)) {
        const title = normalizeColumnTitle(rawField, renamedField);
        if (title && title !== rawField) {
            displayToRaw[title] = rawField;
        }
    }
    return {
        renamedFields,
        excludedFields,
        indexedFields,
        displayToRaw,
    };
}
function resolveRawFieldName(field, organizeMaps) {
    return organizeMaps.displayToRaw[field] || field;
}
function resolveDisplayFieldName(field, organizeMaps) {
    return normalizeColumnTitle(field, organizeMaps.renamedFields[field]);
}
function parseTransformations(transformations) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l;
    const normalized = [];
    let organize = null;
    let fieldFilterPattern = '';
    const valueFilters = [];
    for (const transformation of Array.isArray(transformations) ? transformations : []) {
        if (!(transformation === null || transformation === void 0 ? void 0 : transformation.id))
            continue;
        if (transformation.id === 'organize') {
            organize = transformation.options || {};
            normalized.push(pruneEmpty({
                type: 'organize',
                renameByName: organize.renameByName,
                excludeByName: organize.excludeByName,
                indexByName: organize.indexByName,
            }));
            continue;
        }
        if (transformation.id === 'filterFieldsByName') {
            fieldFilterPattern = ((_b = (_a = transformation.options) === null || _a === void 0 ? void 0 : _a.include) === null || _b === void 0 ? void 0 : _b.pattern) || ((_d = (_c = transformation.options) === null || _c === void 0 ? void 0 : _c.exclude) === null || _d === void 0 ? void 0 : _d.pattern) || '';
            normalized.push(pruneEmpty({
                type: 'filterFieldsByName',
                include: (_e = transformation.options) === null || _e === void 0 ? void 0 : _e.include,
                exclude: (_f = transformation.options) === null || _f === void 0 ? void 0 : _f.exclude,
            }));
            continue;
        }
        if (transformation.id === 'filterByValue') {
            const filters = Array.isArray((_g = transformation.options) === null || _g === void 0 ? void 0 : _g.filters) ? transformation.options.filters : [];
            valueFilters.push(pruneEmpty({
                match: ((_h = transformation.options) === null || _h === void 0 ? void 0 : _h.match) || undefined,
                type: ((_j = transformation.options) === null || _j === void 0 ? void 0 : _j.type) || undefined,
                filters,
            }));
            normalized.push(pruneEmpty({
                type: 'filterByValue',
                match: ((_k = transformation.options) === null || _k === void 0 ? void 0 : _k.match) || undefined,
                mode: ((_l = transformation.options) === null || _l === void 0 ? void 0 : _l.type) || undefined,
                filters,
            }));
            continue;
        }
        normalized.push(pruneEmpty({
            type: transformation.id,
            options: transformation.options,
        }));
    }
    return {
        organize,
        fieldFilterPattern,
        valueFilters,
        normalized,
    };
}
function extractPanelLinks(panel, variableNames) {
    var _a, _b;
    const links = [];
    const defaults = ((_a = panel.fieldConfig) === null || _a === void 0 ? void 0 : _a.defaults) || {};
    const overrideLinks = Array.isArray((_b = panel.fieldConfig) === null || _b === void 0 ? void 0 : _b.overrides)
        ? panel.fieldConfig.overrides.flatMap((override) => (override.properties || [])
            .filter((property) => property.id === 'links')
            .flatMap((property) => property.value || []))
        : [];
    const allLinks = [
        ...(Array.isArray(panel.links) ? panel.links : []),
        ...(Array.isArray(defaults.links) ? defaults.links : []),
        ...overrideLinks,
    ];
    for (const link of allLinks) {
        if (!link || !link.url)
            continue;
        links.push(normalizeGuanceLinkItem(link, variableNames));
    }
    return links;
}
function normalizeGuanceLinkItem(link, variableNames = new Set()) {
    return pruneEmpty({
        url: replaceVariables(link.url || '', variableNames),
        open: Boolean(link.targetBlank) ? 'newWin' : 'curWin',
        show: true,
        type: inferGuanceLinkType(link),
        showChanged: false,
    });
}
function inferGuanceLinkType(link) {
    const title = String((link === null || link === void 0 ? void 0 : link.title) || '').toLowerCase();
    const url = String((link === null || link === void 0 ? void 0 : link.url) || '').toLowerCase();
    const combined = `${title} ${url}`;
    if (url.includes('pipeline-log'))
        return 'custom';
    if (url.includes('/tracing/'))
        return 'tracing';
    if (url.includes('/logindi/') || url.includes('/log/') || url.includes('/logging/'))
        return 'logging';
    if (url.includes('/objectadmin/docker_containers') || url.includes('/container'))
        return 'container';
    if (url.includes('/objectadmin/host_processes') || url.includes('/process'))
        return 'processes';
    if (url.includes('/scene/builtinview/detail') || url.includes('/host'))
        return 'host';
    if (title.includes('trace') || title.includes('tracing'))
        return 'tracing';
    if (title.includes('日志'))
        return 'logging';
    return 'custom';
}
function inferChartType(panel) {
    return PANEL_TYPE_MAP[panel.type] || null;
}
function inferDisplayChartType(panel, chartType) {
    var _a, _b, _c, _d, _e, _f, _g;
    if (chartType === 'pie') {
        return ((_a = panel.options) === null || _a === void 0 ? void 0 : _a.pieType) === 'donut' ? 'donut' : 'pie';
    }
    if (chartType === 'bar')
        return 'bar';
    if (chartType === 'toplist')
        return 'bar';
    const drawStyle = (_d = (_c = (_b = panel.fieldConfig) === null || _b === void 0 ? void 0 : _b.defaults) === null || _c === void 0 ? void 0 : _c.custom) === null || _d === void 0 ? void 0 : _d.drawStyle;
    const fillOpacity = (_g = (_f = (_e = panel.fieldConfig) === null || _e === void 0 ? void 0 : _e.defaults) === null || _f === void 0 ? void 0 : _f.custom) === null || _g === void 0 ? void 0 : _g.fillOpacity;
    if (drawStyle === 'bars')
        return 'bar';
    if (fillOpacity && fillOpacity > 0)
        return 'areaLine';
    return 'line';
}
function inferQueryLanguage(target, queryText) {
    const datasourceType = getDatasourceType(target.datasource);
    // Guance datasource defaults to DQL unless the Grafana target explicitly marks the query as PromQL.
    if (target.qtype === 'promql')
        return 'promql';
    if (target.qtype === 'dql')
        return 'dql';
    if (isSlsDatasource(datasourceType))
        return 'dql';
    if (datasourceType.includes('guance-guance-datasource'))
        return 'dql';
    if (isCloudwatchDatasource(datasourceType))
        return 'promql';
    if (isPrometheusLikeDatasource(datasourceType))
        return 'promql';
    if (isDqlLikeDatasource(datasourceType))
        return 'dql';
    if (/^\s*(with|select)\b/i.test(queryText))
        return 'dql';
    if (/^[A-Z]::/.test(queryText))
        return 'dql';
    return 'promql';
}
function inferVariableQueryType(variable) {
    var _a;
    const datasourceType = getDatasourceType(variable.datasource);
    const explicitQtype = String(((_a = variable.query) === null || _a === void 0 ? void 0 : _a.qtype) || '').toLowerCase();
    if (datasourceType.includes('object'))
        return 'FIELD';
    if (isMysqlDatasource(datasourceType))
        return 'OUTER_DATASOURCE';
    if (explicitQtype === 'promql')
        return 'PROMQL_QUERY';
    if (explicitQtype === 'dql')
        return 'QUERY';
    if (isSlsDatasource(datasourceType))
        return 'QUERY';
    if (isCloudwatchDatasource(datasourceType))
        return 'PROMQL_QUERY';
    if (isPrometheusLikeDatasource(datasourceType))
        return 'PROMQL_QUERY';
    if (isDqlLikeDatasource(datasourceType))
        return 'QUERY';
    return 'PROMQL_QUERY';
}
function extractVariableQuery(variable) {
    if (typeof variable.query === 'string')
        return variable.query;
    if (variable.query && typeof variable.query === 'object') {
        return (variable.query.rawQuery ||
            variable.query.query ||
            variable.query.expr ||
            variable.query.queryText ||
            variable.query.sql ||
            variable.query.queryString ||
            '');
    }
    if (typeof variable.definition === 'string')
        return variable.definition;
    return '';
}
function extractTargetQuery(target) {
    const candidates = [target.expr, target.query, target.queryText, target.expression, target.rawSql];
    for (const candidate of candidates) {
        if (typeof candidate === 'string' && candidate.trim())
            return candidate;
        if (candidate && typeof candidate === 'object') {
            const nestedQuery = extractNestedQuery(candidate);
            if (nestedQuery)
                return nestedQuery;
        }
    }
    const structuredCloudwatchQuery = buildCloudwatchStructuredTargetQuery(target);
    if (structuredCloudwatchQuery)
        return structuredCloudwatchQuery;
    return '';
}
function buildCloudwatchStructuredTargetQuery(target) {
    if (!isCloudwatchDatasource(getDatasourceType(target === null || target === void 0 ? void 0 : target.datasource))) {
        return '';
    }
    const metricName = String((target === null || target === void 0 ? void 0 : target.metricName) || '').trim();
    const namespace = String((target === null || target === void 0 ? void 0 : target.namespace) || '').trim();
    if (!metricName || !namespace) {
        return '';
    }
    const serviceMapping = getCloudwatchServiceMappingByNamespace(namespace);
    if (!serviceMapping) {
        return '';
    }
    const labelMatchers = [`metric_name="${escapePromqlLabelValue(metricName)}"`];
    const dimensions = (target === null || target === void 0 ? void 0 : target.dimensions) && typeof target.dimensions === 'object' ? target.dimensions : {};
    for (const [rawKey, rawValue] of Object.entries(dimensions)) {
        const label = String(rawKey || '').trim();
        const value = normalizeCloudwatchDimensionValue(rawValue);
        if (!label || !value) {
            continue;
        }
        const operator = inferCloudwatchMatcherOperator(value);
        labelMatchers.push(`${label}${operator}"${escapePromqlLabelValue(value)}"`);
    }
    return `cloudwatch_metric_${serviceMapping.service}{${labelMatchers.join(', ')}}`;
}
function extractNestedQuery(candidate) {
    return (candidate.rawQuery ||
        candidate.query ||
        candidate.expr ||
        candidate.queryText ||
        candidate.sql ||
        candidate.queryString ||
        candidate.searchQuery ||
        candidate.expression ||
        '');
}
function prepareVariableQuery(variable, options = {}) {
    return prepareDatasourceQuery(extractVariableQuery(variable), variable.datasource, variable, options, sanitizeVariableQuery);
}
function prepareTargetQuery(target, options = {}) {
    return prepareDatasourceQuery(extractTargetQuery(target), target.datasource, target, options, sanitizeTargetQuery);
}
function prepareDatasourceQuery(queryText, datasource, carrier, options = {}, sanitizer = (value) => value) {
    if (typeof queryText !== 'string' || !queryText.trim()) {
        return {
            queryText,
            conversionInfo: undefined,
            sqlConversionInfo: undefined,
            externalDatasourceInfo: undefined,
        };
    }
    const datasourceType = getDatasourceType(datasource);
    if (isSlsDatasource(datasourceType)) {
        const slsResult = convertSlsQueryToDql(queryText, carrier, options);
        return {
            queryText: sanitizer(slsResult.queryText, options),
            conversionInfo: slsResult.conversionInfo,
            sqlConversionInfo: undefined,
            externalDatasourceInfo: undefined,
        };
    }
    if (isElasticsearchDatasource(datasourceType)) {
        const elasticsearchResult = convertElasticsearchQueryToDql(queryText, carrier);
        return {
            queryText: sanitizer(elasticsearchResult.queryText, options),
            conversionInfo: undefined,
            sqlConversionInfo: undefined,
            externalDatasourceInfo: undefined,
        };
    }
    if (isMysqlDatasource(datasourceType)) {
        return {
            queryText: sanitizer(queryText, options),
            conversionInfo: undefined,
            sqlConversionInfo: undefined,
            externalDatasourceInfo: buildMysqlExternalDatasourceInfo(queryText, datasource, options),
        };
    }
    if (isSqlDatasource(datasourceType)) {
        return {
            queryText: sanitizer(queryText, options),
            conversionInfo: undefined,
            sqlConversionInfo: buildSqlConversionInfo(queryText, datasourceType),
            externalDatasourceInfo: undefined,
        };
    }
    return {
        queryText: sanitizer(queryText, options),
        conversionInfo: undefined,
        sqlConversionInfo: undefined,
        externalDatasourceInfo: undefined,
    };
}
function buildSqlConversionInfo(originalQuery, datasourceType) {
    return {
        tool: 'grafana-sql-pass-through',
        status: 'unsupported',
        unsupportedClass: 'manual-migration',
        datasourceType,
        originalQuery,
        diagnostics: [
            `[warning] SQL_DATASOURCE_PASSTHROUGH: ${datasourceType || 'sql'} raw SQL was preserved because the converter does not rewrite relational SQL into DQL`,
            'hint: Migrate this query manually or map it to an equivalent Guance data source before treating it as executable.',
        ],
    };
}
function buildMysqlExternalDatasourceInfo(originalQuery, datasource, options = {}) {
    const datasourceType = getDatasourceType(datasource) || 'mysql';
    const datasourceUid = typeof (datasource === null || datasource === void 0 ? void 0 : datasource.uid) === 'string' ? datasource.uid.trim() : '';
    const targetDatasource = resolveExternalDatasourceMapping(datasource, options);
    if (!targetDatasource) {
        return {
            tool: 'grafana-mysql-external-datasource-map',
            status: 'unsupported',
            unsupportedClass: 'manual-migration',
            datasourceType,
            datasourceUid: datasourceUid || undefined,
            originalQuery,
            diagnostics: [
                '[warning] MYSQL_EXTERNAL_DATASOURCE_UNMAPPED: mysql raw SQL could not be mapped to a Guance external datasource',
                'hint: Provide a mysql external datasource mapping before treating this query as executable.',
            ],
        };
    }
    return {
        tool: 'grafana-mysql-external-datasource-map',
        status: 'mapped',
        datasourceType,
        datasourceUid: datasourceUid || undefined,
        targetDatasource,
        originalQuery,
        diagnostics: [
            `[info] MYSQL_EXTERNAL_DATASOURCE_MAPPED: mysql raw SQL was mapped to external datasource ${targetDatasource}`,
        ],
    };
}
function resolveExternalDatasourceMapping(datasource, options = {}) {
    const mappings = options.sqlDatasourceMappings || {};
    const datasourceType = getDatasourceType(datasource);
    const datasourceUid = typeof (datasource === null || datasource === void 0 ? void 0 : datasource.uid) === 'string' ? datasource.uid.trim() : '';
    return (firstNonEmptyString(datasourceUid && mappings.byUid && mappings.byUid[datasourceUid], datasourceUid && mappings[datasourceUid], mappings.byType && mappings.byType[datasourceType], mappings[datasourceType], DEFAULT_EXTERNAL_DATASOURCE_MAPPINGS[datasourceType]) ||
        '');
}
function buildExternalDatasourceQuery(externalDatasourceInfo) {
    if (!externalDatasourceInfo || externalDatasourceInfo.status !== 'mapped' || !externalDatasourceInfo.targetDatasource) {
        return undefined;
    }
    return {
        id: externalDatasourceInfo.targetDatasource,
        type: externalDatasourceInfo.datasourceType || 'mysql',
        queryType: 'sql',
    };
}
function resolveExternalDatasourceMetric(externalDatasourceInfo) {
    if (!externalDatasourceInfo || externalDatasourceInfo.status !== 'mapped') {
        return '';
    }
    return externalDatasourceInfo.targetDatasource || '';
}
function normalizeMysqlOuterDatasourceSql(queryText) {
    const trimmed = String(queryText || '').trim();
    if (!trimmed) {
        return '';
    }
    const parsed = parseMysqlSelectStatement(trimmed);
    if (!parsed) {
        return buildMysqlFallbackOuterDatasourceSql(trimmed);
    }
    const normalizedSelect = normalizeMysqlSelectItems(parsed.selectClause, Boolean(parsed.restClause));
    const normalizedRest = formatMysqlOuterDatasourceRest(parsed.restClause, normalizedSelect.hasTime);
    const selectLines = normalizedSelect.items.map((item, index) => `    ${item}${index < normalizedSelect.items.length - 1 ? ',' : ''}`);
    return [
        'SELECT',
        ...selectLines,
        normalizedRest || undefined,
        'LIMIT 5000;',
        '',
    ]
        .filter((line) => line !== undefined && line !== null)
        .join('\n');
}
function parseMysqlSelectStatement(queryText) {
    const statement = stripSqlTrailingSemicolon(queryText);
    if (!/^\s*select\b/i.test(statement)) {
        return null;
    }
    const selectKeyword = statement.match(/^\s*select\b/i);
    const selectStart = selectKeyword ? selectKeyword[0].length : 0;
    const fromIndex = findTopLevelSqlKeyword(statement, 'from', selectStart);
    if (fromIndex < 0) {
        return {
            selectClause: statement.slice(selectStart).trim(),
            restClause: '',
        };
    }
    return {
        selectClause: statement.slice(selectStart, fromIndex).trim(),
        restClause: statement.slice(fromIndex).trim(),
    };
}
function normalizeMysqlSelectItems(selectClause, hasFromClause = false) {
    const rawItems = splitTopLevel(selectClause, ',');
    const valueItems = [];
    let timeItem = '';
    for (const rawItem of rawItems) {
        const normalized = normalizeMysqlSelectItem(rawItem);
        if (!normalized.sql) {
            continue;
        }
        if (normalized.isTime && !timeItem) {
            timeItem = normalized.sql;
            continue;
        }
        if (!normalized.isTime) {
            valueItems.push(normalized.sql);
        }
    }
    return {
        hasTime: Boolean(timeItem),
        items: [timeItem || buildMysqlDefaultTimeSelectItem(hasFromClause), ...valueItems],
    };
}
function buildMysqlDefaultTimeSelectItem(hasFromClause) {
    if (!hasFromClause) {
        return 'NULL AS time';
    }
    return `CAST(UNIX_TIMESTAMP(${DEFAULT_MYSQL_OUTER_DATASOURCE_TIME_FIELD}) * 1000 AS SIGNED) AS time`;
}
function normalizeMysqlSelectItem(rawItem) {
    const item = String(rawItem || '').trim();
    if (!item) {
        return { sql: '', isTime: false };
    }
    if (item === '*') {
        return { sql: '*', isTime: false };
    }
    const aliasInfo = extractMysqlSelectAlias(item);
    const expression = aliasInfo.expression;
    const alias = sanitizeMysqlAlias(aliasInfo.alias || inferMysqlAliasFromExpression(expression) || 'value');
    if (isMysqlTimeSelectItem(expression, alias)) {
        return {
            sql: `${normalizeMysqlTimeExpression(expression)} AS time`,
            isTime: true,
        };
    }
    if (alias.startsWith('tag_')) {
        return { sql: `${expression} AS ${alias}`, isTime: false };
    }
    if (shouldEmitMysqlFieldAsTag(expression, alias)) {
        return { sql: `${expression} AS tag_${alias}`, isTime: false };
    }
    return { sql: `${expression} AS ${alias}`, isTime: false };
}
function extractMysqlSelectAlias(item) {
    const asMatch = item.match(/^(.*?)(?:\s+AS\s+)(`[^`]+`|'[^']+'|"[^"]+"|[\p{L}\p{N}_\u4e00-\u9fa5]+)\s*$/iu);
    if (asMatch) {
        return {
            expression: asMatch[1].trim(),
            alias: asMatch[2],
        };
    }
    const quotedAliasMatch = item.match(/^(.*?)\s+(`[^`]+`|'[^']+'|"[^"]+")\s*$/u);
    if (quotedAliasMatch) {
        return {
            expression: quotedAliasMatch[1].trim(),
            alias: quotedAliasMatch[2],
        };
    }
    return {
        expression: item,
        alias: '',
    };
}
function inferMysqlAliasFromExpression(expression) {
    const trimmed = String(expression || '').trim();
    if (/^\d+(?:\.\d+)?$/u.test(trimmed)) {
        return 'value';
    }
    const identifierMatch = trimmed.match(/(?:^|\.)(`[^`]+`|[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fa5][\u4e00-\u9fa5A-Za-z0-9_]*)$/u);
    if (identifierMatch) {
        return identifierMatch[1];
    }
    return 'value';
}
function sanitizeMysqlAlias(alias) {
    return String(alias || '')
        .trim()
        .replace(/^`|`$/gu, '')
        .replace(/^'|'$/gu, '')
        .replace(/^"|"$/gu, '')
        .replace(/[^\p{L}\p{N}_\u4e00-\u9fa5]/gu, '_')
        .replace(/^_+|_+$/gu, '') || 'value';
}
function isMysqlTimeSelectItem(expression, alias) {
    const normalizedAlias = String(alias || '').toLowerCase();
    if (normalizedAlias === 'time') {
        return true;
    }
    return isMysqlDateTimeLikeExpression(expression);
}
function isMysqlDateTimeLikeExpression(expression) {
    const normalized = String(expression || '')
        .replace(/`/gu, '')
        .trim()
        .toLowerCase();
    if (/unix_timestamp\s*\(|\*\s*1000|\bcast\s*\(/i.test(normalized)) {
        return false;
    }
    const lastIdentifier = normalized.split('.').pop() || normalized;
    return (/^(time|timestamp|date|datetime)$/u.test(lastIdentifier) ||
        /(^|_)(create|created|update|updated|trigger|handle|start|end|event|occur|occurred|timestamp|datetime|date)_?time$/u.test(lastIdentifier));
}
function normalizeMysqlTimeExpression(expression) {
    const trimmed = String(expression || '').trim();
    if (/unix_timestamp\s*\(|\*\s*1000|\bcast\s*\(/i.test(trimmed)) {
        return trimmed;
    }
    if (isMysqlDateTimeLikeExpression(trimmed) && !/^time$/iu.test(trimmed.replace(/`/gu, '').split('.').pop() || '')) {
        return `CAST(UNIX_TIMESTAMP(${trimmed}) * 1000 AS SIGNED)`;
    }
    return trimmed;
}
function shouldEmitMysqlFieldAsTag(expression, alias) {
    const normalizedExpression = String(expression || '').toLowerCase();
    const normalizedAlias = String(alias || '').toLowerCase();
    if (normalizedExpression === '*' || normalizedAlias === 'value') {
        return false;
    }
    if (/^\d+(?:\.\d+)?$/u.test(normalizedExpression)) {
        return false;
    }
    if (/[()+\-*/%]/u.test(normalizedExpression)) {
        return false;
    }
    return !/(count|sum|avg|min|max|round|concat|timestampdiff|percent|percentage|ratio|rate|rows?|number|num|total|success|failure|false|true|result|duration|latency|cost|amount|size|bytes|action_time|elapsed|interval|period|行数|数量|次数|总数|比例|占比|耗时|时长|成功|失败)/iu.test(`${normalizedExpression} ${normalizedAlias}`);
}
function formatMysqlOuterDatasourceRest(restClause, hasTime) {
    const clauses = splitMysqlRestClauses(restClause);
    if (!hasTime && clauses.where) {
        clauses.where = removeMysqlGrafanaTimeRangeConditions(clauses.where);
    }
    const lines = [];
    if (clauses.from) {
        lines.push(`FROM ${clauses.from}`);
    }
    if (clauses.where) {
        lines.push('WHERE');
        lines.push(`    ${normalizeMysqlClauseKeywords(clauses.where)}`);
    }
    if (clauses.groupBy) {
        lines.push('GROUP BY');
        lines.push(`    ${normalizeMysqlClauseKeywords(clauses.groupBy)}`);
    }
    if (clauses.having) {
        lines.push('HAVING');
        lines.push(`    ${normalizeMysqlClauseKeywords(clauses.having)}`);
    }
    if (clauses.orderBy) {
        lines.push('ORDER BY');
        lines.push(`    ${normalizeMysqlClauseKeywords(clauses.orderBy)}`);
    }
    return lines.join('\n');
}
function splitMysqlRestClauses(restClause) {
    const restWithoutLimit = stripTopLevelMysqlLimit(restClause).trim();
    if (!restWithoutLimit) {
        return {};
    }
    const fromPrefix = restWithoutLimit.match(/^\s*from\b/i);
    const bodyStart = fromPrefix ? fromPrefix[0].length : 0;
    const clauseKeywords = [
        ['where', 'where'],
        ['group by', 'groupBy'],
        ['having', 'having'],
        ['order by', 'orderBy'],
    ];
    const positions = clauseKeywords
        .map(([keyword, key]) => ({
        keyword,
        key,
        index: findTopLevelSqlKeyword(restWithoutLimit, keyword, bodyStart),
    }))
        .filter((item) => item.index >= 0)
        .sort((left, right) => left.index - right.index);
    const clauses = {};
    const firstClauseIndex = positions.length ? positions[0].index : restWithoutLimit.length;
    clauses.from = restWithoutLimit.slice(bodyStart, firstClauseIndex).trim();
    for (let index = 0; index < positions.length; index++) {
        const current = positions[index];
        const nextIndex = index + 1 < positions.length ? positions[index + 1].index : restWithoutLimit.length;
        clauses[current.key] = restWithoutLimit.slice(current.index + getSqlKeywordLengthAt(restWithoutLimit, current.index, current.keyword), nextIndex).trim();
    }
    return clauses;
}
function stripTopLevelMysqlLimit(statement) {
    const withoutSemicolon = stripSqlTrailingSemicolon(statement);
    const limitIndex = findTopLevelSqlKeyword(withoutSemicolon, 'limit');
    if (limitIndex < 0) {
        return withoutSemicolon;
    }
    return withoutSemicolon.slice(0, limitIndex).trim();
}
function removeMysqlGrafanaTimeRangeConditions(whereClause) {
    const keptConditions = splitTopLevelAndConditions(whereClause).filter((condition) => !isGrafanaMysqlTimeRangeCondition(condition));
    return keptConditions.join(' AND ');
}
function splitTopLevelAndConditions(input) {
    const conditions = [];
    let current = '';
    let quote = '';
    let depth = 0;
    for (let index = 0; index < input.length; index++) {
        const char = input[index];
        const previous = index > 0 ? input[index - 1] : '';
        if (quote) {
            current += char;
            if (char === quote && previous !== '\\') {
                quote = '';
            }
            continue;
        }
        if (char === '"' || char === '\'' || char === '`') {
            quote = char;
            current += char;
            continue;
        }
        if (char === '(') {
            depth++;
            current += char;
            continue;
        }
        if (char === ')' && depth > 0) {
            depth--;
            current += char;
            continue;
        }
        if (depth === 0 && /^AND\b/i.test(input.slice(index)) && !isSqlIdentifierChar(previous)) {
            if (current.trim()) {
                conditions.push(current.trim());
            }
            current = '';
            index += 2;
            continue;
        }
        current += char;
    }
    if (current.trim()) {
        conditions.push(current.trim());
    }
    return conditions;
}
function isGrafanaMysqlTimeRangeCondition(condition) {
    return /\$__time|\$__unixEpoch|\$__from|\$__to|\$\{__from|\$\{__to|__timeFilter|__timeFrom|__timeTo/i.test(condition);
}
function normalizeMysqlClauseKeywords(clause) {
    return String(clause || '')
        .replace(/\blike\b/giu, 'LIKE')
        .replace(/\bdesc\b/giu, 'DESC')
        .replace(/\basc\b/giu, 'ASC')
        .replace(/\band\b/giu, 'AND')
        .replace(/\bor\b/giu, 'OR');
}
function buildMysqlFallbackOuterDatasourceSql(queryText) {
    const statement = stripTopLevelMysqlLimit(queryText).trim();
    return `SELECT
    NULL AS time,
    *
FROM (
    ${statement}
) AS guance_mysql_outer_source
LIMIT 5000;
`;
}
function stripSqlTrailingSemicolon(statement) {
    return String(statement || '').trim().replace(/;\s*$/u, '');
}
function findTopLevelSqlKeyword(input, keyword, startIndex = 0) {
    let quote = '';
    let depth = 0;
    for (let index = startIndex; index < input.length; index++) {
        const char = input[index];
        const previous = index > 0 ? input[index - 1] : '';
        if (quote) {
            if (char === quote && previous !== '\\') {
                quote = '';
            }
            continue;
        }
        if (char === '"' || char === '\'' || char === '`') {
            quote = char;
            continue;
        }
        if (char === '(') {
            depth++;
            continue;
        }
        if (char === ')' && depth > 0) {
            depth--;
            continue;
        }
        if (depth === 0 && matchesSqlKeywordAt(input, index, keyword)) {
            return index;
        }
    }
    return -1;
}
function matchesSqlKeywordAt(input, index, keyword) {
    const previous = index > 0 ? input[index - 1] : '';
    if (isSqlIdentifierChar(previous)) {
        return false;
    }
    const pattern = new RegExp(`^${keyword.trim().split(/\s+/u).join('\\s+')}(?![A-Za-z0-9_])`, 'i');
    return pattern.test(input.slice(index));
}
function getSqlKeywordLengthAt(input, index, keyword) {
    const pattern = new RegExp(`^${keyword.trim().split(/\s+/u).join('\\s+')}`, 'i');
    const match = input.slice(index).match(pattern);
    return match ? match[0].length : keyword.length;
}
function isSqlIdentifierChar(char) {
    return /[A-Za-z0-9_]/u.test(char || '');
}
function normalizeOuterDatasourceDefaultVal(defaultVal, includeAll) {
    if (!includeAll) {
        return defaultVal;
    }
    const label = String((defaultVal === null || defaultVal === void 0 ? void 0 : defaultVal.label) || '').trim().toLowerCase();
    const value = String((defaultVal === null || defaultVal === void 0 ? void 0 : defaultVal.value) || '').trim().toLowerCase();
    if ((label === 'all' || label === 'all values' || label === '*') &&
        (value === '$__all' || value === '__all__' || value === '*')) {
        return { label: '', value: '' };
    }
    return defaultVal;
}
function firstNonEmptyString(...values) {
    for (const value of values) {
        if (typeof value === 'string' && value.trim()) {
            return value.trim();
        }
    }
    return '';
}
function convertSlsQueryToDql(queryText, carrier = {}, options = {}) {
    const namespace = resolveSlsNamespace(carrier, options);
    const source = resolveSlsSource(carrier, queryText, options);
    const cacheKey = JSON.stringify([namespace, source || '', queryText]);
    if (SLS_CONVERSION_CACHE.has(cacheKey)) {
        return SLS_CONVERSION_CACHE.get(cacheKey);
    }
    const args = ['convert', '--namespace', namespace];
    if (source && !hasSlsFromClause(queryText)) {
        args.push('--source', source);
    }
    args.push('--query', queryText);
    try {
        const output = execFileSync(SLS2DQL_BINARY, args, {
            cwd: REPOSITORY_ROOT,
            encoding: 'utf8',
            stdio: ['ignore', 'pipe', 'pipe'],
        });
        const result = parseSls2dqlOutput(output);
        const conversionInfo = buildSlsConversionInfo(result, namespace, source, queryText);
        const convertedQuery = result.dql && (result.status === 'exact' || result.status === 'approximate')
            ? result.dql
            : queryText;
        const payload = {
            queryText: convertedQuery,
            conversionInfo,
        };
        SLS_CONVERSION_CACHE.set(cacheKey, payload);
        return payload;
    }
    catch (error) {
        const commandOutput = `${String((error === null || error === void 0 ? void 0 : error.stdout) || '')}\n${String((error === null || error === void 0 ? void 0 : error.stderr) || '')}`.trim();
        if (commandOutput) {
            const result = parseSls2dqlOutput(commandOutput);
            if (result.status || result.dql || result.diagnostics.length || result.unsupportedClass) {
                const payload = {
                    queryText: result.dql && (result.status === 'exact' || result.status === 'approximate') ? result.dql : queryText,
                    conversionInfo: buildSlsConversionInfo(result, namespace, source, queryText),
                };
                SLS_CONVERSION_CACHE.set(cacheKey, payload);
                return payload;
            }
        }
        const payload = {
            queryText,
            conversionInfo: buildSlsConversionInfo({
                status: 'unsupported',
                dql: '',
                diagnostics: [String((error === null || error === void 0 ? void 0 : error.message) || 'SLS conversion failed')],
                unsupportedClass: 'tool-error',
            }, namespace, source, queryText),
        };
        SLS_CONVERSION_CACHE.set(cacheKey, payload);
        return payload;
    }
}
function parseSls2dqlOutput(output) {
    const lines = String(output || '')
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    const statusLine = lines.find((line) => line.startsWith('Status:'));
    const dqlLine = lines.find((line) => line.startsWith('DQL:'));
    const unsupportedClassLine = lines.find((line) => line.startsWith('Unsupported Class:'));
    const diagnostics = [];
    let inDiagnostics = false;
    for (const line of lines) {
        if (line.startsWith('Diagnostics:')) {
            inDiagnostics = true;
            continue;
        }
        if (!inDiagnostics) {
            continue;
        }
        diagnostics.push(line.replace(/^- /, ''));
    }
    return {
        status: statusLine ? statusLine.replace(/^Status:\s*/i, '').trim().toLowerCase() : '',
        dql: dqlLine ? dqlLine.replace(/^DQL:\s*/i, '').trim() : '',
        unsupportedClass: unsupportedClassLine ? unsupportedClassLine.replace(/^Unsupported Class:\s*/i, '').trim() : '',
        diagnostics,
    };
}
function buildSlsConversionInfo(result, namespace, source, originalQuery) {
    return pruneEmpty({
        tool: 'sls2dql',
        status: result.status || 'unsupported',
        unsupportedClass: result.unsupportedClass || undefined,
        namespace,
        source: source || undefined,
        originalQuery,
        convertedQuery: result.dql || undefined,
        diagnostics: Array.isArray(result.diagnostics) && result.diagnostics.length ? result.diagnostics : undefined,
    });
}
function resolveSlsNamespace(carrier = {}, options = {}) {
    const candidates = [
        options.slsNamespace,
        carrier.namespace,
        carrier.ns,
        carrier.query && carrier.query.namespace,
        carrier.datasource && carrier.datasource.namespace,
    ];
    for (const candidate of candidates) {
        if (typeof candidate === 'string' && candidate.trim()) {
            return candidate.trim();
        }
    }
    return DEFAULT_SLS_NAMESPACE;
}
function resolveSlsSource(carrier = {}, queryText, options = {}) {
    if (hasSlsFromClause(queryText)) {
        return '';
    }
    const candidates = [
        options.slsSource,
        carrier.source,
        carrier.logstore,
        carrier.logstoreName,
        carrier.query && carrier.query.source,
        carrier.query && carrier.query.logstore,
        carrier.query && carrier.query.logstoreName,
    ];
    for (const candidate of candidates) {
        if (typeof candidate === 'string' && candidate.trim()) {
            return candidate.trim();
        }
    }
    return '';
}
function hasSlsFromClause(queryText) {
    return /\bfrom\s+[`"']?[A-Za-z0-9_.-]+[`"']?/i.test(String(queryText || ''));
}
function sanitizeVariableQuery(queryText, options = {}) {
    return sanitizeQueryText(queryText, options);
}
function sanitizeTargetQuery(queryText, options = {}) {
    return sanitizeQueryText(queryText, options);
}
function sanitizeQueryText(queryText, options = {}) {
    if (typeof queryText !== 'string' || !queryText.trim()) {
        return queryText;
    }
    queryText = stripGrafanaPromqlIntervals(queryText);
    if (options.keepJobVariable === true) {
        return queryText;
    }
    if (looksLikeDqlQuery(queryText)) {
        return sanitizeDqlJobFilters(queryText).trim();
    }
    return sanitizePromqlJobFilters(queryText).trim();
}
function looksLikeDqlQuery(queryText) {
    return /^\s*(with|select)\b/i.test(queryText) || /^[A-Z]::/.test(queryText) || /[A-Z]\('/.test(queryText);
}
function sanitizePromqlJobFilters(queryText) {
    let result = queryText.replace(/\{([^{}]*)\}/g, (match, content) => sanitizePromqlSelector(content));
    result = result.replace(/([A-Za-z_:][A-Za-z0-9_:]*)\{\}/g, '$1');
    return result;
}
function sanitizePromqlSelector(content) {
    const parts = splitTopLevel(content, ',');
    const filtered = parts.filter((part) => !isJobPromqlMatcher(part));
    return `{${filtered.join(',')}}`;
}
function isJobPromqlMatcher(segment) {
    const match = String(segment).match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(=~|!~|=|!=)/);
    if (!match) {
        return false;
    }
    return normalizeVariableIdentifier(match[1]) === 'job';
}
function sanitizeDqlJobFilters(queryText) {
    return queryText.replace(/\{([^{}]*)\}/g, (match, content) => {
        const filtered = splitTopLevelLogical(content).filter((clause) => !isJobDqlClause(clause));
        if (filtered.length === 0) {
            return '';
        }
        return `{ ${filtered.join(' and ')} }`;
    });
}
function isJobDqlClause(segment) {
    const match = String(segment).match(/^\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*(=~|!~|=|!=|>=|<=|>|<|\bIN\b|\bNOT IN\b|\blike\b)/i);
    if (!match) {
        return false;
    }
    return normalizeVariableIdentifier(match[1]) === 'job';
}
function splitTopLevel(input, separator) {
    const segments = [];
    let current = '';
    let quote = '';
    let depth = 0;
    for (let index = 0; index < input.length; index++) {
        const char = input[index];
        const previous = index > 0 ? input[index - 1] : '';
        if (quote) {
            current += char;
            if (char === quote && previous !== '\\') {
                quote = '';
            }
            continue;
        }
        if (char === '"' || char === '\'' || char === '`') {
            quote = char;
            current += char;
            continue;
        }
        if (char === '(' || char === '[') {
            depth++;
            current += char;
            continue;
        }
        if ((char === ')' || char === ']') && depth > 0) {
            depth--;
            current += char;
            continue;
        }
        if (char === separator && depth === 0) {
            if (current.trim()) {
                segments.push(current.trim());
            }
            current = '';
            continue;
        }
        current += char;
    }
    if (current.trim()) {
        segments.push(current.trim());
    }
    return segments;
}
function splitTopLevelLogical(input) {
    const segments = [];
    let current = '';
    let quote = '';
    let depth = 0;
    for (let index = 0; index < input.length; index++) {
        const char = input[index];
        const previous = index > 0 ? input[index - 1] : '';
        if (quote) {
            current += char;
            if (char === quote && previous !== '\\') {
                quote = '';
            }
            continue;
        }
        if (char === '"' || char === '\'' || char === '`') {
            quote = char;
            current += char;
            continue;
        }
        if (char === '(' || char === '[') {
            depth++;
            current += char;
            continue;
        }
        if ((char === ')' || char === ']') && depth > 0) {
            depth--;
            current += char;
            continue;
        }
        if (depth === 0 && input.slice(index).match(/^(AND|OR)\b/i) && /\s/.test(previous || ' ')) {
            const operatorMatch = input.slice(index).match(/^(AND|OR)\b/i);
            if (operatorMatch && current.trim()) {
                segments.push(current.trim());
                current = '';
                index += operatorMatch[0].length - 1;
                continue;
            }
        }
        current += char;
    }
    if (current.trim()) {
        segments.push(current.trim());
    }
    return segments;
}
function stripGrafanaPromqlIntervals(queryText) {
    return String(queryText)
        .replace(/\[\s*\$__rate_interval\s*\]/g, '')
        .replace(/\[\s*\$\{__rate_interval(?:[:}][^}]*)?\}\s*\]/g, '');
}
function extractWorkspaceInfo(targets) {
    const workspaceUUIDs = [];
    const workspaceNames = [];
    for (const target of Array.isArray(targets) ? targets : []) {
        for (const item of Array.isArray(target.workspaceUUIDs) ? target.workspaceUUIDs : []) {
            if ((item === null || item === void 0 ? void 0 : item.value) && !workspaceUUIDs.includes(item.value))
                workspaceUUIDs.push(item.value);
            if ((item === null || item === void 0 ? void 0 : item.label) && !workspaceNames.includes(item.label))
                workspaceNames.push(item.label);
        }
    }
    return pruneEmpty({
        changeWorkspace: workspaceUUIDs.length > 0,
        workspaceUUID: workspaceUUIDs.length ? workspaceUUIDs.join(',') : undefined,
        workspaceName: workspaceNames.length ? workspaceNames : undefined,
    });
}
function normalizeTargetQuery(queryText, qtype, options = {}, target = {}) {
    if (qtype !== 'promql')
        return queryText;
    return normalizeCloudwatchPromqlQuery(queryText);
}
function normalizeTargetAlias(alias, queryText, qtype) {
    const normalizedAlias = normalizeQueryAlias(alias);
    if (!normalizedAlias || qtype !== 'promql') {
        return normalizedAlias;
    }
    return normalizeCloudwatchAlias(normalizedAlias, queryText);
}
function normalizeCloudwatchPromqlQuery(queryText) {
    const input = String(queryText || '');
    let output = '';
    let cursor = 0;
    let changed = false;
    while (cursor < input.length) {
        const matchIndex = input.indexOf('cloudwatch_metric_', cursor);
        if (matchIndex === -1) {
            output += input.slice(cursor);
            break;
        }
        output += input.slice(cursor, matchIndex);
        const selector = extractCloudwatchSelector(input, matchIndex);
        if (!selector) {
            output += input.slice(matchIndex);
            break;
        }
        const parsed = parseCloudwatchMetricQuery(selector.text);
        const rewritten = parsed ? buildCloudwatchMetricSelector(parsed) : '';
        if (rewritten) {
            output += rewritten;
            changed = true;
        }
        else {
            output += selector.text;
        }
        cursor = selector.end;
    }
    return changed ? output : queryText;
}
function normalizeCloudwatchAlias(alias, queryText) {
    const tokenMappings = extractCloudwatchAliasTokenMappings(queryText);
    if (tokenMappings.size === 0) {
        return alias;
    }
    return alias.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (match, token) => {
        const normalizedToken = String(token || '').trim();
        const mappedToken = tokenMappings.get(normalizedToken);
        if (!mappedToken) {
            return match;
        }
        return `{{${mappedToken}}}`;
    });
}
function extractCloudwatchAliasTokenMappings(queryText) {
    const input = String(queryText || '');
    const mappings = new Map();
    let cursor = 0;
    while (cursor < input.length) {
        const matchIndex = input.indexOf('cloudwatch_metric_', cursor);
        if (matchIndex === -1) {
            break;
        }
        const selector = extractCloudwatchSelector(input, matchIndex);
        if (!selector) {
            break;
        }
        const parsed = parseCloudwatchMetricQuery(selector.text);
        const serviceMapping = parsed ? getCloudwatchServiceMapping(parsed.service) : null;
        const aliasToken = (serviceMapping === null || serviceMapping === void 0 ? void 0 : serviceMapping.aliasToken) || (serviceMapping === null || serviceMapping === void 0 ? void 0 : serviceMapping.dimension) || '';
        if ((serviceMapping === null || serviceMapping === void 0 ? void 0 : serviceMapping.sourceLabel) && aliasToken && !mappings.has(serviceMapping.sourceLabel)) {
            mappings.set(serviceMapping.sourceLabel, aliasToken);
        }
        if ((serviceMapping === null || serviceMapping === void 0 ? void 0 : serviceMapping.dimension) && aliasToken && !mappings.has(serviceMapping.dimension)) {
            mappings.set(serviceMapping.dimension, aliasToken);
        }
        cursor = selector.end;
    }
    return mappings;
}
function extractCloudwatchSelector(input, startIndex) {
    const braceIndex = input.indexOf('{', startIndex);
    if (braceIndex === -1) {
        return null;
    }
    const metricId = input.slice(startIndex, braceIndex).trim();
    if (!/^cloudwatch_metric_[A-Za-z0-9_]+$/.test(metricId)) {
        return null;
    }
    let inQuotes = false;
    let quoteChar = '';
    let escaped = false;
    let depth = 0;
    for (let index = braceIndex; index < input.length; index++) {
        const char = input[index];
        if (escaped) {
            escaped = false;
            continue;
        }
        if (char === '\\') {
            escaped = true;
            continue;
        }
        if ((char === '"' || char === "'")) {
            if (!inQuotes) {
                inQuotes = true;
                quoteChar = char;
            }
            else if (quoteChar === char) {
                inQuotes = false;
                quoteChar = '';
            }
            continue;
        }
        if (inQuotes) {
            continue;
        }
        if (char === '{') {
            depth++;
            continue;
        }
        if (char === '}') {
            depth--;
            if (depth === 0) {
                return {
                    text: input.slice(startIndex, index + 1),
                    end: index + 1,
                };
            }
        }
    }
    return null;
}
function buildCloudwatchMetricSelector(parsed) {
    const serviceMapping = getCloudwatchServiceMapping(parsed.service);
    if (!serviceMapping) {
        return '';
    }
    const metricName = appendCloudwatchStatisticSuffix(parsed.metricName, serviceMapping.statistic || 'Average');
    if (!metricName) {
        return '';
    }
    const labelMatchers = buildCloudwatchGuanceLabelMatchers(parsed.matchers, serviceMapping);
    return `${metricName}{${labelMatchers.join(',')}}`;
}
function parseCloudwatchMetricQuery(queryText) {
    const trimmed = String(queryText || '').trim();
    const match = trimmed.match(/^([A-Za-z_:][A-Za-z0-9_:]*)(?:\{([\s\S]*)\})?$/);
    if (!match) {
        return null;
    }
    const metricId = match[1];
    if (!metricId.startsWith('cloudwatch_metric_')) {
        return null;
    }
    const metricMatcherText = match[2] || '';
    const matchers = parsePromqlLabelMatchers(metricMatcherText);
    const metricName = resolveCloudwatchMetricName(matchers);
    if (!metricName) {
        return null;
    }
    return {
        service: metricId.slice('cloudwatch_metric_'.length),
        metricName,
        matchers,
    };
}
function resolveCloudwatchMetricName(matchers) {
    const metricNameMatcher = matchers.find((matcher) => matcher.label === 'metric_name' && (matcher.operator === '=' || matcher.operator === '=~'));
    if (!(metricNameMatcher === null || metricNameMatcher === void 0 ? void 0 : metricNameMatcher.value)) {
        return '';
    }
    if (metricNameMatcher.operator === '=') {
        return metricNameMatcher.value;
    }
    const literalCandidate = metricNameMatcher.value.trim();
    if (!literalCandidate || /[.*+?^${}()|[\]\\]/.test(literalCandidate)) {
        return '';
    }
    return literalCandidate;
}
function parsePromqlLabelMatchers(input) {
    if (!input.trim()) {
        return [];
    }
    const parts = [];
    let current = '';
    let inQuotes = false;
    let escaped = false;
    for (const char of input) {
        if (escaped) {
            current += char;
            escaped = false;
            continue;
        }
        if (char === '\\') {
            current += char;
            escaped = true;
            continue;
        }
        if (char === '"') {
            current += char;
            inQuotes = !inQuotes;
            continue;
        }
        if (char === ',' && !inQuotes) {
            if (current.trim()) {
                parts.push(current.trim());
            }
            current = '';
            continue;
        }
        current += char;
    }
    if (current.trim()) {
        parts.push(current.trim());
    }
    return parts
        .map((part) => parsePromqlLabelMatcher(part))
        .filter(Boolean);
}
function parsePromqlLabelMatcher(part) {
    const matcher = String(part || '').match(/^([A-Za-z_][A-Za-z0-9_]*)\s*(=~|!~|!=|=)\s*(.+)$/);
    if (!matcher) {
        return null;
    }
    const label = matcher[1];
    const operator = matcher[2];
    const rawValue = matcher[3].trim();
    const quoteChar = rawValue[0];
    if ((quoteChar !== '"' && quoteChar !== "'") || rawValue[rawValue.length - 1] !== quoteChar) {
        return null;
    }
    return {
        label,
        operator,
        value: rawValue.slice(1, -1),
    };
}
function normalizeCloudwatchDimensionValue(value) {
    if (Array.isArray(value)) {
        return value.map((item) => String(item || '').trim()).filter(Boolean).join('|');
    }
    return String(value || '').trim();
}
function inferCloudwatchMatcherOperator(value) {
    const normalizedValue = String(value || '');
    if (!normalizedValue) {
        return '=';
    }
    if (normalizedValue.includes('$') || normalizedValue.includes('#{') || /[|*+?()[\].]/.test(normalizedValue)) {
        return '=~';
    }
    return '=';
}
function escapePromqlLabelValue(value) {
    return String(value || '')
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"');
}
function getCloudwatchServiceMapping(service) {
    const normalizedService = String(service || '').trim().toLowerCase();
    if (!normalizedService) {
        return null;
    }
    const mappings = loadCloudwatchServiceMappings();
    return mappings.get(normalizedService) || null;
}
function getCloudwatchServiceMappingByNamespace(namespace) {
    const normalizedNamespace = String(namespace || '').trim().toLowerCase();
    if (!normalizedNamespace) {
        return null;
    }
    const mappings = loadCloudwatchServiceMappings();
    for (const mapping of mappings.values()) {
        if (String(mapping.namespace || '').trim().toLowerCase() === normalizedNamespace) {
            return mapping;
        }
    }
    return null;
}
function loadCloudwatchServiceMappings() {
    if (CLOUDWATCH_SERVICE_MAPPINGS instanceof Map) {
        return CLOUDWATCH_SERVICE_MAPPINGS;
    }
    try {
        const content = readFileSync(CLOUDWATCH_MAPPING_FILE, 'utf8');
        CLOUDWATCH_SERVICE_MAPPINGS = parseCloudwatchServiceMappings(content);
    }
    catch (_error) {
        CLOUDWATCH_SERVICE_MAPPINGS = new Map();
    }
    return CLOUDWATCH_SERVICE_MAPPINGS;
}
function parseCloudwatchServiceMappings(markdownText) {
    const mappings = new Map();
    const lines = String(markdownText || '').split(/\r?\n/);
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('|') || /^[:\-\s|]+$/.test(trimmed)) {
            continue;
        }
        const columns = trimmed
            .split('|')
            .slice(1, -1)
            .map((item) => item.trim());
        if (columns.length < 8) {
            continue;
        }
        if (columns[0] === 'service') {
            continue;
        }
        const [service, namespace, measurement, dimension, sourceLabel, variableName, statistic, aliasToken] = columns;
        if (!service || !measurement || !dimension) {
            continue;
        }
        mappings.set(service.toLowerCase(), {
            service,
            namespace,
            measurement,
            dimension,
            sourceLabel,
            variableName,
            statistic: statistic || 'Average',
            aliasToken: aliasToken || dimension,
        });
    }
    return mappings;
}
function appendCloudwatchStatisticSuffix(metricName, statistic) {
    const trimmedMetricName = String(metricName || '').trim();
    if (!trimmedMetricName) {
        return '';
    }
    if (/_(Average|Maximum|Minimum|Sum|SampleCount)$/.test(trimmedMetricName)) {
        return trimmedMetricName;
    }
    return `${trimmedMetricName}_${statistic}`;
}
function buildCloudwatchGuanceLabelMatchers(matchers, serviceMapping) {
    const labels = [
        `M="${serviceMapping.measurement}"`,
        `Dimensions="${serviceMapping.dimension}"`,
    ];
    for (const matcher of matchers) {
        if (matcher.label === 'metric_name') {
            continue;
        }
        const mappedLabel = matcher.label === serviceMapping.sourceLabel ? serviceMapping.dimension : matcher.label;
        const shouldMapToVariable = serviceMapping.variableName &&
            (matcher.label === serviceMapping.sourceLabel || matcher.label === serviceMapping.dimension) &&
            hasGrafanaVariableReference(matcher.value);
        if (shouldMapToVariable) {
            labels.push(`${serviceMapping.dimension}=~"#{${serviceMapping.variableName}}"`);
            continue;
        }
        labels.push(`${mappedLabel}${matcher.operator}"${matcher.value}"`);
    }
    return labels;
}
function hasGrafanaVariableReference(value) {
    const normalizedValue = String(value || '').trim();
    if (!normalizedValue) {
        return false;
    }
    return normalizedValue.includes('#{') || /\$[A-Za-z_][A-Za-z0-9_]*/.test(normalizedValue);
}
function extractMetricName(queryString, variableNames) {
    if (/^\s*(with|select)\b/i.test(queryString))
        return '';
    const labelValuesMatch = queryString.match(/label_values\(([^,]+),\s*([^)]+)\)/i);
    if (labelValuesMatch)
        return replaceVariables(labelValuesMatch[1].trim(), variableNames);
    return '';
}
function extractFieldName(queryString) {
    const fieldValuesMatch = queryString.match(/field_values\(`?([^`)\s]+)`?\)/i);
    if (fieldValuesMatch)
        return fieldValuesMatch[1].trim();
    const labelValuesMatch = queryString.match(/label_values\([^,]+,\s*([^)]+)\)/i);
    if (labelValuesMatch)
        return labelValuesMatch[1].replace(/[`'"]/g, '').trim();
    return '';
}
function normalizeTimeInterval(value) {
    const allowedIntervals = new Set([
        '',
        'auto',
        '1ms',
        '10ms',
        '50ms',
        '100ms',
        '500ms',
        '1s',
        '10s',
        '20s',
        '30s',
        '1m',
        '5m',
        '10m',
        '30m',
        '1h',
        '6h',
        '12h',
        '1d',
        '7d',
        '30d',
    ]);
    if (value === undefined || value === null)
        return 'auto';
    const normalized = String(value).trim();
    if (!normalized)
        return 'auto';
    if (normalized.startsWith('$') || normalized.includes('#{')) {
        return 'auto';
    }
    if (allowedIntervals.has(normalized)) {
        return normalized;
    }
    const durationMatch = normalized.match(/^(\d+)(ms|s|m|h|d)$/i);
    if (durationMatch) {
        const amount = Number(durationMatch[1]);
        const unit = durationMatch[2].toLowerCase();
        const mapped = normalizeDurationToAllowedInterval(amount, unit);
        return mapped || 'auto';
    }
    if (/^\d+$/.test(normalized)) {
        const mapped = normalizeDurationToAllowedInterval(Number(normalized), 's');
        return mapped || 'auto';
    }
    return normalized;
}
function normalizeChartDirection(value, chartType) {
    const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
    if (normalized === 'horizontal' || normalized === 'vertical') {
        return normalized;
    }
    if (chartType === 'toplist') {
        return 'horizontal';
    }
    return undefined;
}
function normalizeDurationToAllowedInterval(amount, unit) {
    if (!Number.isFinite(amount) || amount <= 0) {
        return null;
    }
    const totalMilliseconds = unit === 'ms'
        ? amount
        : unit === 's'
            ? amount * 1000
            : unit === 'm'
                ? amount * 60 * 1000
                : unit === 'h'
                    ? amount * 60 * 60 * 1000
                    : unit === 'd'
                        ? amount * 24 * 60 * 60 * 1000
                        : null;
    if (!totalMilliseconds) {
        return null;
    }
    const intervalByMilliseconds = new Map([
        [1, '1ms'],
        [10, '10ms'],
        [50, '50ms'],
        [100, '100ms'],
        [500, '500ms'],
        [1000, '1s'],
        [10000, '10s'],
        [20000, '20s'],
        [30000, '30s'],
        [60000, '1m'],
        [300000, '5m'],
        [600000, '10m'],
        [1800000, '30m'],
        [3600000, '1h'],
        [21600000, '6h'],
        [43200000, '12h'],
        [86400000, '1d'],
        [604800000, '7d'],
        [2592000000, '30d'],
    ]);
    return intervalByMilliseconds.get(totalMilliseconds) || null;
}
function inferUnitFromQueries(queries, chartType) {
    if (!Array.isArray(queries) || queries.length === 0)
        return undefined;
    if (['text', 'table', 'topology', 'iframe', 'picture', 'video'].includes(chartType))
        return undefined;
    const inferredUnits = queries
        .map((query) => { var _a; return inferUnitFromQueryText(((_a = query === null || query === void 0 ? void 0 : query.query) === null || _a === void 0 ? void 0 : _a.q) || ''); })
        .filter(Boolean);
    if (inferredUnits.length === 0)
        return undefined;
    const counts = new Map();
    for (const unit of inferredUnits) {
        counts.set(unit, (counts.get(unit) || 0) + 1);
    }
    let bestUnit = inferredUnits[0];
    let bestCount = counts.get(bestUnit) || 0;
    for (const unit of inferredUnits) {
        const currentCount = counts.get(unit) || 0;
        if (currentCount > bestCount) {
            bestUnit = unit;
            bestCount = currentCount;
        }
    }
    return bestUnit;
}
function inferCompareSettings(queries, chartType) {
    var _a;
    if (!Array.isArray(queries) || queries.length === 0) {
        return { compares: undefined, compareType: undefined, openCompare: undefined, compareChartType: undefined };
    }
    if (!['sequence', 'singlestat'].includes(chartType)) {
        return { compares: undefined, compareType: undefined, openCompare: undefined, compareChartType: undefined };
    }
    const compareTypes = [];
    for (const query of queries) {
        const compareType = inferCompareTypeFromQuery(((_a = query === null || query === void 0 ? void 0 : query.query) === null || _a === void 0 ? void 0 : _a.q) || '');
        if (compareType && !compareTypes.includes(compareType)) {
            compareTypes.push(compareType);
        }
    }
    if (compareTypes.length === 0) {
        return { compares: undefined, compareType: undefined, openCompare: undefined, compareChartType: undefined };
    }
    return {
        compares: compareTypes.map((type) => COMPARE_OPTIONS[type]).filter(Boolean),
        compareType: compareTypes,
        openCompare: true,
        compareChartType: chartType,
    };
}
function inferCompareTypeFromQuery(queryText) {
    if (typeof queryText !== 'string' || !queryText.trim())
        return undefined;
    const normalized = queryText.toLowerCase();
    if (/\boffset\s+1h\b/.test(normalized))
        return 'hourCompare';
    if (/\boffset\s+1d\b/.test(normalized))
        return 'dayCompare';
    if (/\boffset\s+(7d|1w)\b/.test(normalized))
        return 'weekCompare';
    if (/\boffset\s+(30d|4w)\b/.test(normalized))
        return 'monthCompare';
    return undefined;
}
function inferSortSettings(chartType, legend, tableSortBy) {
    const sequenceSort = inferSequenceSortOrder(legend);
    const mainMeasurementSort = inferMainMeasurementSort(chartType, legend, tableSortBy);
    return {
        sorderByOrder: sequenceSort,
        mainMeasurementSort,
    };
}
function inferSeriesLimit(queries, options, chartType) {
    const explicitLimit = extractReduceLimit(options);
    if (['pie', 'toplist', 'treemap'].includes(chartType)) {
        return extractTopkLimit(queries) || explicitLimit;
    }
    if (['sequence', 'table'].includes(chartType)) {
        return extractTopkLimit(queries) || undefined;
    }
    return undefined;
}
function extractTopkLimit(queries) {
    var _a;
    if (!Array.isArray(queries))
        return undefined;
    for (const query of queries) {
        const queryText = String(((_a = query === null || query === void 0 ? void 0 : query.query) === null || _a === void 0 ? void 0 : _a.q) || '');
        const match = queryText.match(/\btopk\s*\(\s*(\d+)/i);
        if (!match)
            continue;
        const limit = Number(match[1]);
        if (Number.isFinite(limit))
            return limit;
    }
    return undefined;
}
function inferSequenceSortOrder(legend) {
    if (typeof (legend === null || legend === void 0 ? void 0 : legend.sortDesc) === 'boolean') {
        return legend.sortDesc ? 'desc' : 'asc';
    }
    return undefined;
}
function inferMainMeasurementSort(chartType, legend, tableSortBy) {
    if (!['pie', 'toplist', 'table', 'treemap'].includes(chartType))
        return undefined;
    if (chartType === 'table') {
        const primarySort = Array.isArray(tableSortBy) ? tableSortBy[0] : undefined;
        if (primarySort && typeof primarySort.desc === 'boolean') {
            return primarySort.desc ? 'top' : 'bottom';
        }
    }
    if (typeof (legend === null || legend === void 0 ? void 0 : legend.sortDesc) === 'boolean') {
        return legend.sortDesc ? 'top' : 'bottom';
    }
    return undefined;
}
function inferUnitFromQueryText(queryText) {
    if (typeof queryText !== 'string' || !queryText.trim())
        return undefined;
    const normalized = queryText.toLowerCase();
    const isRateLike = /rate\(|irate\(|increase\(|delta\(|deriv\(/.test(normalized);
    if (/cpu.*(?:usage|utili[sz]ation|used)|cpu_usage|cpu_used|usage_seconds_total/.test(normalized) &&
        /limit|quota|max|capacity|total|cores?|100/.test(normalized)) {
        return 'percent';
    }
    if (/memory.*(?:usage|used|utili[sz]ation)|heap.*used|rss|working_set|used_bytes|usage_bytes/.test(normalized)) {
        return 'bytes';
    }
    if (/disk.*(?:usage|used|utili[sz]ation)|filesystem.*(?:avail|free|size|used)|storage.*(?:used|usage)/.test(normalized)) {
        return 'bytes';
    }
    if (/error_rate|success_rate|failure_rate|biz_error_rate|_ratio\b|_percent\b|percent/.test(normalized) ||
        /container_cpu_usage_seconds_total/.test(normalized) && /kube_pod_container_resource_limits/.test(normalized) ||
        /\*\s*100\b/.test(normalized)) {
        return 'percent';
    }
    if (/p99|p95|p90|latency|duration|response_time|cost\b|elapsed|load_time|_ms\b|milliseconds?/.test(normalized) ||
        /performance_host_interface_p\d+/.test(normalized)) {
        return 'ms';
    }
    if (/_bytes\b|_bytes_total\b|memory|heap|rss|bandwidth|byte\b/.test(normalized)) {
        return 'bytes';
    }
    if (/gc_pause_seconds|gc.*(?:pause|time)|duration_seconds|latency_seconds|response_seconds/.test(normalized)) {
        return 's';
    }
    if (/\bqps\b|\brps\b|reqps|requests?_per_second|interface_qps|host_qps|requests?_total/.test(normalized) && isRateLike) {
        return 'reqps';
    }
    if (/\btps\b|\biops\b|\bops\b|operations?_per_second|ops_total/.test(normalized) && isRateLike) {
        return 'ops';
    }
    if (/cpu:load\d+s|load5s|load1s|load15s|system_load/.test(normalized)) {
        return 'short';
    }
    if (!isRateLike &&
        /goroutines?|threads?|connections?|conn_count|fd|file_descriptors?|queue(_size|_depth)?|pool(_size)?|inflight|pending|blocked|active_requests|jvm_.*_count|_count\b|_total\b|count_over_time\(/.test(normalized)) {
        return 'none';
    }
    if (/_seconds\b/.test(normalized) && !/rate\(|increase\(|irate\(/.test(normalized)) {
        return 's';
    }
    return undefined;
}
function getDatasourceType(datasource) {
    return String((datasource === null || datasource === void 0 ? void 0 : datasource.type) || datasource || '').toLowerCase();
}
function isPrometheusLikeDatasource(datasourceType) {
    return datasourceType.includes('prometheus') || datasourceType.includes('guance-guance-datasource');
}
function isCloudwatchDatasource(datasourceType) {
    return datasourceType.includes('cloudwatch');
}
function isSlsDatasource(datasourceType) {
    return (datasourceType.includes('aliyun-log-service-datasource') ||
        datasourceType.includes('aliyun-log-service') ||
        datasourceType.includes('sls'));
}
function isMysqlDatasource(datasourceType) {
    return datasourceType.includes('mysql');
}
function isSqlDatasource(datasourceType) {
    return (datasourceType.includes('postgres') ||
        datasourceType.includes('mssql') ||
        datasourceType === 'sql');
}
function isDqlLikeDatasource(datasourceType) {
    return (isMysqlDatasource(datasourceType) ||
        datasourceType.includes('postgres') ||
        datasourceType.includes('mssql') ||
        datasourceType.includes('sql') ||
        datasourceType.includes('loki') ||
        datasourceType.includes('elasticsearch') ||
        datasourceType.includes('opensearch') ||
        datasourceType.includes('influx') ||
        datasourceType.includes('tempo') ||
        datasourceType.includes('jaeger') ||
        datasourceType.includes('zipkin'));
}
function extractReduceLimit(options) {
    var _a;
    const limit = (_a = options.reduceOptions) === null || _a === void 0 ? void 0 : _a.limit;
    return typeof limit === 'number' ? limit : 10;
}
function extractCustomOptions(options) {
    if (!Array.isArray(options))
        return '';
    return options
        .filter((item) => item && item.value !== '$__all')
        .map((item) => item.text || item.value || '')
        .filter(Boolean)
        .join(',');
}
function mapLegendPlacement(value) {
    if (value === 'bottom')
        return 'bottom';
    if (value === 'right')
        return 'right';
    if (value === 'left')
        return 'left';
    if (value === 'top')
        return 'top';
    return 'none';
}
function mapLegendCalcs(values) {
    if (!Array.isArray(values))
        return [];
    const allowed = new Set(['first', 'last', 'avg', 'min', 'max', 'sum', 'count']);
    return values
        .map((value) => String(value).toLowerCase())
        .filter((value) => allowed.has(value));
}
function extractLegacyLegendCalcs(legend) {
    if (!legend || typeof legend !== 'object')
        return [];
    const calcs = [];
    if (legend.current)
        calcs.push('last');
    if (legend.avg)
        calcs.push('avg');
    if (legend.min)
        calcs.push('min');
    if (legend.max)
        calcs.push('max');
    if (legend.total)
        calcs.push('sum');
    return calcs;
}
function mapLineInterpolation(value) {
    if (value === 'smooth')
        return 'smooth';
    if (value === 'stepAfter')
        return 'stepAfter';
    if (value === 'stepBefore')
        return 'stepBefore';
    return 'linear';
}
function mapStackType(value) {
    if (value === 'percent')
        return 'percent';
    if (value === 'normal')
        return 'time';
    return 'time';
}
function inferShowLine(panel, custom) {
    if (typeof panel.lines === 'boolean')
        return panel.lines;
    if (custom.drawStyle === 'bars')
        return false;
    return true;
}
function inferOpenStack(panel, custom) {
    var _a;
    if ((_a = custom.stacking) === null || _a === void 0 ? void 0 : _a.mode)
        return custom.stacking.mode !== 'none';
    if (typeof panel.stack === 'boolean')
        return panel.stack;
    return undefined;
}
function inferSequenceChartType(panel, graphMode) {
    if (graphMode === 'area')
        return 'line';
    if (graphMode === 'none')
        return undefined;
    return inferDisplayChartType(panel, 'sequence') === 'bar' ? 'bar' : 'line';
}
function inferGaugeMode(panel, options, legacyGauge) {
    if (panel.type === 'gauge')
        return 'gauge';
    if (legacyGauge.show)
        return 'gauge';
    if (options.graphMode === 'none')
        return 'value';
    return 'value';
}
function normalizeConnectNulls(value) {
    if (typeof value === 'boolean')
        return value;
    if (typeof value === 'number')
        return value > 0;
    if (value === 'connected')
        return true;
    if (value === 'null' || value === 'null as zero')
        return false;
    return undefined;
}
function mapUnit(unit) {
    if (!unit)
        return [];
    const rawUnit = String(unit);
    const mapped = UNIT_MAP[rawUnit] || UNIT_MAP[rawUnit.toLowerCase()];
    if (mapped)
        return mapped;
    return ['custom', rawUnit];
}
function buildLegacyValueMappings(valueMaps) {
    if (!Array.isArray(valueMaps))
        return [];
    return valueMaps
        .filter((item) => item && Object.prototype.hasOwnProperty.call(item, 'value'))
        .map((item) => ({
        originalVal: [String(item.value)],
        operation: normalizeLegacyMappingOperation(item.op),
        mappingVal: item.text || String(item.value),
    }));
}
function buildLegacyRangeMappings(rangeMaps) {
    if (!Array.isArray(rangeMaps))
        return [];
    return rangeMaps.map((item) => {
        var _a, _b;
        return ({
            originalVal: [String((_a = item.from) !== null && _a !== void 0 ? _a : ''), String((_b = item.to) !== null && _b !== void 0 ? _b : '')],
            operation: 'between',
            mappingVal: item.text || '',
        });
    });
}
function normalizeLegacyMappingOperation(value) {
    const allowed = new Set(['>', '>=', '<', '<=', '=', '!=', 'between', '=~', '!=~', 'nodata']);
    if (allowed.has(value))
        return value;
    return '=';
}
function normalizeLegacyFill(value) {
    if (typeof value !== 'number')
        return undefined;
    return Math.max(0, Math.min(100, value * 10));
}
function firstDefinedNumber(...values) {
    for (const value of values) {
        if (typeof value === 'number' && Number.isFinite(value))
            return value;
    }
    return undefined;
}
function replaceVariables(input, variableNames = new Set()) {
    if (typeof input !== 'string')
        return input;
    return input
        .replace(/\$\{([^}]+)\}/g, (match, expression) => {
        const variable = normalizeTemplateVariable(expression);
        if (!variable)
            return match;
        if (GRAFANA_BUILTIN_VARS.has(variable))
            return match;
        if (!variableNames.has(variable))
            return match;
        return `#{${variable}}`;
    })
        .replace(/(^|[^{])\$([A-Za-z0-9_]+)/g, (match, prefix, variable) => {
        if (GRAFANA_BUILTIN_VARS.has(variable))
            return match;
        if (!variableNames.has(variable))
            return match;
        return `${prefix}#{${variable}}`;
    });
}
function normalizeTemplateVariable(expression) {
    const trimmed = String(expression).trim();
    if (!trimmed)
        return '';
    const beforeFormat = trimmed.split(':')[0];
    if (!/^[A-Za-z0-9_.]+$/.test(beforeFormat))
        return '';
    return beforeFormat;
}
function normalizeVariableIdentifier(value) {
    return String(value || '').trim().toLowerCase();
}
function normalizeQueryCode(refId, index) {
    if (typeof refId === 'string' && refId.trim())
        return refId.trim();
    const codePoint = 65 + index;
    return String.fromCharCode(codePoint);
}
function normalizeOuterDatasourceQueryCode(index) {
    const codePoint = 66 + index;
    return String.fromCharCode(codePoint);
}
function stringifyCurrent(value) {
    if (Array.isArray(value))
        return value.join(',');
    if (typeof value === 'string')
        return value;
    if (typeof value === 'number' || typeof value === 'boolean')
        return String(value);
    return '';
}
function normalizeAllValue(value, allValue, isValue = false) {
    if (value === 'All')
        return allValue === '.*' ? '*' : 'all values';
    if (value === '$__all')
        return allValue === '.*' ? '*' : '__all__';
    if (isValue && value === '.*')
        return '*';
    return value;
}
function normalizeColor(color) {
    if (!color)
        return '#999999';
    return String(color);
}
function numberOr(value, fallback) {
    return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}
function numberOrUndefined(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}
function round1(value) {
    return Number(value.toFixed(1));
}
function firstDefined(...values) {
    for (const value of values) {
        if (value !== undefined && value !== null && value !== '')
            return value;
    }
    return undefined;
}
function pruneEmpty(value) {
    if (Array.isArray(value)) {
        return value
            .map((item) => pruneEmpty(item))
            .filter((item) => item !== undefined);
    }
    if (!value || typeof value !== 'object') {
        return value;
    }
    const entries = Object.entries(value)
        .map(([key, current]) => [key, pruneEmpty(current)])
        .filter(([key, current]) => {
        if (current === undefined)
            return false;
        if (Array.isArray(current) && current.length === 0 && key !== 'queries' && key !== 'funcList')
            return false;
        if (current && typeof current === 'object' && !Array.isArray(current) && Object.keys(current).length === 0)
            return false;
        return true;
    });
    return Object.fromEntries(entries);
}
function readJson(filePath) {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}
function forEachFile(directoryPath, callback) {
    for (const entry of fs.readdirSync(directoryPath, { withFileTypes: true })) {
        const entryPath = path.join(directoryPath, entry.name);
        if (entry.isDirectory()) {
            forEachFile(entryPath, callback);
        }
        else {
            callback(entryPath);
        }
    }
}
