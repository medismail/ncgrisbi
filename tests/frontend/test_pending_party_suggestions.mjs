import assert from 'node:assert/strict'
import {
  applyEditorDraft,
  buildResponsiveMutationOperations,
  newResponsiveDraft,
  setSelectedItem,
} from '../../src/domain/responsiveEditor.mjs'
import { partyChoicesWithPending } from '../../src/domain/pendingPartySuggestions.mjs'

const snapshot = {
  account: { id: '1', name: 'Main' },
  accounts: [{ id: '1', name: 'Main', closed: false }],
  parties: [{ id: '1', name: 'Cafe' }],
  categories: [],
  paymentMethods: [{ id: '1', name: 'Card', sign: 1, accountId: '1' }],
  paymentMethodsByAccount: {
    '1': [{ id: '1', name: 'Card', sign: 1, accountId: '1' }],
  },
  transactions: [],
}

const pending = newResponsiveDraft(snapshot, 'new-1', '07/12/2026')
assert.equal(partyChoicesWithPending(snapshot.parties, [pending]).length, 1)

// Save draft: still local, not persisted, and therefore no Grisbi ID.
applyEditorDraft(pending, {
  ...pending,
  partyName: 'Épicerie du Centre',
  amount: '-12.00',
  paymentMethodName: 'Card',
  paymentMethodSelectionId: '1',
})
const choices = partyChoicesWithPending(snapshot.parties, [pending])
assert.equal(choices.length, 2)
assert.deepEqual(choices[0], {
  id: null,
  name: 'Épicerie du Centre',
  pending: true,
  secondary: 'Pending save',
  completionPriority: -1,
})
assert.equal(snapshot.parties.length, 1)

// Save draft & add another: picking a pending suggestion must keep a name,
// not manufacture a persisted ID or attach stale completion history.
const another = newResponsiveDraft(snapshot, 'new-2', '07/13/2026')
setSelectedItem(another, 'party', choices[0])
another.amount = '-8.00'
another.paymentMethodName = 'Card'
another.paymentMethodSelectionId = '1'
assert.equal(another.partyName, 'Épicerie du Centre')
assert.equal(another.partySelectionId, null)
const operations = buildResponsiveMutationOperations([pending, another], snapshot)
assert.deepEqual(operations.map(item => item.type), ['createTransaction', 'createTransaction'])
assert.deepEqual(operations.map(item => item.partyName), ['Épicerie du Centre', 'Épicerie du Centre'])
assert.deepEqual(operations.map(item => item.createMissing), [true, true])
assert.equal(operations.every(item => !('partyId' in item)), true)

// Duplicate pending names (case/spacing) should appear only once.
const repeated = newResponsiveDraft(snapshot, 'new-3', '07/14/2026')
applyEditorDraft(repeated, { ...repeated, partyName: '  épicerie   du centre  ' })
assert.equal(partyChoicesWithPending(snapshot.parties, [pending, repeated]).length, 2)

// Search-only accent folding must not merge Cafe (persisted) with Café (pending).
const accented = newResponsiveDraft(snapshot, 'new-4', '07/14/2026')
applyEditorDraft(accented, { ...accented, partyName: 'Café' })
const withAccent = partyChoicesWithPending(snapshot.parties, [pending, accented])
assert.deepEqual(withAccent.map(item => item.name), ['Café', 'Épicerie du Centre', 'Cafe'])

// Only locally applied, undeleted new rows contribute; discarded names vanish.
pending.deleted = true
assert.deepEqual(
  partyChoicesWithPending(snapshot.parties, [pending, accented]).map(item => item.name),
  ['Café', 'Cafe'],
)

console.log('Pending party autocomplete suggestions tests passed')
