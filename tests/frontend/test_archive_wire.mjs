import assert from 'node:assert/strict'
import { decodeCompactSnapshot } from '../../src/domain/snapshotWire.mjs'
import { calculateTotals } from '../../src/domain/transactionEditor.mjs'

const transaction = [
  '1', '01/01/2026', null, '-10.00', '1', '0', '0', '1',
  'January', null, 0, null, null, '0', null, null, 0,
  null, null, 1,
]
const wire = {
  v: 2,
  a: ['1', 'Current', 0, '1', 'Euro', 'EUR', '€', 2, '-10.00', '-10.00', '0.00', '-10.00', '-10.00'],
  A: [['1', 'Current', 0, '1', '1', '1', 0]],
  P: [['1', 'Shop']],
  C: [],
  M: [['1', [['1', 'Card', 1, 1, 0, null]]]],
  T: [transaction],
  H: [],
  U: [],
  W: [],
  Z: 1123,
}
const snapshot = decodeCompactSnapshot(wire)
assert.equal(snapshot.transactions.length, 1)
assert.equal(snapshot.archiveTotal, 1123)
assert.equal(snapshot.transactions[0].ar, 1)
assert.equal(snapshot.transactions[0].protected, true)
assert.ok(snapshot.transactions[0].protectionReasons.includes('archived'))
assert.equal(snapshot.transactions[0].partyName, 'Shop')
assert.equal(snapshot.account.totalAmount, '-10.00')
assert.equal(snapshot.account.archivedBalance, '-10.00')
assert.deepEqual(calculateTotals([], 2, '0', '-10.00', '-10.00'), {
  totalAmount: '-10.00', totalMarkedAmount: '-10.00',
})
assert.deepEqual(calculateTotals([
  { amount: '-5.00', marked: 1, deleted: false },
], 2, '0', '-10.00', '-10.00'), {
  totalAmount: '-15.00', totalMarkedAmount: '-15.00',
})

// The normal editor keeps a single numeric archive flag per row.
const active = decodeCompactSnapshot({ ...wire, T: [[...transaction.slice(0, -1), 0]], Z: null })
assert.equal(active.transactions[0].ar, 0)
assert.equal(active.transactions[0].protected, false)
assert.equal(active.archiveTotal, null)

// Older compact snapshots lacking the optional archive flag remain readable.
const older = decodeCompactSnapshot({ ...wire, T: [transaction.slice(0, -1)], Z: null })
assert.equal(older.transactions[0].ar, 0)
assert.equal(older.transactions[0].protected, false)

console.log('Compact archive row flags and paged snapshot tests passed')
