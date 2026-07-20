import {
  TRANSFER_CATEGORY,
  applyPartyCompletion,
  buildMutationOperations,
  calculateTotals,
  createDrafts,
  newTransactionDraft,
  normalizeName,
  onAmountDirectionChanged,
  paymentMethodsForAmount,
  sameEditableValues,
} from './transactionEditor.mjs'

export {
  TRANSFER_CATEGORY,
  calculateTotals,
  normalizeName,
  onAmountDirectionChanged,
  paymentMethodsForAmount,
}

const SELECTION_FIELDS = [
  'partySelectionId',
  'categorySelectionId',
  'subcategorySelectionId',
  'paymentMethodSelectionId',
  'transferAccountSelectionId',
  'transferPaymentMethodSelectionId',
]

const COMPLETION_FIELDS = [
  'amount',
  'categoryName',
  'subcategoryName',
  'paymentMethodName',
  'transferPaymentMethodName',
  'note',
  'paymentReference',
  'voucher',
  'bankReference',
]

function clone(value) {
  if (typeof structuredClone === 'function') return structuredClone(value)
  return JSON.parse(JSON.stringify(value))
}

function nonZeroId(value) {
  const text = value == null ? '' : String(value)
  return text && text !== '0' ? text : null
}

function selectionState(row) {
  return {
    partySelectionId: nonZeroId(row.original?.partyId),
    categorySelectionId: row.original?.isTransfer ? null : nonZeroId(row.original?.categoryId),
    subcategorySelectionId: row.original?.isTransfer ? null : nonZeroId(row.original?.subcategoryId),
    paymentMethodSelectionId: nonZeroId(row.original?.paymentMethodId),
    transferAccountSelectionId: row.original?.isTransfer
      ? nonZeroId(row.original?.transferAccountId)
      : null,
    transferPaymentMethodSelectionId: row.original?.isTransfer
      ? nonZeroId(row.original?.transferPaymentMethodId)
      : null,
  }
}

function decorate(row) {
  const selections = selectionState(row)
  return {
    ...row,
    ...selections,
    originalSelections: clone(selections),
    locallyApplied: !row.isNew,
  }
}

export function createResponsiveDrafts(snapshot) {
  return createDrafts(snapshot).map(decorate)
}

export function newResponsiveDraft(snapshot, key, date) {
  return {
    ...decorate(newTransactionDraft(snapshot, key, date)),
    editing: false,
    locallyApplied: false,
  }
}

export function cloneEditorDraft(row) {
  return clone({ ...row, editing: true })
}

export function applyEditorDraft(target, draft) {
  const preservedOriginal = target.original
  const preservedOriginalSelections = target.originalSelections
  Object.assign(target, clone(draft), {
    original: preservedOriginal,
    originalSelections: preservedOriginalSelections,
    editing: false,
    locallyApplied: true,
  })
}

function sameSelections(row) {
  const original = row.originalSelections ?? {}
  return SELECTION_FIELDS.every(field => String(row[field] ?? '') === String(original[field] ?? ''))
}

export function sameResponsiveValues(row) {
  if (row.isNew) return false
  return sameEditableValues(row) && sameSelections(row)
}

export function hasResponsivePendingChanges(rows) {
  return rows.some(row => row.deleted || row.isNew || !sameResponsiveValues(row))
}

export function pendingChangeSummary(rows) {
  const result = { total: 0, created: 0, edited: 0, marked: 0, deleted: 0 }
  for (const row of rows) {
    if (row.deleted) {
      if (!row.isNew) {
        result.deleted += 1
        result.total += 1
      }
      continue
    }
    if (row.isNew) {
      result.created += 1
      result.total += 1
      continue
    }
    const markedChanged = Number(row.marked) !== Number(row.original?.marked)
    const otherChanged = !sameEditableValues({ ...row, marked: row.original?.marked }) || !sameSelections(row)
    if (otherChanged) {
      result.edited += 1
      result.total += 1
    } else if (markedChanged) {
      result.marked += 1
      result.total += 1
    }
  }
  return result
}

function selectedRecord(records, selectedId) {
  if (!selectedId) return null
  return records.find(item => String(item.id) === String(selectedId)) ?? null
}

function retainSelectedName(records, selectedId, typedName) {
  const selected = selectedRecord(records, selectedId)
  if (!selected) return records
  const key = normalizeName(typedName || selected.name)
  return records.filter(item => String(item.id) === String(selected.id) || normalizeName(item.name) !== key)
}

function snapshotForRow(snapshot, row) {
  const result = {
    ...snapshot,
    accounts: retainSelectedName(
      snapshot.accounts,
      row.transferAccountSelectionId,
      row.subcategoryName,
    ),
    parties: retainSelectedName(snapshot.parties, row.partySelectionId, row.partyName),
  }

  let categories = retainSelectedName(
    snapshot.categories,
    row.categorySelectionId,
    row.categoryName,
  )
  categories = categories.map(category => {
    if (String(category.id) !== String(row.categorySelectionId ?? '')) return category
    return {
      ...category,
      subcategories: retainSelectedName(
        category.subcategories ?? [],
        row.subcategorySelectionId,
        row.subcategoryName,
      ),
    }
  })
  result.categories = categories

  const groups = {}
  for (const [accountId, methods] of Object.entries(snapshot.paymentMethodsByAccount ?? {})) {
    let selectedId = null
    let typedName = ''
    if (String(accountId) === String(snapshot.account.id)) {
      selectedId = row.paymentMethodSelectionId
      typedName = row.paymentMethodName
    } else if (String(accountId) === String(row.transferAccountSelectionId ?? '')) {
      selectedId = row.transferPaymentMethodSelectionId
      typedName = row.transferPaymentMethodName
    }
    groups[accountId] = retainSelectedName(methods, selectedId, typedName)
  }
  result.paymentMethodsByAccount = groups
  result.paymentMethods = groups[String(snapshot.account.id)] ?? []
  return result
}

export function buildResponsiveMutationOperations(rows, snapshot) {
  const operations = []
  const marks = []
  for (const row of rows) {
    const rowOperations = buildMutationOperations([row], snapshotForRow(snapshot, row))
    for (const operation of rowOperations) {
      if (operation.type === 'setTransactionMarks') marks.push(...operation.marks)
      else operations.push(operation)
    }
  }
  if (marks.length) operations.push({ type: 'setTransactionMarks', marks })
  return operations
}

export function setSelectedItem(row, kind, item) {
  const id = item?.id == null ? null : String(item.id)
  const name = item?.name ?? ''
  if (kind === 'party') {
    row.partyName = name
    row.partySelectionId = id
  } else if (kind === 'category') {
    if (item?.isTransfer) {
      row.categoryName = TRANSFER_CATEGORY
      row.categorySelectionId = null
    } else {
      row.categoryName = name
      row.categorySelectionId = id
    }
    row.subcategoryName = ''
    row.subcategorySelectionId = null
    row.transferAccountSelectionId = null
    row.transferPaymentMethodName = ''
    row.transferPaymentMethodSelectionId = null
  } else if (kind === 'subcategory') {
    row.subcategoryName = name
    row.subcategorySelectionId = id
  } else if (kind === 'payment') {
    row.paymentMethodName = name
    row.paymentMethodSelectionId = id
  } else if (kind === 'transferAccount') {
    row.subcategoryName = name
    row.transferAccountSelectionId = id
    row.subcategorySelectionId = null
    row.transferPaymentMethodName = ''
    row.transferPaymentMethodSelectionId = null
  } else if (kind === 'transferPayment') {
    row.transferPaymentMethodName = name
    row.transferPaymentMethodSelectionId = id
  }
}

export function updateSelectionText(row, kind, value, items = []) {
  const text = String(value ?? '')
  const mapping = {
    party: ['partyName', 'partySelectionId'],
    category: ['categoryName', 'categorySelectionId'],
    subcategory: ['subcategoryName', 'subcategorySelectionId'],
    payment: ['paymentMethodName', 'paymentMethodSelectionId'],
    transferAccount: ['subcategoryName', 'transferAccountSelectionId'],
    transferPayment: ['transferPaymentMethodName', 'transferPaymentMethodSelectionId'],
  }
  const pair = mapping[kind]
  if (!pair) return
  row[pair[0]] = text
  const selected = selectedRecord(items, row[pair[1]])
  if (!selected || normalizeName(selected.name) !== normalizeName(text)) row[pair[1]] = null
  if (kind === 'category' && normalizeName(text) === normalizeName(TRANSFER_CATEGORY)) {
    row.categorySelectionId = null
  }
}

function uniqueByName(records, name) {
  const key = normalizeName(name)
  if (!key) return null
  const matches = records.filter(item => normalizeName(item.name) === key)
  return matches.length === 1 ? matches[0] : null
}

export function syncSelectionIds(row, snapshot) {
  row.partySelectionId = uniqueByName(snapshot.parties, row.partyName)?.id ?? null
  if (normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)) {
    row.categorySelectionId = null
    row.subcategorySelectionId = null
    row.transferAccountSelectionId = uniqueByName(
      snapshot.accounts.filter(item => !item.closed && String(item.id) !== String(snapshot.account.id)),
      row.subcategoryName,
    )?.id ?? null
    const targetMethods = snapshot.paymentMethodsByAccount?.[String(row.transferAccountSelectionId)] ?? []
    row.transferPaymentMethodSelectionId = uniqueByName(
      targetMethods,
      row.transferPaymentMethodName,
    )?.id ?? null
  } else {
    const category = uniqueByName(snapshot.categories, row.categoryName)
    row.categorySelectionId = category?.id ?? null
    row.subcategorySelectionId = uniqueByName(category?.subcategories ?? [], row.subcategoryName)?.id ?? null
    row.transferAccountSelectionId = null
    row.transferPaymentMethodSelectionId = null
  }
  row.paymentMethodSelectionId = uniqueByName(
    snapshot.paymentMethodsByAccount?.[String(snapshot.account.id)] ?? [],
    row.paymentMethodName,
  )?.id ?? null
}

export function applyPartyCompletionTrace(row, snapshot) {
  const before = Object.fromEntries(COMPLETION_FIELDS.map(field => [field, row[field]]))
  const changed = applyPartyCompletion(row, snapshotForRow(snapshot, row))
  if (!changed) return null

  const hint = row.partySelectionId == null
    ? null
    : snapshot.completionByPartyId?.[String(row.partySelectionId)]
  if (hint) {
    if (normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)) {
      row.categorySelectionId = null
      row.subcategorySelectionId = null
      row.transferAccountSelectionId = nonZeroId(hint.transferAccountId)
    } else {
      row.categorySelectionId = nonZeroId(hint.categoryId)
      row.subcategorySelectionId = nonZeroId(hint.subcategoryId)
      row.transferAccountSelectionId = null
    }
    row.paymentMethodSelectionId = nonZeroId(hint.paymentMethodId)
  }
  syncSelectionIds(row, snapshotForRow(snapshot, row))
  const fields = COMPLETION_FIELDS.filter(field => String(before[field] ?? '') !== String(row[field] ?? ''))
  return { before, fields }
}

export function undoPartyCompletion(row, trace, snapshot) {
  if (!trace) return
  Object.assign(row, trace.before)
  syncSelectionIds(row, snapshot)
}

export function editorDraftChanged(draft, baseline) {
  if (!draft || !baseline) return false
  const ignored = new Set(['editing', 'locallyApplied'])
  const keys = new Set([...Object.keys(draft), ...Object.keys(baseline)])
  for (const key of keys) {
    if (ignored.has(key) || key === 'original' || key === 'originalSelections') continue
    if (JSON.stringify(draft[key] ?? null) !== JSON.stringify(baseline[key] ?? null)) return true
  }
  return false
}

export function preferredDisplayMode(preferences) {
  return Number(preferences?.linesPerTransaction ?? 1) > 1
    || preferences?.twoLinesShowed
    || preferences?.threeLinesShowed
    ? 'detailed'
    : 'compact'
}
