import assert from 'node:assert/strict'
import {
  buildMutationOperations,
  calculateTotals,
  createDrafts,
  newTransactionDraft,
} from '../../src/domain/transactionEditor.mjs'

const snapshot = {
  account: { id: '1', currency: { precision: 2 } },
  parties: [{ id: '1', name: 'Supplier' }],
  categories: [{
    id: '1',
    name: 'Housing',
    kind: 1,
    subcategories: [{ id: '1', name: 'Power' }],
  }],
  paymentMethods: [{ id: '1', name: 'Card' }],
  transactions: [{
    id: '10',
    date: '07/01/2026',
    valueDate: '07/02/2026',
    amount: '-42.50',
    partyId: '1',
    partyName: 'Supplier',
    categoryId: '1',
    categoryName: 'Housing',
    subcategoryId: '1',
    subcategoryName: 'Power',
    paymentMethodId: '1',
    paymentMethodName: 'Card',
    note: 'Invoice',
    paymentReference: null,
    marked: 1,
    voucher: null,
    bankReference: 'statement',
    protected: false,
    protectionReasons: [],
  }],
}

const rows = createDrafts(snapshot)
rows[0].note = 'Updated invoice'
let operations = buildMutationOperations(rows, snapshot)
assert.deepEqual(operations, [{
  type: 'updateTransaction',
  transactionId: '10',
  changes: { note: 'Updated invoice' },
}])

const created = newTransactionDraft(snapshot, 'new-1', '07/12/2026')
created.amount = '-10.00'
created.partyName = 'New Shop'
created.categoryName = 'Food'
created.subcategoryName = 'Groceries'
created.paymentMethodName = 'Card'
operations = buildMutationOperations([
  ...rows.map(row => ({ ...row, note: row.original.note })),
  created,
], snapshot)
assert.equal(operations.length, 1)
assert.equal(operations[0].type, 'createTransaction')
assert.equal(operations[0].partyName, 'New Shop')
assert.equal(operations[0].categoryName, 'Food')
assert.equal(operations[0].subcategoryName, 'Groceries')
assert.equal(operations[0].createMissing, true)
assert.equal(operations[0].paymentMethodId, '1')

const deleted = createDrafts(snapshot)
deleted[0].deleted = true
assert.deepEqual(buildMutationOperations(deleted, snapshot), [{
  type: 'deleteTransaction',
  transactionId: '10',
}])

const protectedRows = createDrafts({
  ...snapshot,
  transactions: [{
    ...snapshot.transactions[0],
    protected: true,
    protectionReasons: ['transfer'],
  }],
})
protectedRows[0].deleted = true
assert.throws(
  () => buildMutationOperations(protectedRows, snapshot),
  /cannot be deleted/u,
)

assert.deepEqual(calculateTotals([created], 2), {
  totalAmount: '-10.00',
  totalMarkedAmount: '0.00',
})

console.log('phase5 frontend editor tests passed')
