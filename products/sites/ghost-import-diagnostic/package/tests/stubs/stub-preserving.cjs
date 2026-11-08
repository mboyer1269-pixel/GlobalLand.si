'use strict';
// STUB: preserves all text.
const {build} = require('./stub-common.cjs');
module.exports = {htmlToLexical: h => build(h, false)};
