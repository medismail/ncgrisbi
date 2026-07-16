import assert from 'node:assert/strict'
import {
  TRANSFER_CATEGORY,
  allowReconciledMutations,
  applyPartyCompletion,
  buildMutationOperations,
  createDrafts,
  newTransactionDraft,
  paymentMethodsForAmount,
} from '../../src/domain/transactionEditor.mjs'
import { decodeCompactSnapshot } from '../../src/domain/snapshotWire.mjs'

const snapshot = {
  account: { id: '1', currency: { precision: 2 } },
  accounts: [
    {
      id: '1', name: 'Current', closed: false,
      defaultDebitMethodId: '1', defaultCreditMethodId: '2',
    },
    {
      id: '2', name: 'Savings', closed: false,
      defaultDebitMethodId: '3', defaultCreditMethodId: '4',
    },
  ],
  parties: [{ id: '1', name: 'Shop' }],
  categories: [{
    id: '1', name: 'Food', kind: 1,
    subcategories: [{ id: '1', name: 'Groceries' }],
  }],
  paymentMethods: [
    { id: '1', name: 'Card', sign: 1, accountId: '1' },
    { id: '2', name: 'Deposit', sign: 2, accountId: '1' },
  ],
  paymentMethodsByAccount: {
    '1': [
      { id: '1', name: 'Card', sign: 1, accountId: '1' },
      { id: '2', name: 'Deposit', sign: 2, accountId: '1' },
    ],
    '2': [
      { id: '3', name: 'Transfer out', sign: 1, accountId: '2' },
      { id: '4', name: 'Transfer in', sign: 2, accountId: '2' },
    ],
  },
  completionByPartyId: {
    '1': {
      amount: '-12.50', categoryId: '1', subcategoryId: '1',
      paymentMethodId: '1', note: 'Last note', transferAccountId: null,
    },
  },
  transactions: [],
}

assert.deepEqual(
  paymentMethodsForAmount(snapshot, '1', '-1').map(item => item.id),
  ['1'],
)
assert.deepEqual(
  paymentMethodsForAmount(snapshot, '1', '1').map(item => item.id),
  ['2'],
)

const completed = newTransactionDraft(snapshot, 'new-1', '07/12/2026')
completed.partyName = 'Shop'
completed.paymentMethodName = ''
assert.equal(applyPartyCompletion(completed, snapshot), true)
assert.equal(completed.amount, '-12.50')
assert.equal(completed.categoryName, 'Food')
assert.equal(completed.subcategoryName, 'Groceries')
assert.equal(completed.paymentMethodName, 'Card')
assert.equal(completed.note, 'Last note')

const transfer = newTransactionDraft(snapshot, 'new-2', '07/12/2026')
Object.assign(transfer, {
  amount: '-100.00',
  categoryName: TRANSFER_CATEGORY,
  subcategoryName: 'Savings',
  paymentMethodName: 'Card',
  transferPaymentMethodName: 'Transfer in',
})
let operations = buildMutationOperations([transfer], snapshot)
assert.equal(operations[0].type, 'createTransfer')
assert.equal(operations[0].targetAccountId, '2')
assert.equal(operations[0].paymentMethodId, '1')
assert.equal(operations[0].targetPaymentMethodId, '4')

const normalTransaction = {
  id: '10', date: '07/10/2026', amount: '-25.00',
  partyId: '1', partyName: 'Shop', categoryId: '1', categoryName: 'Food',
  subcategoryId: '1', subcategoryName: 'Groceries', paymentMethodId: '1',
  paymentMethodName: 'Card', note: null, paymentReference: null, marked: 0,
  quickMarkable: true, voucher: null, bankReference: null, protected: false,
  protectionReasons: [], isTransfer: false,
}
const normalSnapshot = { ...snapshot, transactions: [normalTransaction] }
const normalDraft = createDrafts(normalSnapshot)[0]
normalDraft.editing = true
normalDraft.categoryName = TRANSFER_CATEGORY
normalDraft.subcategoryName = 'Savings'
normalDraft.transferPaymentMethodName = 'Transfer in'
operations = buildMutationOperations([normalDraft], normalSnapshot)
assert.equal(operations[0].type, 'convertTransactionToTransfer')
assert.equal(operations[0].transactionId, '10')
assert.equal(operations[0].targetAccountId, '2')

const transferTransaction = {
  ...normalTransaction,
  id: '20', amount: '-50.00', categoryId: '0', categoryName: null,
  subcategoryId: '0', subcategoryName: null, isTransfer: true,
  transferAccountId: '2', transferAccountName: 'Savings',
  transferPaymentMethodId: '4', transferPaymentMethodName: 'Transfer in',
}
const transferSnapshot = { ...snapshot, transactions: [transferTransaction] }
const transferDraft = createDrafts(transferSnapshot)[0]
transferDraft.editing = true
transferDraft.amount = '-55.00'
transferDraft.marked = 1
operations = buildMutationOperations([transferDraft], transferSnapshot)
assert.equal(operations[0].type, 'updateTransfer')
assert.equal(operations[0].changes.amount, '-55.00')
assert.equal('marked' in operations[0].changes, false)
assert.deepEqual(operations[1], {
  type: 'setTransactionMarks',
  marks: [['20', 1]],
})

const toNormal = createDrafts(transferSnapshot)[0]
toNormal.categoryName = 'Food'
toNormal.subcategoryName = 'Groceries'
operations = buildMutationOperations([toNormal], transferSnapshot)
assert.equal(operations[0].type, 'convertTransferToTransaction')
assert.equal(operations[0].categoryId, '1')
assert.equal(operations[0].subcategoryId, '1')

const deletedTransfer = createDrafts(transferSnapshot)[0]
deletedTransfer.deleted = true
operations = buildMutationOperations([deletedTransfer], transferSnapshot)
assert.equal(operations[0].type, 'deleteTransfer')
assert.equal(allowReconciledMutations(operations)[0].allowReconciled, true)

const protectedSnapshot = {
  ...snapshot,
  transactions: [{
    ...normalTransaction,
    id: '30', protected: true, protectionReasons: ['breakdown'],
  }],
}
const protectedDraft = createDrafts(protectedSnapshot)[0]
protectedDraft.marked = 1
assert.deepEqual(buildMutationOperations([protectedDraft], protectedSnapshot), [{
  type: 'setTransactionMarks',
  marks: [['30', 1]],
}])

const fiftySnapshot = {
  ...snapshot,
  transactions: Array.from({ length: 50 }, (_, index) => ({
    ...normalTransaction,
    id: String(index + 100),
  })),
}
const fiftyDrafts = createDrafts(fiftySnapshot)
for (const row of fiftyDrafts) row.marked = 1
operations = buildMutationOperations(fiftyDrafts, fiftySnapshot)
assert.equal(operations.length, 1)
assert.equal(operations[0].type, 'setTransactionMarks')
assert.equal(operations[0].marks.length, 50)

const decoded = decodeCompactSnapshot({
  v: 2,
  a: ['1', 'Current', 0, '1', 'Euro', 'EUR', '€', 2, '10.00', '0.00'],
  A: [
    ['1', 'Current', 0, '1', '1', '2', 0],
    ['2', 'Savings', 0, '1', '3', '4', 0],
  ],
  P: [['1', 'Shop']],
  C: [['1', 'Food', 1, [['1', 'Groceries']]]],
  M: [
    ['1', [['1', 'Card', 1, 0, 0, null]]],
    ['2', [['4', 'Transfer in', 2, 0, 0, null]]],
  ],
  T: [[
    '10', '07/01/2026', null, '-5.00', '1', '0', '0', '1', null,
    null, 0, null, null, '0', '11', null, 4, '2', '4',
  ]],
  H: [['1', '1', '-5.00', '1', '1', '1', 'N', null, null, null, null]],
  U: [3, 0, 0, '18-1-3', '11-12-31', '18-1-3'],
  W: [['missing-transfer-target', 'Broken transfer', 'Transaction', '99']],
})
assert.equal(decoded.transactions[0].isTransfer, true)
assert.equal(decoded.transactions[0].quickMarkable, true)
assert.equal(decoded.transactions[0].transferAccountName, 'Savings')
assert.equal(decoded.transactions[0].transferPaymentMethodName, 'Transfer in')
assert.equal(decoded.completionByPartyId['1'].note, 'N')
assert.equal(decoded.preferences.linesPerTransaction, 3)
assert.equal(decoded.preferences.transactionsView, '18-1-3')
assert.equal(decoded.warnings[0].code, 'missing-transfer-target')

console.log('phase6 editor and compact snapshot tests passed')
