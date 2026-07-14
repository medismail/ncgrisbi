import assert from 'node:assert/strict'
import {
  TRANSFER_CATEGORY,
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
      id: '1',
      name: 'Current',
      closed: false,
      defaultDebitMethodId: '1',
      defaultCreditMethodId: '2',
    },
    {
      id: '2',
      name: 'Savings',
      closed: false,
      defaultDebitMethodId: '3',
      defaultCreditMethodId: '4',
    },
  ],
  parties: [{ id: '1', name: 'Shop' }],
  categories: [{
    id: '1',
    name: 'Food',
    kind: 1,
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
      amount: '-12.50',
      categoryId: '1',
      subcategoryId: '1',
      paymentMethodId: '1',
      note: 'Last note',
      transferAccountId: null,
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

const transferSnapshot = {
  ...snapshot,
  transactions: [{
    id: '20',
    date: '07/10/2026',
    amount: '-50.00',
    partyId: '1',
    partyName: 'Shop',
    categoryId: '0',
    categoryName: null,
    subcategoryId: '0',
    subcategoryName: null,
    paymentMethodId: '1',
    paymentMethodName: 'Card',
    note: null,
    paymentReference: null,
    marked: 0,
    voucher: null,
    bankReference: null,
    protected: false,
    protectionReasons: [],
    isTransfer: true,
    transferAccountId: '2',
    transferAccountName: 'Savings',
    transferPaymentMethodId: '4',
    transferPaymentMethodName: 'Transfer in',
  }],
}
const transferDraft = createDrafts(transferSnapshot)[0]
transferDraft.editing = true
transferDraft.amount = '-55.00'
operations = buildMutationOperations([transferDraft], transferSnapshot)
assert.equal(operations[0].type, 'updateTransfer')
assert.equal(operations[0].changes.amount, '-55.00')
transferDraft.deleted = true
operations = buildMutationOperations([transferDraft], transferSnapshot)
assert.equal(operations[0].type, 'deleteTransfer')

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
})
assert.equal(decoded.transactions[0].isTransfer, true)
assert.equal(decoded.transactions[0].transferAccountName, 'Savings')
assert.equal(decoded.transactions[0].transferPaymentMethodName, 'Transfer in')
assert.equal(decoded.completionByPartyId['1'].note, 'N')

console.log('phase5 revised editor tests passed')
