const ELASTICSEARCH_TRACE_SOURCE = 'T::RE(`.*`)';

// These rules are derived from the real Grafana dashboard
// `/home/liurui/Downloads/问题定位大盘-1775721080549.json`.
// Keep this file as the single maintenance point for Elasticsearch -> DQL mapping.
export const ELASTICSEARCH_DQL_RULES = {
  source: ELASTICSEARCH_TRACE_SOURCE,
  fields: {
    'tag.otel@library@name': {
      targetField: 'otel_library_name',
      kind: 'string',
    },
    'tag.net@peer@name': {
      targetField: 'net_peer_name',
      kind: 'string',
    },
    'tag.error': {
      targetField: 'status',
      kind: 'status_bool',
    },
    'tag.otel@status_code': {
      targetField: 'status',
      kind: 'status_code',
    },
    'process.serviceName': {
      targetField: 'service',
      kind: 'string',
    },
    'tag.span@kind': {
      targetField: 'span_kind',
      kind: 'string',
    },
    'tag.http@route': {
      targetField: 'http_route',
      kind: 'string',
    },
    'tag.http@url': {
      targetField: 'http_url',
      kind: 'string',
    },
    duration: {
      targetField: 'duration',
      kind: 'number',
    },
  },
};

export function isElasticsearchDatasource(datasourceType) {
  return datasourceType.includes('elasticsearch') || datasourceType.includes('opensearch');
}

export function convertElasticsearchQueryToDql(queryText, target = {}) {
  if (typeof queryText !== 'string' || !queryText.trim()) {
    return {
      queryText,
      conversionInfo: undefined,
    };
  }

  const filterResult = convertElasticsearchFilters(queryText);
  if (filterResult.status !== 'mapped') {
    return {
      queryText,
      conversionInfo: buildElasticsearchConversionInfo(queryText, '', filterResult),
    };
  }

  const queryResult = buildElasticsearchDqlQuery(target, filterResult.filters);
  return {
    queryText: queryResult.status === 'mapped' ? queryResult.queryText : queryText,
    conversionInfo: buildElasticsearchConversionInfo(queryText, queryResult.queryText, queryResult),
  };
}

function buildElasticsearchDqlQuery(target, filters) {
  const metrics = Array.isArray(target.metrics) ? target.metrics : [];
  const bucketAggs = Array.isArray(target.bucketAggs) ? target.bucketAggs : [];
  const whereClause = buildWhereClause(filters);

  if (metrics.some((metric) => String(metric?.type || '') === 'raw_data')) {
    return buildRawTraceQuery(target, whereClause);
  }

  const metricResult = buildMetricExpressions(metrics);
  if (metricResult.status !== 'mapped') {
    return metricResult;
  }

  const groupResult = buildGroupByClause(bucketAggs);
  if (groupResult.status !== 'mapped') {
    return groupResult;
  }

  const sortAndLimitClause = buildSortAndLimitClause(bucketAggs, metricResult.primarySortExpr);
  if (sortAndLimitClause.status !== 'mapped') {
    return sortAndLimitClause;
  }

  const queryParts = [
    `${ELASTICSEARCH_TRACE_SOURCE}:(${metricResult.metricExpressions.join(', ')})`,
    whereClause,
    groupResult.groupByClause,
    sortAndLimitClause.value,
  ].filter(Boolean);

  return {
    status: 'mapped',
    queryText: queryParts.join(' '),
    diagnostics: [
      '[info] ELASTICSEARCH_QUERY_MAPPED: lucene-style filters and bucket aggregations were lowered to DQL trace query syntax',
    ],
  };
}

function buildRawTraceQuery(target, whereClause) {
  const metrics = Array.isArray(target.metrics) ? target.metrics : [];
  const rawMetric = metrics.find((metric) => String(metric?.type || '') === 'raw_data');
  const size = Number(rawMetric?.settings?.size);
  const limitClause = Number.isFinite(size) && size > 0 ? `LIMIT ${Math.trunc(size)}` : '';

  return {
    status: 'mapped',
    queryText: [ `${ELASTICSEARCH_TRACE_SOURCE}:(traces)`, whereClause, limitClause ].filter(Boolean).join(' '),
    diagnostics: [
      '[info] ELASTICSEARCH_RAW_DATA_MAPPED: raw_data metric was lowered to trace record query form',
    ],
  };
}

function buildMetricExpressions(metrics) {
  if (!Array.isArray(metrics) || metrics.length === 0) {
    return unsupportedMetric('missing metric definition');
  }

  const metricExpressions = [];
  let primarySortExpr = '';

  for (const metric of metrics) {
    const metricType = String(metric?.type || '').trim().toLowerCase();
    if (metricType === 'count') {
      const expr = 'count(`*`)';
      metricExpressions.push(expr);
      primarySortExpr ||= expr;
      continue;
    }
    if (metricType === 'avg') {
      const fieldExpression = buildMetricFieldExpression(metric);
      if (!fieldExpression) {
        return unsupportedMetric(`avg metric requires supported field expression: ${String(metric?.field || '')}`);
      }
      const expr = `avg(${fieldExpression})`;
      metricExpressions.push(expr);
      primarySortExpr ||= expr;
      continue;
    }
    if (metricType === 'percentiles') {
      const fieldExpression = buildMetricFieldExpression(metric);
      if (!fieldExpression) {
        return unsupportedMetric(`percentiles metric requires supported field expression: ${String(metric?.field || '')}`);
      }
      const percents = Array.isArray(metric?.settings?.percents) ? metric.settings.percents : [];
      const percentileExpressions = percents
        .map((value) => Number.parseInt(String(value), 10))
        .filter((value) => Number.isFinite(value) && value > 0)
        .map((value) => `p${value}(${fieldExpression})`);
      if (percentileExpressions.length === 0) {
        return unsupportedMetric('percentiles metric requires at least one percentile value');
      }
      metricExpressions.push(...percentileExpressions);
      primarySortExpr ||= percentileExpressions[0];
      continue;
    }
    if (metricType === 'raw_data') {
      continue;
    }
    return unsupportedMetric(`unsupported metric type "${metricType}"`);
  }

  if (metricExpressions.length === 0) {
    return unsupportedMetric('no executable Elasticsearch metric expressions were produced');
  }

  return {
    status: 'mapped',
    metricExpressions,
    primarySortExpr,
  };
}

function unsupportedMetric(message) {
  return {
    status: 'unsupported',
    unsupportedClass: 'converter-fixable',
    diagnostics: [
      `[error] ELASTICSEARCH_METRIC_UNSUPPORTED: ${message}`,
    ],
    queryText: '',
  };
}

function buildMetricFieldExpression(metric) {
  const rawField = String(metric?.field || '').trim();
  if (!rawField) {
    return '';
  }

  const rule = ELASTICSEARCH_DQL_RULES.fields[rawField];
  if (!rule?.targetField) {
    return '';
  }

  const script = String(metric?.settings?.script || '').replace(/\s+/g, '');
  if (script === '_value/1000') {
    return `\`${rule.targetField}\` / 1000`;
  }
  return `\`${rule.targetField}\``;
}

function buildGroupByClause(bucketAggs) {
  const groupFields = [];

  for (const bucketAgg of Array.isArray(bucketAggs) ? bucketAggs : []) {
    const bucketType = String(bucketAgg?.type || '').trim().toLowerCase();
    if (bucketType === 'date_histogram') {
      continue;
    }
    if (bucketType !== 'terms') {
      return {
        status: 'unsupported',
        unsupportedClass: 'converter-fixable',
        diagnostics: [
          `[error] ELASTICSEARCH_BUCKET_UNSUPPORTED: unsupported bucket aggregation type "${bucketType}"`,
        ],
        queryText: '',
      };
    }

    const rule = ELASTICSEARCH_DQL_RULES.fields[String(bucketAgg?.field || '').trim()];
    if (!rule?.targetField) {
      return {
        status: 'unsupported',
        unsupportedClass: 'converter-fixable',
        diagnostics: [
          `[error] ELASTICSEARCH_BUCKET_FIELD_UNSUPPORTED: unsupported bucket field "${String(bucketAgg?.field || '')}"`,
        ],
        queryText: '',
      };
    }

    const fieldExpr = `\`${rule.targetField}\``;
    if (!groupFields.includes(fieldExpr)) {
      groupFields.push(fieldExpr);
    }
  }

  return {
    status: 'mapped',
    groupByClause: groupFields.length ? `BY ${groupFields.join(', ')}` : '',
  };
}

function buildSortAndLimitClause(bucketAggs, primarySortExpr) {
  const termsBucket = (Array.isArray(bucketAggs) ? bucketAggs : []).find(
    (bucketAgg) => String(bucketAgg?.type || '').trim().toLowerCase() === 'terms'
  );
  if (!termsBucket) {
    return { status: 'mapped', value: '' };
  }

  const settings = termsBucket.settings || {};
  const size = Number(settings.size);
  const order = String(settings.order || '').trim().toLowerCase();
  const orderBy = String(settings.orderBy || '').trim();

  if (!(Number.isFinite(size) && size > 0)) {
    return { status: 'mapped', value: '' };
  }

  if (orderBy === '1' || orderBy === '_count') {
    const sortDirection = order === 'asc' ? 'ASC' : 'DESC';
    return {
      status: 'mapped',
      value: `SORDER BY ${primarySortExpr} ${sortDirection} SLIMIT ${Math.trunc(size)}`,
    };
  }

  if (orderBy === '_term' || orderBy === '_key') {
    return {
      status: 'mapped',
      value: `SLIMIT ${Math.trunc(size)}`,
    };
  }

  if (!orderBy) {
    return {
      status: 'mapped',
      value: `SLIMIT ${Math.trunc(size)}`,
    };
  }

  return {
    status: 'unsupported',
    unsupportedClass: 'converter-fixable',
    diagnostics: [
      `[error] ELASTICSEARCH_SORT_UNSUPPORTED: unsupported terms orderBy "${orderBy}"`,
    ],
    queryText: '',
  };
}

function convertElasticsearchFilters(queryText) {
  const clauses = splitTopLevelAnd(queryText);
  const filters = [];

  for (const clause of clauses) {
    const parsedClause = parseFilterClause(clause);
    if (!parsedClause) {
      return unsupportedFilter(`unsupported lucene clause "${clause}"`);
    }

    const rule = ELASTICSEARCH_DQL_RULES.fields[parsedClause.sourceField];
    if (!rule?.targetField) {
      return unsupportedFilter(`unsupported filter field "${parsedClause.sourceField}"`);
    }

    const convertedFilter = mapFilterClause(parsedClause, rule);
    if (!convertedFilter) {
      return unsupportedFilter(`unsupported filter value for "${parsedClause.sourceField}"`);
    }
    filters.push(convertedFilter);
  }

  return {
    status: 'mapped',
    filters: prioritizeFilters(filters),
  };
}

function unsupportedFilter(message) {
  return {
    status: 'unsupported',
    unsupportedClass: 'converter-fixable',
    diagnostics: [
      `[error] ELASTICSEARCH_FILTER_UNSUPPORTED: ${message}`,
    ],
    filters: [],
  };
}

function splitTopLevelAnd(input) {
  const clauses = [];
  let current = '';
  let quote = '';

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

    if (char === '"' || char === '\'') {
      quote = char;
      current += char;
      continue;
    }

    if (input.slice(index).match(/^AND\b/)) {
      const before = index === 0 ? ' ' : input[index - 1];
      const after = input[index + 3] || ' ';
      if (/\s/.test(before) && /\s/.test(after)) {
        if (current.trim()) {
          clauses.push(current.trim());
        }
        current = '';
        index += 2;
        continue;
      }
    }

    current += char;
  }

  if (current.trim()) {
    clauses.push(current.trim());
  }

  return clauses;
}

function parseFilterClause(clause) {
  const trimmedClause = String(clause || '').trim();
  if (!trimmedClause) {
    return null;
  }

  let negative = false;
  let normalizedClause = trimmedClause;
  if (normalizedClause.startsWith('-')) {
    negative = true;
    normalizedClause = normalizedClause.slice(1).trim();
  }

  const match = normalizedClause.match(/^([^:]+):\s*(.+)$/);
  if (!match) {
    return null;
  }

  const sourceField = match[1].trim();
  const rawValue = match[2].trim();
  if (!sourceField || !rawValue) {
    return null;
  }

  let comparator = '=';
  let value = rawValue;

  if (value.startsWith('>=')) {
    comparator = '>=';
    value = value.slice(2).trim();
  } else if (value.startsWith('<=')) {
    comparator = '<=';
    value = value.slice(2).trim();
  } else if (value.startsWith('>')) {
    comparator = '>';
    value = value.slice(1).trim();
  } else if (value.startsWith('<')) {
    comparator = '<';
    value = value.slice(1).trim();
  }

  return {
    negative,
    sourceField,
    comparator,
    value: unwrapQuoted(value),
  };
}

function unwrapQuoted(value) {
  const trimmedValue = String(value || '').trim();
  if (trimmedValue.length < 2) {
    return trimmedValue;
  }
  const first = trimmedValue[0];
  const last = trimmedValue.at(-1);
  if ((first === '"' || first === '\'') && first === last) {
    return trimmedValue.slice(1, -1);
  }
  return trimmedValue;
}

function mapFilterClause(parsedClause, rule) {
  const mappedValue = mapFilterValue(parsedClause, rule);
  if (!mappedValue) {
    return null;
  }

  const operator = normalizeOperator(parsedClause, rule, mappedValue);
  if (!operator) {
    return null;
  }

  return {
    field: rule.targetField,
    operator,
    value: mappedValue.value,
    valueType: mappedValue.valueType,
  };
}

function mapFilterValue(parsedClause, rule) {
  if (rule.kind === 'status_bool') {
    const normalized = String(parsedClause.value || '').trim().toLowerCase();
    if (normalized === 'true') {
      return { value: 'error', valueType: 'string' };
    }
    if (normalized === 'false') {
      return { value: 'error', valueType: 'string', invertMeaning: true };
    }
    return null;
  }

  if (rule.kind === 'status_code') {
    const normalized = String(parsedClause.value || '').trim().toUpperCase();
    if (normalized === 'ERROR') {
      return { value: 'error', valueType: 'string' };
    }
    if (normalized === 'OK' || normalized === 'UNSET') {
      return { value: 'error', valueType: 'string', invertMeaning: true };
    }
    return { value: parsedClause.value, valueType: 'string' };
  }

  if (rule.kind === 'number') {
    const numericValue = Number(parsedClause.value);
    if (!Number.isFinite(numericValue)) {
      return null;
    }
    return { value: numericValue, valueType: 'number' };
  }

  return { value: parsedClause.value, valueType: 'string' };
}

function normalizeOperator(parsedClause, rule, mappedValue) {
  if (['>', '>=', '<', '<='].includes(parsedClause.comparator)) {
    return parsedClause.negative ? null : parsedClause.comparator;
  }

  if (mappedValue.invertMeaning) {
    return parsedClause.negative ? '=' : '!=';
  }

  return parsedClause.negative ? '!=' : '=';
}

function prioritizeFilters(filters) {
  return [...filters].sort((left, right) => {
    if (left.field === 'status' && right.field !== 'status') {
      return -1;
    }
    if (left.field !== 'status' && right.field === 'status') {
      return 1;
    }
    return 0;
  });
}

function buildWhereClause(filters) {
  if (!Array.isArray(filters) || filters.length === 0) {
    return '';
  }

  return `{ ${filters.map(formatFilter).join(' and ')} }`;
}

function formatFilter(filter) {
  return `\`${filter.field}\` ${filter.operator} ${formatFilterValue(filter.value, filter.valueType)}`;
}

function formatFilterValue(value, valueType) {
  if (valueType === 'number') {
    return String(value);
  }
  return `'${escapeDqlString(String(value))}'`;
}

function escapeDqlString(value) {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function buildElasticsearchConversionInfo(originalQuery, convertedQuery, result) {
  return pruneEmpty({
    tool: 'grafana-elasticsearch-to-dql',
    status: result.status || 'unsupported',
    unsupportedClass: result.unsupportedClass || undefined,
    source: ELASTICSEARCH_TRACE_SOURCE,
    originalQuery,
    convertedQuery: result.status === 'mapped' ? convertedQuery : undefined,
    diagnostics: Array.isArray(result.diagnostics) && result.diagnostics.length ? result.diagnostics : undefined,
  });
}

function pruneEmpty(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => pruneEmpty(item))
      .filter((item) => item !== undefined);
  }
  if (value && typeof value === 'object') {
    const next = {};
    for (const [key, child] of Object.entries(value)) {
      const normalizedChild = pruneEmpty(child);
      if (normalizedChild === undefined) {
        continue;
      }
      if (Array.isArray(normalizedChild) && normalizedChild.length === 0) {
        continue;
      }
      if (
        normalizedChild &&
        typeof normalizedChild === 'object' &&
        !Array.isArray(normalizedChild) &&
        Object.keys(normalizedChild).length === 0
      ) {
        continue;
      }
      next[key] = normalizedChild;
    }
    return Object.keys(next).length ? next : undefined;
  }
  if (value === undefined || value === null || value === '') {
    return undefined;
  }
  return value;
}
