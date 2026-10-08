import assert from 'node:assert/strict'
import {
  sortTransactions,
} from '../../src/domain/transactionOrdering.mjs'
import {
  applyEditorDraft,
  applyPartyCompletionTrace,
  buildAccountDisplayModeOperation,
  buildResponsiveMutationOperations,
  cloneEditorDraft,
  createResponsiveDrafts,
  hasResponsivePendingChanges,
  newResponsiveDraft,
  pendingChangeSummary,
  preferredDisplayMode,
  setSelectedItem,
  undoPartyCompletion,
} from '../../src/domain/responsiveEditor.mjs'

const snapshot = {
  account: {
    id: '1',
    name: 'Current',
    currency: { id: '1', code: 'EUR', precision: 2 },
  },
  accounts: [
    { id: '1', name: 'Current', closed: false, defaultDebitMethodId: '1', defaultCreditMethodId: '2' },
    { id: '2', name: 'Savings', closed: false, defaultDebitMethodId: '3', defaultCreditMethodId: '4' },
  ],
  parties: [
    { id: '1', name: 'Shop' },
    { id: '2', name: 'Shop' },
  ],
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
    '2': {
      amount: '-12.50',
      categoryId: '1',
      subcategoryId: '1',
      paymentMethodId: '1',
      note: 'Latest purchase',
      paymentReference: null,
      voucher: null,
      bankReference: null,
      transferAccountId: null,
    },
  },
  transactions: [{
    id: '10',
    date: '07/10/2026',
    valueDate: null,
    amount: '-5.00',
    partyId: '1',
    partyName: 'Shop',
    categoryId: '1',
    categoryName: 'Food',
    subcategoryId: '1',
    subcategoryName: 'Groceries',
    paymentMethodId: '1',
    paymentMethodName: 'Card',
    note: null,
    paymentReference: null,
    marked: 0,
    voucher: null,
    bankReference: null,
    protected: false,
    protectionReasons: [],
    quickMarkable: true,
    isTransfer: false,
    transferAccountId: null,
    transferAccountName: null,
    transferPaymentMethodId: '0',
    transferPaymentMethodName: null,
  }, {
    id: '11',
    date: '07/11/2026',
    valueDate: null,
    amount: '-7.00',
    partyId: '1',
    partyName: 'Shop',
    categoryId: '1',
    categoryName: 'Food',
    subcategoryId: '1',
    subcategoryName: 'Groceries',
    paymentMethodId: '1',
    paymentMethodName: 'Card',
    note: null,
    paymentReference: null,
    marked: 0,
    voucher: null,
    bankReference: null,
    protected: false,
    protectionReasons: [],
    quickMarkable: true,
    isTransfer: false,
    transferAccountId: null,
    transferAccountName: null,
    transferPaymentMethodId: '0',
    transferPaymentMethodName: null,
  }],
}

const sortableRows = [
  { key: '3', transactionId: '3', date: '07/12/2026', partyName: 'Zulu', categoryName: 'Food', subcategoryName: 'Dining', isTransfer: false },
  { key: '2', transactionId: '2', date: '07/11/2026', partyName: 'Alpha', categoryName: 'Utilities', subcategoryName: 'Power', isTransfer: false },
  { key: '1', transactionId: '1', date: '07/10/2026', partyName: 'Alpha', categoryName: 'Food', subcategoryName: 'Groceries', isTransfer: false },
  { key: '4', transactionId: '4', date: '07/13/2026', partyName: '', categoryName: '', subcategoryName: '', isTransfer: false },
  { key: '5', transactionId: '5', date: '07/09/2026', partyName: 'Beta', categoryName: 'Ignored', subcategoryName: '', isTransfer: true },
]
assert.deepEqual(sortTransactions(sortableRows, 'date').map(row => row.key), ['4', '3', '2', '1', '5'])
assert.deepEqual(sortTransactions(sortableRows, 'party').map(row => row.key), ['2', '1', '5', '3', '4'])
assert.deepEqual(sortTransactions(sortableRows, 'category').map(row => row.key), ['3', '1', '5', '2', '4'])
assert.deepEqual(sortTransactions(sortableRows, 'unknown').map(row => row.key), ['4', '3', '2', '1', '5'])

assert.equal(preferredDisplayMode({ linesPerTransaction: 1 }), 'compact')
assert.equal(preferredDisplayMode({
  linesPerTransaction: 1,
  twoLinesShowed: true,
  threeLinesShowed: true,
}), 'compact')
assert.equal(preferredDisplayMode({ linesPerTransaction: 2 }), 'detailed')
assert.equal(preferredDisplayMode({ linesPerTransaction: 3 }), 'detailed')
assert.equal(buildAccountDisplayModeOperation('1', 'compact', 'compact'), null)
assert.deepEqual(buildAccountDisplayModeOperation('1', 'detailed', 'compact'), {
  type: 'setAccountDisplayMode',
  accountId: '1',
  mode: 'detailed',
})

const exactRows = createResponsiveDrafts(snapshot)
setSelectedItem(exactRows[0], 'party', snapshot.parties[1])
let operations = buildResponsiveMutationOperations([exactRows[0]], snapshot)
assert.equal(operations.length, 1)
assert.equal(operations[0].type, 'updateTransaction')
assert.equal(operations[0].changes.partyId, '2')

const markRows = createResponsiveDrafts(snapshot)
markRows[0].marked = 1
markRows[1].marked = 1
operations = buildResponsiveMutationOperations(markRows, snapshot)
assert.equal(operations.length, 1)
assert.equal(operations[0].type, 'setTransactionMarks')
assert.deepEqual(operations[0].marks, [['10', 1], ['11', 1]])

const firstNew = newResponsiveDraft(snapshot, 'new-1', '07/12/2026')
Object.assign(firstNew, {
  amount: '-9.00',
  partyName: 'Shop',
  partySelectionId: '2',
  categoryName: 'Food',
  categorySelectionId: '1',
  subcategoryName: 'Groceries',
  subcategorySelectionId: '1',
  paymentMethodName: 'Card',
  paymentMethodSelectionId: '1',
})
const secondNew = newResponsiveDraft(snapshot, 'new-2', '07/12/2026')
Object.assign(secondNew, {
  amount: '-10.00',
  partyName: 'Shop',
  partySelectionId: '1',
  categoryName: 'Food',
  categorySelectionId: '1',
  subcategoryName: 'Groceries',
  subcategorySelectionId: '1',
  paymentMethodName: 'Card',
  paymentMethodSelectionId: '1',
})
operations = buildResponsiveMutationOperations([firstNew, secondNew], snapshot)
assert.deepEqual(operations.map(operation => operation.type), ['createTransaction', 'createTransaction'])
assert.equal(hasResponsivePendingChanges([firstNew, secondNew]), true)
assert.equal(pendingChangeSummary([firstNew, secondNew]).created, 2)

// Regression: applying one editor payload must only update its matching row,
// then a second editor payload must remain independent.
const sequentialRows = createResponsiveDrafts(snapshot)
const firstEditorDraft = cloneEditorDraft(sequentialRows[0])
firstEditorDraft.note = 'Edited transaction 10'
applyEditorDraft(sequentialRows[0], firstEditorDraft)
assert.equal(sequentialRows[0].note, 'Edited transaction 10')
assert.equal(sequentialRows[1].note, null)
assert.equal(sequentialRows[0].locallyApplied, true)

const secondEditorDraft = cloneEditorDraft(sequentialRows[1])
secondEditorDraft.note = 'Edited transaction 11'
applyEditorDraft(sequentialRows[1], secondEditorDraft)
assert.equal(sequentialRows[0].note, 'Edited transaction 10')
assert.equal(sequentialRows[1].note, 'Edited transaction 11')
assert.equal(sequentialRows[1].locallyApplied, true)

const completion = newResponsiveDraft(snapshot, 'new-3', '07/12/2026')
setSelectedItem(completion, 'party', snapshot.parties[1])
const trace = applyPartyCompletionTrace(completion, snapshot)
assert.ok(trace)
assert.equal(completion.amount, '-12.50')
assert.equal(completion.categorySelectionId, '1')
assert.equal(completion.subcategorySelectionId, '1')
assert.equal(completion.paymentMethodSelectionId, '1')
assert.equal(completion.note, 'Latest purchase')
undoPartyCompletion(completion, trace, snapshot)
assert.equal(completion.amount, '0.00')
assert.equal(completion.note, '')

console.log('phase8a responsive batch UI domain tests passed')
