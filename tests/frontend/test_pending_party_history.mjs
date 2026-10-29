import assert from 'node:assert/strict'
import {
  applyEditorDraft,
  applyPartyCompletionTrace,
  buildResponsiveMutationOperations,
  createResponsiveDrafts,
  newResponsiveDraft,
  setSelectedItem,
  undoPartyCompletion,
} from '../../src/domain/responsiveEditor.mjs'
import {
  partyChoicesWithPending,
  snapshotWithPendingPartyHistory,
} from '../../src/domain/pendingPartySuggestions.mjs'

const snapshot = {
  account: { id: '1', name: 'Current', currency: { id: '1', code: 'EUR', precision: 2 } },
  accounts: [{
    id: '1', name: 'Current', closed: false, defaultDebitMethodId: '1', defaultCreditMethodId: '0',
  }, {
    id: '2', name: 'Savings', closed: false, defaultDebitMethodId: '3', defaultCreditMethodId: '4',
  }],
  parties: [{ id: '1', name: 'Café' }, { id: '2', name: 'Shop' }],
  categories: [{
    id: '1', name: 'Food', kind: 1, subcategories: [{ id: '1', name: 'Groceries' }],
  }, {
    id: '2', name: 'Bills', kind: 1, subcategories: [{ id: '1', name: 'Electricity' }],
  }],
  paymentMethods: [{ id: '1', name: 'Debit', sign: 1, accountId: '1' }, {
    id: '2', name: 'Bank card', sign: 1, accountId: '1',
  }],
  paymentMethodsByAccount: {
    '1': [{ id: '1', name: 'Debit', sign: 1, accountId: '1' }, {
      id: '2', name: 'Bank card', sign: 1, accountId: '1',
    }],
    '2': [{ id: '3', name: 'Outgoing', sign: 1, accountId: '2' }, {
      id: '4', name: 'Incoming', sign: 2, accountId: '2',
    }],
  },
  completionByPartyId: {
    '2': {
      sourceAccountId: '1', amount: '-9.00', categoryId: '1', subcategoryId: '1',
      paymentMethodId: '1', note: 'Saved history', transferAccountId: null,
    },
  },
  transactions: [{
    id: '10', date: '07/10/2026', valueDate: null, amount: '-9.00',
    partyId: '2', partyName: 'Shop', categoryId: '1', categoryName: 'Food',
    subcategoryId: '1', subcategoryName: 'Groceries', paymentMethodId: '1',
    paymentMethodName: 'Debit', note: 'Saved history', paymentReference: null,
    voucher: null, bankReference: null, marked: 0, protected: false,
    quickMarkable: true, isTransfer: false,
  }],
}

function applied(row, values, order) {
  applyEditorDraft(row, { ...row, ...values })
  row.localCompletionOrder = order
  return row
}

function complete(snap, choice) {
  const draft = newResponsiveDraft(snap, 'next', '07/14/2026')
  setSelectedItem(draft, 'party', choice)
  return { draft, trace: applyPartyCompletionTrace(draft, snap) }
}

// The saved party hint is stale until Save all, but Save draft must override it.
const savedRow = createResponsiveDrafts(snapshot)[0]
applied(savedRow, {
  amount: '-42.50', categoryName: 'Bills', categorySelectionId: '2',
  subcategoryName: 'Electricity', subcategorySelectionId: '1',
  paymentMethodName: 'Bank card', paymentMethodSelectionId: '2',
  note: 'Revised local history', paymentReference: 'NEW-REF',
  voucher: 'NEW-VOUCHER', bankReference: 'NEW-BANK',
}, 1)
const withEdited = snapshotWithPendingPartyHistory(snapshot, [savedRow])
assert.equal(snapshot.completionByPartyId['2'].amount, '-9.00')
assert.equal(withEdited.completionByPartyId['2'].amount, '-42.50')
const { draft: fromEdited, trace: editedTrace } = complete(withEdited, snapshot.parties[1])
assert.ok(editedTrace)
assert.equal(fromEdited.amount, '-42.50')
assert.equal(fromEdited.categoryName, 'Bills')
assert.equal(fromEdited.categorySelectionId, '2')
assert.equal(fromEdited.subcategoryName, 'Electricity')
assert.equal(fromEdited.subcategorySelectionId, '1')
assert.equal(fromEdited.paymentMethodName, 'Bank card')
assert.equal(fromEdited.paymentMethodSelectionId, '2')
assert.equal(fromEdited.note, 'Revised local history')
assert.equal(fromEdited.paymentReference, 'NEW-REF')
assert.equal(fromEdited.voucher, 'NEW-VOUCHER')
assert.equal(fromEdited.bankReference, 'NEW-BANK')
undoPartyCompletion(fromEdited, editedTrace, withEdited)
assert.equal(fromEdited.amount, '0.00')
assert.equal(fromEdited.note, '')

// A new locally applied transaction takes precedence over an older applied edit.
const newShop = newResponsiveDraft(snapshot, 'new-1', '07/12/2026')
applied(newShop, {
  partyName: 'Shop', partySelectionId: '2',
  amount: '-19.00', categoryName: 'Food', categorySelectionId: '1',
  subcategoryName: 'Groceries', subcategorySelectionId: '1',
  paymentMethodName: 'Debit', paymentMethodSelectionId: '1',
  note: 'More recent draft',
}, 2)
let history = snapshotWithPendingPartyHistory(snapshot, [savedRow, newShop])
assert.equal(complete(history, snapshot.parties[1]).draft.note, 'More recent draft')

// Re-applying an earlier row overrides newer history by local save order, not date.
applied(savedRow, { amount: '-55.00', note: 'Latest edited values' }, 3)
history = snapshotWithPendingPartyHistory(snapshot, [savedRow, newShop])
assert.equal(complete(history, snapshot.parties[1]).draft.amount, '-55.00')
assert.equal(complete(history, snapshot.parties[1]).draft.note, 'Latest edited values')

// New party + new category and subcategory are never given invented IDs.
const newParty = newResponsiveDraft(snapshot, 'new-2', '07/13/2026')
applied(newParty, {
  partyName: 'Épicerie du Centre', partySelectionId: null,
  categoryName: 'Home care', categorySelectionId: null,
  subcategoryName: 'Plumbing', subcategorySelectionId: null,
  amount: '-33.00', paymentMethodName: 'Bank card', paymentMethodSelectionId: '2',
  note: 'Draft for new party',
}, 4)
const rows = [savedRow, newShop, newParty]
history = snapshotWithPendingPartyHistory(snapshot, rows)
const pendingChoice = partyChoicesWithPending(snapshot.parties, rows)[0]
assert.equal(pendingChoice.name, 'Épicerie du Centre')
assert.equal(pendingChoice.id, null)
const { draft: nextParty, trace: pendingTrace } = complete(history, pendingChoice)
assert.ok(pendingTrace)
assert.equal(nextParty.partySelectionId, null)
assert.equal(nextParty.amount, '-33.00')
assert.equal(nextParty.categoryName, 'Home care')
assert.equal(nextParty.subcategoryName, 'Plumbing')
assert.equal(nextParty.categorySelectionId, null)
assert.equal(nextParty.subcategorySelectionId, null)
assert.equal(nextParty.paymentMethodName, 'Bank card')
assert.equal(nextParty.paymentMethodSelectionId, '2')
assert.equal(nextParty.note, 'Draft for new party')
const operations = buildResponsiveMutationOperations([newParty, nextParty], snapshot)
assert.equal(operations.length, 2)
assert.equal(operations[1].partyName, 'Épicerie du Centre')
assert.equal(operations[1].categoryName, 'Home care')
assert.equal(operations[1].subcategoryName, 'Plumbing')
assert.equal(operations[1].createMissing, true)

// Existing transaction assigned to a new party also offers local completion.
applied(savedRow, { partyName: 'Local Contractor', partySelectionId: null }, 5)
history = snapshotWithPendingPartyHistory(snapshot, rows)
const localChoice = partyChoicesWithPending(snapshot.parties, rows).find(item =>
  item.name === 'Local Contractor')
assert.equal(localChoice.id, null)
assert.equal(complete(history, localChoice).draft.amount, '-55.00')

// Deleted rows must not seed history, and a fresh snapshot has no pending overlay.
newParty.deleted = true
history = snapshotWithPendingPartyHistory(snapshot, rows)
assert.equal(history.pendingCompletionByPartyName['épicerie du centre'], undefined)
assert.equal(partyChoicesWithPending(snapshot.parties, rows).some(item =>
  item.name === 'Épicerie du Centre'), false)
const afterReload = snapshotWithPendingPartyHistory(snapshot, createResponsiveDrafts(snapshot))
assert.deepEqual(afterReload.completionByPartyId, snapshot.completionByPartyId)
assert.deepEqual(afterReload.pendingCompletionByPartyName, {})

// Unapplied drafts must not affect completion history.
const unapplied = newResponsiveDraft(snapshot, 'new-3', '07/14/2026')
unapplied.partyName = 'Not yet applied'
unapplied.amount = '-999.00'
assert.equal(snapshotWithPendingPartyHistory(snapshot, [unapplied])
  .pendingCompletionByPartyName['not yet applied'], undefined)

// Transfer completion also uses locally applied destination and counterpart details.
const transfer = newResponsiveDraft(snapshot, 'new-transfer', '07/14/2026')
applied(transfer, {
  partyName: 'Café', partySelectionId: '1',
  categoryName: 'Transfer', categorySelectionId: null,
  subcategoryName: 'Savings', transferAccountSelectionId: '2',
  amount: '-70.00',
  paymentMethodName: 'Debit', paymentMethodSelectionId: '1',
  transferPaymentMethodName: 'Incoming', transferPaymentMethodSelectionId: '4',
  note: 'Latest transfer',
}, 6)
const transferHistory = snapshotWithPendingPartyHistory(snapshot, [transfer])
const { draft: nextTransfer } = complete(transferHistory, snapshot.parties[0])
assert.equal(nextTransfer.amount, '-70.00')
assert.equal(nextTransfer.categoryName, 'Transfer')
assert.equal(nextTransfer.subcategoryName, 'Savings')
assert.equal(nextTransfer.transferAccountSelectionId, '2')
assert.equal(nextTransfer.transferPaymentMethodName, 'Incoming')
assert.equal(nextTransfer.transferPaymentMethodSelectionId, '4')
assert.equal(nextTransfer.note, 'Latest transfer')

// With duplicate real payee IDs, the autocomplete should select the ID
// belonging to the latest locally applied transaction, not the older one.
const duplicateSnapshot = {
  ...snapshot,
  parties: [
    ...snapshot.parties,
    { id: '3', name: 'Shop', preferredCompletionPartyId: '2', completionPriority: 2 },
  ],
  completionByPartyId: {
    ...snapshot.completionByPartyId,
    '3': { ...snapshot.completionByPartyId['2'], amount: '-999.00' },
  },
}
const duplicateRow = newResponsiveDraft(duplicateSnapshot, 'new-duplicate', '07/14/2026')
applied(duplicateRow, {
  partyName: 'Shop', partySelectionId: '3',
  amount: '-23.00',
  categoryName: 'Bills', categorySelectionId: '2',
  subcategoryName: 'Electricity', subcategorySelectionId: '1',
  paymentMethodName: 'Debit', paymentMethodSelectionId: '1',
}, 7)
const duplicateChoices = partyChoicesWithPending(duplicateSnapshot.parties, [duplicateRow])
assert.equal(duplicateChoices.find(item => item.id === '2').preferredCompletionPartyId, '3')
assert.equal(duplicateChoices.find(item => item.id === '3').completionPriority, -1)
const duplicateHistory = snapshotWithPendingPartyHistory(duplicateSnapshot, [duplicateRow])
assert.equal(
  complete(duplicateHistory, duplicateChoices.find(item => item.id === '3')).draft.amount,
  '-23.00',
)

console.log('Unsaved party completion history tests passed')
