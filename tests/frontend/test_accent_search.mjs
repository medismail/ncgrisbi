import assert from 'node:assert/strict'
import { normalizeSearchText } from '../../src/domain/searchNormalization.mjs'
import { normalizeName } from '../../src/domain/transactionEditor.mjs'

const variants = [
  ['e', 'é', 'è', 'ê', 'ë', 'ē'],
  ['a', 'à', 'â', 'ä', 'á', 'ã', 'å'],
  ['i', 'í', 'ì', 'î', 'ï'],
  ['o', 'ó', 'ò', 'ô', 'ö'],
  ['u', 'ú', 'ù', 'û', 'ü'],
  ['c', 'ç'],
]

for (const group of variants) {
  for (const value of group) {
    assert.equal(normalizeSearchText(value), group[0], `Expected ${value} to match ${group[0]}`)
    assert.equal(normalizeSearchText(value.toUpperCase()), group[0])
  }
}

assert.equal(normalizeSearchText('  ÉPİCERIE   DU  CENTRE '), 'epicerie du centre')
assert.equal(normalizeSearchText('Cafe\u0301'), 'cafe')
assert.equal(normalizeSearchText(null), '')

// Search equivalence must never become Grisbi record identity equivalence.
assert.notEqual(normalizeName('Café'), normalizeName('Cafe'))
assert.notEqual(normalizeName('Côte'), normalizeName('Cote'))

console.log('Accent-insensitive search normalization tests passed')
