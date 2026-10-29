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
assert.equal(matchesTransactionSearch(transaction, 'cafe'), true)
assert.equal(matchesTransactionSearch(transaction, 'CAFÈ'), true)
assert.equal(matchesTransactionSearch(transaction, 'CAFÉ'), true)
assert.equal(matchesTransactionSearch({ partyName: 'Epicerie du Centre' }, 'Épicerie'), true)
assert.equal(matchesTransactionSearch({ partyName: 'À la maison' }, 'a la'), true)
assert.equal(matchesTransactionSearch({ note: 'Électricité et Noël' }, 'electricite'), true)
assert.equal(matchesTransactionSearch({ note: 'Électricité et Noël' }, 'noel'), true)
assert.equal(matchesTransactionSearch({ paymentReference: 'Référence-123' }, 'reference'), true)
assert.equal(matchesTransactionSearch({ categoryName: 'Café' }, 'cafe'), false)
assert.equal(matchesTransactionSearch(transaction, 'subscription'), true)
assert.equal(matchesTransactionSearch(transaction, '2026-0042'), true)
assert.equal(matchesTransactionSearch(transaction, 'bank-7788'), true)
assert.equal(matchesTransactionSearch(transaction, 'inv-19'), true)
assert.equal(matchesTransactionSearch(transaction, 'unknown'), false)

console.log('phase8a transaction search tests passed')
