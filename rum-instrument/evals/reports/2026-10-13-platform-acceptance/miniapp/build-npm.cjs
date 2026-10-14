const fs = require('fs');
const path = require('path');
const ci = require('./tooling/node_modules/miniprogram-ci');
(async () => {
  const project = path.join(__dirname, 'project');
  const result = await ci.packNpmManually({ packageJsonPath: path.join(project, 'package.json'), miniprogramNpmDistDir: project });
  fs.writeFileSync(path.join(__dirname, 'logs/npm-build-result.json'), JSON.stringify(result, null, 2));
  if (result.warnList.length) throw new Error('NPM packing warnings require review');
  const entry = path.join(project, 'miniprogram_npm/@cloudcare/rum-miniapp/index.js');
  if (!fs.existsSync(entry)) throw new Error('Missing packaged SDK entry');
  console.log(JSON.stringify({result, entry, bytes: fs.statSync(entry).size}));
})().catch(e => { console.error(e); process.exitCode = 1; });
