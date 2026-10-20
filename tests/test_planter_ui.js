const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const scripts = path.join(__dirname, '../src/webapp/scripts/tabs');
const home = fs.readFileSync(path.join(scripts, 'home.js'), 'utf8');
const formatter = home.match(/function secondsToMinsAndHours\(time\) \{[\s\S]*?\n\}/)[0];
const start = home.indexOf('  function getPlanterHTML(');
const renderer = home.slice(start, home.indexOf('\n  }', start) + 4);
const context = vm.createContext({
  Date: { now: () => 1000000 },
  fieldNectarIcons: {},
  toTitleCase: value => value,
});
vm.runInContext(formatter + '\n' + renderer, context);
for (const remaining of [0, -1]) {
  assert.match(context.getPlanterHTML('candy', 'stump', 0, 0, remaining),
    /class="time ready">Ready!</);
}
assert.match(context.getPlanterHTML('candy', 'stump', 0, 0, 3660), /1h 1m/);
assert.match(context.getPlanterHTML('candy', 'stump', 4660, 0, null), /1h 1m/);

const planters = fs.readFileSync(path.join(scripts, 'planters.js'), 'utf8');
const fallback = planters.match(/    if \(!Object\.prototype\.hasOwnProperty[\s\S]*?\n    \}/)[0];
for (const present of [false, true]) {
  const settings = { auto_planters_special_drop: 'candy_stump_glue' };
  if (present) settings.auto_planters_special_drop_queue = [];
  vm.runInNewContext(fallback, { settings });
  assert.deepEqual(Array.from(settings.auto_planters_special_drop_queue),
    present ? [] : ['candy_stump_glue']);
}
console.log('Planter readiness and route queue regressions passed.');
