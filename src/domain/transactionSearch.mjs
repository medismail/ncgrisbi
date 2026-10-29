import { normalizeSearchText } from './searchNormalization.mjs'

const SEARCH_FIELDS = [
  'partyName',
  'note',
  'paymentReference',
  'bankReference',
  'voucher',
]

export function matchesTransactionSearch(transaction, query) {
  const pattern = normalizeSearchText(query)
  if (!pattern) return true
  return SEARCH_FIELDS.some(field => normalizeSearchText(transaction?.[field]).includes(pattern))
}
