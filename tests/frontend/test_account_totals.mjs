import assert from 'node:assert/strict'
import {
  mergeAccountTotals,
  snapshotAccountTotals,
} from '../../src/domain/accountTotals.mjs'

const accounts = [
  {
    id: '1',
    name: 'Main',
    total: { total_amount: -10, total_marked_amount: -10 },
  },
  {
    id: '2',
    name: 'Savings',
    total: { total_amount: 25, total_marked_amount: 5 },
  },
]

assert.deepEqual(snapshotAccountTotals({
  id: '1',
  totalAmount: '-12.50',
  totalMarkedAmount: '-10.00',
}), {
  '1': {
    total_amount: -12.5,
    total_marked_amount: -10,
  },
})
assert.deepEqual(snapshotAccountTotals(null), {})

const unchanged = mergeAccountTotals(accounts, {
  '1': { total_amount: -10, total_marked_amount: -10 },
})
assert.equal(unchanged, accounts, 'unchanged totals should preserve the accounts array')

const updated = mergeAccountTotals(accounts, {
  '1': { total_amount: -15, total_marked_amount: -10 },
})
assert.notEqual(updated, accounts, 'a changed total should publish a reactive array update')
assert.notEqual(updated[0], accounts[0], 'only the affected account should be replaced')
assert.equal(updated[1], accounts[1], 'unaffected account objects should be preserved')
assert.deepEqual(updated[0].total, {
  total_amount: -15,
  total_marked_amount: -10,
})

const transferUpdate = mergeAccountTotals(updated, {
  '1': { total_amount: -20, total_marked_amount: -10 },
  '2': { total_amount: 30, total_marked_amount: 5 },
})
assert.equal(transferUpdate[0].total.total_amount, -20)
assert.equal(transferUpdate[1].total.total_amount, 30)

const ignoredInvalid = mergeAccountTotals(transferUpdate, {
  '1': { total_amount: 'not-a-number', total_marked_amount: -10 },
})
assert.equal(ignoredInvalid, transferUpdate, 'invalid backend totals must not corrupt account state')

console.log('account total state merge tests passed')
