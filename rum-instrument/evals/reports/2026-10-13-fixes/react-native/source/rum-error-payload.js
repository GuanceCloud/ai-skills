'use strict';

// Error messages and arbitrary object fields may contain application data.
// Keep bounded categories and locations in maintained, allowlisted source files.
const categories = new Set(['Error', 'TypeError', 'RangeError', 'ReferenceError', 'SyntaxError']);
function rumErrorPayload(error, isFatal) {
  const category = error && categories.has(error.name) ? error.name : 'Error';
  const frames = [];
  const stack = error && typeof error.stack === 'string' ? error.stack.slice(0, 16384) : '';
  for (const line of stack.split('\n').slice(1, 33)) {
    const match = line.match(/(?:^|[/\\])(index\.js|App\.js|rum\.js):(\d{1,6}):(\d{1,6})\)?$/);
    if (match) frames.push(`at ${match[1]}:${match[2]}:${match[3]}`);
    if (frames.length === 12) break;
  }
  return { stack: frames.join('\n'), message: category, properties: { is_fatal: isFatal === true } };
}
module.exports = { rumErrorPayload };
