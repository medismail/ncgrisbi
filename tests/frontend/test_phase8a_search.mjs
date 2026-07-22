import assert from 'node:assert/strict'
import { matchesTransactionSearch } from '../../src/domain/transactionSearch.mjs'

const transaction = {
  partyName: 'Café de la Gare',
  note: 'Monthly subscription',
  paymentReference: 'CARD-2026-0042',
  bankReference: 'BANK-7788',
  voucher: 'INV-19',
}

assert.equal(matchesTransactionSearch(transaction, ''), true)
assert.equal(matchesTransactionSearch(transaction, 'café'), true)
assert.equal(matchesTransactionSearch(transaction, 'subscription'), true)
assert.equal(matchesTransactionSearch(transaction, '2026-0042'), true)
assert.equal(matchesTransactionSearch(transaction, 'bank-7788'), true)
assert.equal(matchesTransactionSearch(transaction, 'inv-19'), true)
assert.equal(matchesTransactionSearch(transaction, 'unknown'), false)

console.log('phase8a transaction search tests passed')
