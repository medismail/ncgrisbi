import assert from 'node:assert/strict'
import {
  buildResponsiveMutationOperations,
  createResponsiveDrafts,
} from '../../src/domain/responsiveEditor.mjs'

const snapshot = {
  account: { id: '1', name: 'Main' },
  accounts: [{ id: '1', name: 'Main', closed: false }],
  parties: [{ id: '1', name: 'Existing Shop' }],
  categories: [{
    id: '1', name: 'Food', kind: 1,
    subcategories: [{ id: '1', name: 'Groceries' }],
  }],
  paymentMethods: [{ id: '1', name: 'Card', sign: 1, accountId: '1' }],
  paymentMethodsByAccount: {
    '1': [{ id: '1', name: 'Card', sign: 1, accountId: '1' }],
  },
  transactions: [{
    id: '1', date: '07/10/2026', amount: '-10.00',
    partyId: '1', partyName: 'Existing Shop',
    categoryId: '1', categoryName: 'Food',
    subcategoryId: '1', subcategoryName: 'Groceries',
    paymentMethodId: '1', paymentMethodName: 'Card',
    marked: 0, protected: false, quickMarkable: true,
    isTransfer: false,
  }],
}

const changesOf = (change) => {
  const row = createResponsiveDrafts(snapshot)[0]
  Object.assign(row, change)
  const operations = buildResponsiveMutationOperations([row], snapshot)
  assert.equal(operations.length, 1)
  assert.equal(operations[0].type, 'updateTransaction')
  assert.equal(operations[0].transactionId, '1')
  return operations[0].changes
}

assert.deepEqual(
  changesOf({
    partyName: 'Local Plumber',
    categoryName: 'Household',
    subcategoryName: 'Repairs',
    partySelectionId: null,
    categorySelectionId: null,
    subcategorySelectionId: null,
  }),
  {
    partyName: 'Local Plumber',
    categoryName: 'Household',
    subcategoryName: 'Repairs',
    createMissing: true,
  },
)

assert.deepEqual(
  changesOf({ subcategoryName: 'Takeaway', subcategorySelectionId: null }),
  { subcategoryName: 'Takeaway', createMissing: true },
)

assert.deepEqual(
  changesOf({ categoryName: 'Bills', categorySelectionId: null, subcategoryName: '', subcategorySelectionId: null }),
  { categoryName: 'Bills', createMissing: true },
)

assert.deepEqual(
  changesOf({ partyName: 'New Supplier', partySelectionId: null }),
  { partyName: 'New Supplier', createMissing: true },
)

assert.deepEqual(
  changesOf({ partyName: '', partySelectionId: null }),
  { partyId: '0' },
)

assert.deepEqual(
  changesOf({ subcategoryName: '', subcategorySelectionId: null }),
  { subcategoryId: '0' },
)

assert.deepEqual(buildResponsiveMutationOperations(createResponsiveDrafts(snapshot), snapshot), [])

console.log('Editing existing transaction with missing references tests passed')
