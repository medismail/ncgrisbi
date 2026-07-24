import assert from 'node:assert/strict'
import { decodeCompactSnapshot } from '../../src/domain/snapshotWire.mjs'
import {
  applyPartyCompletionTrace,
  newResponsiveDraft,
  setSelectedItem,
} from '../../src/domain/responsiveEditor.mjs'

const wire = {
  v: 2,
  a: ['1', 'Current', 0, '1', 'Euro', 'EUR', '€', 2, '0', '0'],
  A: [
    ['1', 'Current', 0, '1', '6', '2', 0],
    ['2', 'Savings', 0, '1', '3', '5', 0],
  ],
  P: [
    ['1', 'Transfer party'],
    ['2', 'Fallback only'],
    ['3', 'Transfer party'],
  ],
  C: [],
  M: [
    ['1', [
      ['1', 'Exact source method', 1, 1, 0, null],
      ['2', 'Deposit', 2, 1, 0, null],
      ['6', 'Default source method', 1, 1, 0, null],
      ['7', 'Exact source method', 1, 1, 0, null],
    ]],
    ['2', [
      ['3', 'Transfer out', 1, 1, 0, null],
      ['4', 'Exact counterpart method', 2, 1, 0, null],
      ['5', 'Default counterpart method', 2, 1, 0, null],
      ['8', 'Exact counterpart method', 2, 1, 0, null],
    ]],
  ],
  T: [[
    '10', '07/15/2026', null, '-40.00', '1', '0', '0', '1',
    'Current-account transfer', null, 0, null, null, '0', '11', null,
    4, '2', '4',
  ]],
  H: [
    ['1', '2', '999.00', '0', '0', '2', 'Wrong account', null, null, null, null],
    ['2', '2', '-12.00', '0', '0', '2', 'Fallback remains available', null, null, null, null],
    ['3', '2', '888.00', '0', '0', '2', 'Duplicate from other account', null, null, null, null],
  ],
  U: [],
  W: [],
}

const snapshot = decodeCompactSnapshot(wire)
const preferred = snapshot.completionByPartyId['1']
assert.equal(preferred.sourceAccountId, '1')
assert.equal(preferred.amount, '-40.00')
assert.equal(preferred.transferAccountId, '2')
assert.equal(preferred.paymentMethodId, '1')
assert.equal(preferred.targetPaymentMethodId, '4')
assert.equal(snapshot.completionByPartyId['2'].sourceAccountId, '2')

const preferredParty = snapshot.parties.find(item => item.id === '1')
const duplicateParty = snapshot.parties.find(item => item.id === '3')
assert.equal(preferredParty.preferredCompletionPartyId, '1')
assert.equal(preferredParty.completionPriority, 0)
assert.equal(duplicateParty.preferredCompletionPartyId, '1')
assert.ok(duplicateParty.completionPriority > preferredParty.completionPriority)
assert.match(preferredParty.secondary, /Latest in Current/u)
assert.match(duplicateParty.secondary, /history from Savings/u)

const draft = newResponsiveDraft(snapshot, 'new-1', '07/16/2026')
assert.equal(draft.paymentMethodName, 'Default source method')
setSelectedItem(draft, 'party', preferredParty)
const trace = applyPartyCompletionTrace(draft, snapshot)

assert.ok(trace)
assert.equal(draft.amount, '-40.00')
assert.equal(draft.partySelectionId, '1')
assert.equal(draft.categoryName, 'Transfer')
assert.equal(draft.subcategoryName, 'Savings')
assert.equal(draft.transferAccountSelectionId, '2')
assert.equal(draft.paymentMethodName, 'Exact source method')
assert.equal(draft.paymentMethodSelectionId, '1')
assert.equal(draft.transferPaymentMethodName, 'Exact counterpart method')
assert.equal(draft.transferPaymentMethodSelectionId, '4')
assert.equal(draft.note, 'Current-account transfer')

console.log('phase8a same-account completion tests passed')
