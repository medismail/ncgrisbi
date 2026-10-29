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

function selectedByName(records, id, name) {
  const normalized = normalizeName(name)
  if (!normalized) return null
  const selected = id == null ? null : records.find(item =>
    String(item.id) === String(id) && normalizeName(item.name) === normalized)
  if (selected) return selected
  const matches = records.filter(item => normalizeName(item.name) === normalized)
  return matches.length === 1 ? matches[0] : null
}

function partyIdForRow(snapshot, row) {
  const party = selectedByName(snapshot.parties, row.partySelectionId, row.partyName)
  return party ? String(party.id) : null
}

function selectedId(records, id, name) {
  const selected = selectedByName(records, id, name)
  return selected ? String(selected.id) : '0'
}

function draftCompletion(snapshot, row) {
  const transfer = normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)
  const category = transfer ? null : selectedByName(
    snapshot.categories, row.categorySelectionId, row.categoryName,
  )
  const paymentMethods = snapshot.paymentMethodsByAccount?.[String(snapshot.account.id)] ?? []
  const target = transfer ? selectedByName(
    snapshot.accounts.filter(account =>
      !account.closed && String(account.id) !== String(snapshot.account.id)),
    row.transferAccountSelectionId, row.subcategoryName,
  ) : null
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
  // Duplicate payees can have different real Grisbi IDs. Prefer the payee
  // used in the latest locally applied draft instead of stale saved history.
  const preferredIds = new Map()
  for (const { row } of applied) {
    const partyId = partyIdForRow({ parties: savedParties }, row)
    if (partyId) preferredIds.set(normalizeName(row.partyName), partyId)
  }
  const savedChoices = savedParties.map(party => {
    const preferred = preferredIds.get(normalizeName(party.name))
    if (!preferred) return party
    return {
      ...party,
      preferredCompletionPartyId: preferred,
      completionPriority: String(party.id) === preferred ? -1 : party.completionPriority,
    }
  })
  return [...pending, ...savedChoices]
}
