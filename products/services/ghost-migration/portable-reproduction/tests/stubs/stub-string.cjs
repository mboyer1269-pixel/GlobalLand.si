'use strict';
// STUB: returns a JSON string instead of an object.
const {build} = require('./stub-common.cjs');
module.exports = {htmlToLexical: h => JSON.stringify(build(h, false))};
