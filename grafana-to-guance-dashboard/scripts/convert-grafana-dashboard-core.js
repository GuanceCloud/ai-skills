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
    bytes: ['digital', 'B'],
    decbytes: ['digital', 'B'],
    bits: ['digital', 'b'],
    deckbytes: ['digital', 'KB'],
    decgbytes: ['digital', 'GB'],
    ms: ['time', 'ms'],
    s: ['time', 's'],
    m: ['time', 'min'],
    h: ['time', 'h'],
    d: ['time', 'd'],
    short: ['custom', 'short'],
    none: ['custom', 'none'],
    reqps: ['custom', 'reqps'],
    ops: ['custom', 'ops'],
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
    const variableNames = new Set((((_a = grafanaDashboard.templating) === null || _a === void 0 ? void 0 : _a.list) || []).map((item) => item === null || item === void 0 ? void 0 : item.name).filter(Boolean));
    const state = {
        groups: [],
        groupUnfoldStatus: {},
        charts: [],
    };
    const sortedPanels = sortPanels(grafanaDashboard.panels || []);
    collectPanels(sortedPanels, state, null, variableNames, options);
    return pruneEmpty({
        title: grafanaDashboard.title || '',
        description: grafanaDashboard.description || undefined,
        tags: grafanaDashboard.tags || undefined,
        uid: grafanaDashboard.uid || undefined,
        dashboardExtend: {
            groupUnfoldStatus: state.groupUnfoldStatus,
        },
        main: {
            vars: convertVariables(((_b = grafanaDashboard.templating) === null || _b === void 0 ? void 0 : _b.list) || [], variableNames),
            charts: state.charts,
            groups: state.groups,
            type: 'template',
        },
    });
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
function convertVariables(variables, variableNames) {
    return variables
        .map((variable, index) => convertVariable(variable, index, variableNames))
        .filter(Boolean);
}
function convertVariable(variable, index, variableNames) {
    const variableType = String(variable.type || '');
    const current = variable.current || {};
    const currentText = stringifyCurrent(current.text);
    const currentValue = stringifyCurrent(current.value);
    const includeAll = Boolean(variable.includeAll);
    const defaultVal = {
        label: normalizeAllValue(currentText, variable.allValue),
        value: normalizeAllValue(currentValue, variable.allValue, true),
    };
    const base = {
        name: variable.label || variable.name || '',
        seq: index,
        code: variable.name || `var_${index}`,
        hide: variable.hide && variable.hide !== 0 ? 1 : 0,
        multiple: Boolean(variable.multi),
        includeStar: includeAll,
        valueSort: 'desc',
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
        const queryString = extractVariableQuery(variable);
        const queryKind = inferVariableQueryType(variable, queryString);
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
    const settings = buildSettings(panel, chartType, queries, variableNames);
    const links = extractPanelLinks(panel, variableNames);
    const group = groupName !== null && groupName !== void 0 ? groupName : null;
    const position = buildPosition(panel, rowPanel);
    return pruneEmpty({
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
        const queryText = extractTargetQuery(target);
        if (!queryText)
            continue;
        const qtype = inferQueryLanguage(target, queryText);
        const normalizedQueryText = normalizeTargetQuery(queryText, qtype, options);
        queries.push(pruneEmpty({
            name: target.legendFormat || target.alias || '',
            type: chartType,
            qtype,
            datasource: 'dataflux',
            disabled: Boolean(target.hide),
            query: {
                q: replaceVariables(normalizedQueryText, variableNames),
                code: normalizeQueryCode(target.refId, index),
                type: qtype,
                promqlCode: qtype === 'promql' ? index + 1 : undefined,
                alias: target.legendFormat || target.alias || '',
                field: target.field || undefined,
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
function buildSettings(panel, chartType, queries, variableNames) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w, _x;
    const defaults = ((_a = panel.fieldConfig) === null || _a === void 0 ? void 0 : _a.defaults) || {};
    const custom = defaults.custom || {};
    const options = panel.options || {};
    const legend = options.legend || panel.legend || {};
    const transformationInfo = parseTransformations(panel.transformations || []);
    const aliases = buildAliases(queries);
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
        maxPointCount: (_l = panel.maxDataPoints) !== null && _l !== void 0 ? _l : null,
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
        xAxisShowType: chartType === 'sequence' || chartType === 'bar' ? 'time' : undefined,
        unitType: effectiveUnitType,
        globalUnit: customUnits.length ? undefined : mapUnit(unit),
        units: customUnits.length ? customUnits : undefined,
        colors: customColors.length ? customColors : undefined,
        colorMappings: colorMappings.length ? colorMappings : undefined,
        levels: buildLevels(defaults.thresholds),
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
        direction: options.orientation || undefined,
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
        color: ((_q = defaults.color) === null || _q === void 0 ? void 0 : _q.fixedColor) || undefined,
        fontColor: options.colorMode === 'value' ? (_r = defaults.color) === null || _r === void 0 ? void 0 : _r.fixedColor : undefined,
        bgColor: options.colorMode === 'background' ? (_s = defaults.color) === null || _s === void 0 ? void 0 : _s.fixedColor : undefined,
        sequenceChartType: chartType === 'singlestat' && graphMode ? inferSequenceChartType(panel, graphMode) : undefined,
        showLineAxis: chartType === 'singlestat' ? graphMode !== 'none' : undefined,
        repeatChartVariable: typeof panel.repeat === 'string' && panel.repeat ? panel.repeat : undefined,
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
            stackingGroup: ((_t = custom.stacking) === null || _t === void 0 ? void 0 : _t.group) || undefined,
            graphMode,
            colorMode: options.colorMode || undefined,
            fieldColorMode: ((_u = defaults.color) === null || _u === void 0 ? void 0 : _u.mode) || undefined,
            fixedColor: ((_v = defaults.color) === null || _v === void 0 ? void 0 : _v.fixedColor) || undefined,
            thresholdsMode: ((_w = defaults.thresholds) === null || _w === void 0 ? void 0 : _w.mode) || undefined,
            thresholdsStyleMode: ((_x = custom.thresholdsStyle) === null || _x === void 0 ? void 0 : _x.mode) || undefined,
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
        fieldOverrides: fieldOverrides.length ? fieldOverrides : undefined,
        transformations: transformationInfo.normalized.length ? transformationInfo.normalized : undefined,
        fieldFilterPattern: transformationInfo.fieldFilterPattern || undefined,
        valueFilters: transformationInfo.valueFilters.length ? transformationInfo.valueFilters : undefined,
        layout: pruneEmpty({
            repeatDirection: panel.repeatDirection || undefined,
        }),
    });
    return pruneEmpty(settings);
}
function buildLevels(thresholds) {
    const steps = Array.isArray(thresholds === null || thresholds === void 0 ? void 0 : thresholds.steps) ? thresholds.steps : [];
    return steps
        .filter((step) => typeof step.value === 'number' || typeof step.color === 'string')
        .map((step, index) => ({
        title: `Level ${index + 1}`,
        value: typeof step.value === 'number' ? step.value : 0,
        bgColor: normalizeColor(step.color),
    }));
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
function buildAliases(queries) {
    return queries
        .filter((query) => { var _a; return (_a = query.query) === null || _a === void 0 ? void 0 : _a.alias; })
        .map((query) => ({
        alias: query.query.alias,
        key: query.query.code || query.name || '',
        name: query.query.code || query.name || '',
    }));
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
    if (datasourceType.includes('guance-guance-datasource'))
        return 'dql';
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
function inferVariableQueryType(variable, queryString) {
    var _a;
    const datasourceType = getDatasourceType(variable.datasource);
    const explicitQtype = String(((_a = variable.query) === null || _a === void 0 ? void 0 : _a.qtype) || '').toLowerCase();
    if (datasourceType.includes('object'))
        return 'FIELD';
    if (explicitQtype === 'promql')
        return 'PROMQL_QUERY';
    if (explicitQtype === 'dql')
        return 'QUERY';
    if (isDqlLikeDatasource(datasourceType) && /^\s*(with|select)\b/i.test(queryString))
        return 'QUERY';
    if (/field_values\(/i.test(queryString) || /label_values\(/i.test(queryString))
        return 'QUERY';
    if (/^[A-Z]::/.test(queryString) || /L\('/.test(queryString))
        return 'QUERY';
    if (/^\s*(with|select)\b/i.test(queryString))
        return 'QUERY';
    return 'PROMQL_QUERY';
}
function extractVariableQuery(variable) {
    if (typeof variable.query === 'string')
        return variable.query;
    if (variable.query && typeof variable.query === 'object') {
        return variable.query.rawQuery || variable.query.query || variable.query.expr || '';
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
    }
    return '';
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
function normalizeTargetQuery(queryText, qtype, options = {}) {
    if (qtype !== 'promql')
        return queryText;
    if (!options.guancePromqlCompatible)
        return queryText;
    return normalizePromqlForGuance(queryText);
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
    if (!value || typeof value !== 'string')
        return 'auto';
    const normalized = value.trim();
    if (!normalized)
        return 'auto';
    return normalized;
}
function normalizePromqlForGuance(queryText) {
    if (typeof queryText !== 'string' || !queryText.trim())
        return queryText;
    let result = '';
    let index = 0;
    let braceDepth = 0;
    while (index < queryText.length) {
        const current = queryText[index];
        if (current === '{') {
            braceDepth++;
            result += current;
            index++;
            continue;
        }
        if (current === '}') {
            braceDepth = Math.max(0, braceDepth - 1);
            result += current;
            index++;
            continue;
        }
        if (braceDepth === 0 && /[A-Za-z_:]/.test(current)) {
            let end = index + 1;
            while (end < queryText.length && /[A-Za-z0-9_:]/.test(queryText[end]))
                end++;
            const token = queryText.slice(index, end);
            let lookahead = end;
            while (lookahead < queryText.length && /\s/.test(queryText[lookahead]))
                lookahead++;
            const next = queryText[lookahead];
            if (next === '{' || next === '[') {
                result += toGuancePromqlMetricName(token);
                index = end;
                continue;
            }
        }
        result += current;
        index++;
    }
    return result;
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
function toGuancePromqlMetricName(token) {
    if (!token)
        return token;
    if (token.includes(':'))
        return token;
    if (!token.includes('_'))
        return token;
    if (token.startsWith('__'))
        return token;
    if (PROMQL_RESERVED_WORDS.has(token))
        return token;
    const firstUnderscore = token.indexOf('_');
    if (firstUnderscore <= 0 || firstUnderscore === token.length - 1)
        return token;
    return `${token.slice(0, firstUnderscore)}:${token.slice(firstUnderscore + 1)}`;
}
function getDatasourceType(datasource) {
    return String((datasource === null || datasource === void 0 ? void 0 : datasource.type) || datasource || '').toLowerCase();
}
function isPrometheusLikeDatasource(datasourceType) {
    return datasourceType.includes('prometheus') || datasourceType.includes('guance-guance-datasource');
}
function isDqlLikeDatasource(datasourceType) {
    return (datasourceType.includes('mysql') ||
        datasourceType.includes('postgres') ||
        datasourceType.includes('mssql') ||
        datasourceType.includes('sql') ||
        datasourceType.includes('loki') ||
        datasourceType.includes('elasticsearch') ||
        datasourceType.includes('opensearch') ||
        datasourceType.includes('cloudwatch') ||
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
    const mapped = UNIT_MAP[String(unit).toLowerCase()];
    if (mapped)
        return mapped;
    return ['custom', String(unit)];
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
function normalizeQueryCode(refId, index) {
    if (typeof refId === 'string' && refId.trim())
        return refId.trim();
    const codePoint = 65 + index;
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
        .filter(([, current]) => {
        if (current === undefined)
            return false;
        if (Array.isArray(current) && current.length === 0)
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
