import { normalizeName } from './transactionEditor.mjs'

const SEARCH_FIELDS = [
  'partyName',
  'note',
  'paymentReference',
  'bankReference',
  'voucher',
]

export function matchesTransactionSearch(transaction, query) {
  const pattern = normalizeName(query)
  if (!pattern) return true
  return SEARCH_FIELDS.some(field => normalizeName(transaction?.[field]).includes(pattern))
}
