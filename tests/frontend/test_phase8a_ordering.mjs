import assert from 'node:assert/strict'
import { sortTransactionsRecentFirst } from '../../src/domain/transactionOrdering.mjs'

const rows = [
  { key: 'transaction-8', transactionId: '8', date: '07/21/2026' },
  { key: 'transaction-12', transactionId: '12', date: '07/22/2026' },
  { key: 'transaction-11', transactionId: '11', date: '07/22/2026' },
  { key: 'transaction-999', transactionId: '999', date: '07/20/2026' },
]
assert.deepEqual(
  sortTransactionsRecentFirst(rows).map(row => row.transactionId),
  ['12', '11', '8', '999'],
)

const sameDate = [
  { key: 'transaction-9', transactionId: '9', date: '07/22/2026' },
  { key: 'transaction-100000000000000000001', transactionId: '100000000000000000001', date: '07/22/2026' },
  { key: 'transaction-10', transactionId: '10', date: '07/22/2026' },
]
assert.deepEqual(
  sortTransactionsRecentFirst(sameDate).map(row => row.transactionId),
  ['100000000000000000001', '10', '9'],
)

const pending = [
  { key: 'transaction-15', transactionId: '15', date: '07/22/2026' },
  { key: 'new-1', transactionId: null, date: '07/22/2026' },
  { key: 'new-2', transactionId: null, date: '07/22/2026' },
]
assert.deepEqual(
  sortTransactionsRecentFirst(pending).map(row => row.key),
  ['new-2', 'new-1', 'transaction-15'],
)

const original = [...rows]
sortTransactionsRecentFirst(rows)
assert.deepEqual(rows, original)

console.log('phase8a transaction ordering tests passed')
