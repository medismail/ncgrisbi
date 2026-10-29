import { TRANSFER_CATEGORY, normalizeName } from './transactionEditor.mjs'

function pendingRows(rows) {
  return rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => row.locallyApplied && !row.deleted
      && (row.isNew || Number(row.localCompletionOrder) > 0))
    .sort((left, right) =>
      (Number(left.row.localCompletionOrder) || left.index + 1)
      - (Number(right.row.localCompletionOrder) || right.index + 1))
}

function partyIdForRow(snapshot, row) {
  const name = normalizeName(row.partyName)
  if (!name) return null
  const selected = snapshot.parties.find(party =>
    String(party.id) === String(row.partySelectionId) && normalizeName(party.name) === name)
  if (selected) return String(selected.id)
  const matches = snapshot.parties.filter(party => normalizeName(party.name) === name)
  return matches.length === 1 ? String(matches[0].id) : null
}

function selectedId(records, id, name) {
  const normalized = normalizeName(name)
  const record = records.find(item =>
    String(item.id) === String(id) && normalizeName(item.name) === normalized)
  if (record) return String(record.id)
  const matches = records.filter(item => normalizeName(item.name) === normalized)
  return matches.length === 1 ? String(matches[0].id) : '0'
}

function draftCompletion(snapshot, row) {
  const transfer = normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)
  const category = transfer ? null : snapshot.categories.find(item =>
    String(item.id) === String(row.categorySelectionId)
    && normalizeName(item.name) === normalizeName(row.categoryName))
    ?? (transfer ? null : snapshot.categories.filter(item =>
      normalizeName(item.name) === normalizeName(row.categoryName)).length === 1
      ? snapshot.categories.find(item => normalizeName(item.name) === normalizeName(row.categoryName))
      : null)
  const paymentMethods = snapshot.paymentMethodsByAccount?.[String(snapshot.account.id)] ?? []
  const target = transfer ? snapshot.accounts.find(item =>
    String(item.id) === String(row.transferAccountSelectionId)
    && normalizeName(item.name) === normalizeName(row.subcategoryName))
    ?? snapshot.accounts.find(item => normalizeName(item.name) === normalizeName(row.subcategoryName))
    : null
  const targetMethods = snapshot.paymentMethodsByAccount?.[String(target?.id)] ?? []
  return {
    sourceAccountId: String(snapshot.account.id),
    amount: String(row.amount),
    categoryId: category ? String(category.id) : '0',
    categoryName: transfer ? '' : String(row.categoryName ?? ''),
    subcategoryId: category
      ? selectedId(category.subcategories ?? [], row.subcategorySelectionId, row.subcategoryName)
      : '0',
    subcategoryName: transfer ? '' : String(row.subcategoryName ?? ''),
    paymentMethodId: selectedId(paymentMethods, row.paymentMethodSelectionId, row.paymentMethodName),
    paymentMethodName: String(row.paymentMethodName ?? ''),
    note: row.note ?? null,
    paymentReference: row.paymentReference ?? null,
    voucher: row.voucher ?? null,
    bankReference: row.bankReference ?? null,
    transferAccountId: target ? String(target.id) : null,
    targetPaymentMethodId: target
      ? selectedId(targetMethods, row.transferPaymentMethodSelectionId, row.transferPaymentMethodName)
      : null,
    transferPaymentMethodName: String(row.transferPaymentMethodName ?? ''),
  }
}

/**
 * Local draft history overrides the loaded party completion history until Save all.
 * Keep the saved snapshot, real Grisbi IDs and mutation planning untouched.
 */
export function snapshotWithPendingPartyHistory(snapshot, rows) {
  const completionByPartyId = { ...snapshot.completionByPartyId }
  const pendingCompletionByPartyName = {}
  for (const { row } of pendingRows(rows)) {
    const name = normalizeName(row.partyName)
    if (!name) continue
    const hint = draftCompletion(snapshot, row)
    const partyId = partyIdForRow(snapshot, row)
    if (partyId) completionByPartyId[partyId] = { ...hint, partyId }
    else pendingCompletionByPartyName[name] = hint
  }
  return { ...snapshot, completionByPartyId, pendingCompletionByPartyName }
}

/**
 * Expose locally applied new payee names (including existing transactions
 * reassigned to a newly created payee) without fabricating Grisbi IDs.
 */
export function partyChoicesWithPending(savedParties, rows) {
  const knownNames = new Set(savedParties.map(party => normalizeName(party.name)))
  const pending = []
  const applied = pendingRows(rows)
  for (let index = applied.length - 1; index >= 0; index--) {
    const { row } = applied[index]
    const name = String(row.partyName ?? '').trim()
    const key = normalizeName(name)
    if (!key || knownNames.has(key)) continue
    knownNames.add(key)
    pending.push({
      id: null,
      name,
      pending: true,
      secondary: 'Pending save',
      completionPriority: -1,
    })
  }
  return [...pending, ...savedParties]
}
