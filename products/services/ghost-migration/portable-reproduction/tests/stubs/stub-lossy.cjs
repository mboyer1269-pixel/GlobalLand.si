'use strict';
// STUB: drops text in quotes containing <br> without <p>, imitating the reported symptom.
const {build} = require('./stub-common.cjs');
module.exports = {htmlToLexical: h => build(h, true)};
