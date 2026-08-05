export const TRANSFER_CATEGORY = 'Transfer'

export class EditorValidationError extends Error {
  constructor(message, rowKey = null) {
    super(message)
    this.name = 'EditorValidationError'
    this.rowKey = rowKey
  }
}

export function normalizeName(value) {
  return String(value ?? '').normalize('NFKC').trim().replace(/\s+/gu, ' ').toLocaleLowerCase()
}

function optionalText(value) {
  const text = String(value ?? '').trim()
  return text === '' ? null : text
}

function requiredText(value, field, rowKey) {
  const text = String(value ?? '').trim()
  if (!text) throw new EditorValidationError(`${field} is required.`, rowKey)
  return text
}

function decimalText(value, rowKey) {
  const text = requiredText(value, 'Amount', rowKey)
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/u.test(text)) {
    throw new EditorValidationError('Amount must be a decimal number.', rowKey)
  }
  return text
}

function uniqueByName(records, name, label, rowKey) {
  const key = normalizeName(name)
  if (!key) return null
  const matches = records.filter(record => normalizeName(record.name) === key)
  if (matches.length > 1) {
    throw new EditorValidationError(`${label} “${String(name).trim()}” is ambiguous.`, rowKey)
  }
  return matches[0] ?? null
}

function accountForName(snapshot, name, rowKey) {
  return uniqueByName(
    snapshot.accounts.filter(account => !account.closed && String(account.id) !== String(snapshot.account.id)),
    name,
    'Destination account',
    rowKey,
  )
}

function partyForName(snapshot, name, rowKey) {
  return uniqueByName(snapshot.parties, name, 'Party', rowKey)
}

function categoryForName(snapshot, name, rowKey) {
  return uniqueByName(snapshot.categories, name, 'Category', rowKey)
}

function subcategoryForName(category, name, rowKey) {
  return uniqueByName(category?.subcategories ?? [], name, 'Subcategory', rowKey)
}

function paymentForName(methods, name, rowKey) {
  return uniqueByName(methods, name, 'Payment method', rowKey)
}

export function paymentMethodsForAmount(snapshot, accountId, amount) {
  const methods = snapshot.paymentMethodsByAccount?.[String(accountId)] ?? []
  const number = Number(amount)
  if (!Number.isFinite(number) || number === 0) return methods
  const expected = number < 0 ? 1 : 2
  return methods.filter(method => Number(method.sign) === 0 || Number(method.sign) === expected)
}

function accountDefaultPayment(snapshot, accountId, amount) {
  const account = snapshot.accounts.find(item => String(item.id) === String(accountId))
  const number = Number(amount)
  const preferredId = number < 0
    ? account?.defaultDebitMethodId
    : number > 0
      ? account?.defaultCreditMethodId
      : null
  const methods = paymentMethodsForAmount(snapshot, accountId, amount)
  return methods.find(item => String(item.id) === String(preferredId)) ?? methods[0] ?? null
}

function editableValues(source) {
  return {
    date: source.date ?? '',
    valueDate: source.valueDate ?? '',
    amount: String(source.amount ?? ''),
    partyName: source.partyName ?? '',
    categoryName: source.isTransfer ? TRANSFER_CATEGORY : source.categoryName ?? '',
    subcategoryName: source.isTransfer ? source.transferAccountName ?? '' : source.subcategoryName ?? '',
    paymentMethodName: source.paymentMethodName ?? '',
    transferPaymentMethodName: source.transferPaymentMethodName ?? '',
    note: source.note ?? '',
    paymentReference: source.paymentReference ?? '',
    marked: Number(source.marked ?? 0),
    voucher: source.voucher ?? '',
    bankReference: source.bankReference ?? '',
  }
}

export function draftFromTransaction(transaction) {
  const values = editableValues(transaction)
  return {
    key: `transaction-${transaction.id}`,
    transactionId: String(transaction.id),
    isNew: false,
    deleted: false,
    editing: false,
    protected: Boolean(transaction.protected),
    protectionReasons: [...(transaction.protectionReasons ?? [])],
    quickMarkable: transaction.quickMarkable !== false,
    isTransfer: Boolean(transaction.isTransfer),
    ...values,
    original: {
      ...values,
      isTransfer: Boolean(transaction.isTransfer),
      partyId: String(transaction.partyId ?? '0'),
      categoryId: String(transaction.categoryId ?? '0'),
      subcategoryId: String(transaction.subcategoryId ?? '0'),
      paymentMethodId: String(transaction.paymentMethodId ?? '0'),
      transferAccountId: transaction.transferAccountId == null ? null : String(transaction.transferAccountId),
      transferPaymentMethodId: String(transaction.transferPaymentMethodId ?? '0'),
    },
  }
}

export function newTransactionDraft(snapshot, key, date) {
  const defaultPayment = accountDefaultPayment(snapshot, snapshot.account.id, '-1')
  return {
    key,
    transactionId: null,
    isNew: true,
    deleted: false,
    editing: true,
    protected: false,
    protectionReasons: [],
    quickMarkable: true,
    isTransfer: false,
    date,
    valueDate: '',
    amount: '0.00',
    partyName: '',
    categoryName: '',
    subcategoryName: '',
    paymentMethodName: defaultPayment?.name ?? '',
    transferPaymentMethodName: '',
    note: '',
    paymentReference: '',
    marked: 0,
    voucher: '',
    bankReference: '',
    original: null,
  }
}

export function createDrafts(snapshot) {
  return snapshot.transactions.map(item => draftFromTransaction(item))
}

const COMMON_FIELDS = [
  'date',
  'valueDate',
  'amount',
  'partyName',
  'paymentMethodName',
  'note',
  'paymentReference',
  'voucher',
  'bankReference',
]

function sameFields(row, original, fields) {
  return fields.every(field => String(row[field] ?? '') === String(original?.[field] ?? ''))
}

function sameNonMarkedValues(row, original = row.original) {
  if (!original) return false
  return sameFields(row, original, [
    ...COMMON_FIELDS,
    'categoryName',
    'subcategoryName',
    'transferPaymentMethodName',
  ])
}

function scalarChanges(row) {
  const changes = {}
  const mappings = [
    ['date', 'date', value => requiredText(value, 'Date', row.key)],
    ['valueDate', 'valueDate', optionalText],
    ['amount', 'amount', value => decimalText(value, row.key)],
    ['note', 'note', optionalText],
    ['paymentReference', 'paymentReference', optionalText],
    ['voucher', 'voucher', optionalText],
    ['bankReference', 'bankReference', optionalText],
  ]
  for (const [draftField, apiField, convert] of mappings) {
    const current = convert(row[draftField])
    const original = convert(row.original[draftField])
    if (current !== original) changes[apiField] = current
  }
  return changes
}

function validateMarked(value, rowKey, quick = false) {
  const marked = Number(value)
  const allowed = quick ? [0, 1] : [0, 1, 2, 3]
  if (!allowed.includes(marked)) {
    throw new EditorValidationError(
      quick
        ? 'Only unchecked and checked transactions can be changed directly.'
        : 'Marked state must be between 0 and 3.',
      rowKey,
    )
  }
  return marked
}

function partyReference(operation, snapshot, row, allowCreate) {
  const name = optionalText(row.partyName)
  if (name === null) {
    operation.partyId = '0'
    return
  }
  const party = partyForName(snapshot, name, row.key)
  if (party) operation.partyId = String(party.id)
  else if (allowCreate) {
    operation.partyName = name
    operation.createMissing = true
  } else {
    throw new EditorValidationError(`Party “${name}” does not exist.`, row.key)
  }
}

function normalCategoryReference(operation, snapshot, row, allowCreate) {
  const categoryName = optionalText(row.categoryName)
  const subcategoryName = optionalText(row.subcategoryName)
  if (categoryName === null) {
    if (subcategoryName !== null) {
      throw new EditorValidationError('A subcategory cannot be used without a category.', row.key)
    }
    operation.categoryId = '0'
    operation.subcategoryId = '0'
    return
  }
  const category = categoryForName(snapshot, categoryName, row.key)
  if (!category) {
    if (!allowCreate) {
      throw new EditorValidationError(`Category “${categoryName}” does not exist.`, row.key)
    }
    operation.categoryName = categoryName
    operation.createMissing = true
    if (subcategoryName !== null) operation.subcategoryName = subcategoryName
    return
  }
  operation.categoryId = String(category.id)
  if (subcategoryName === null) {
    operation.subcategoryId = '0'
    return
  }
  const subcategory = subcategoryForName(category, subcategoryName, row.key)
  if (subcategory) operation.subcategoryId = String(subcategory.id)
  else if (allowCreate) {
    operation.subcategoryName = subcategoryName
    operation.createMissing = true
  } else {
    throw new EditorValidationError(
      `Subcategory “${subcategoryName}” does not exist in “${categoryName}”.`,
      row.key,
    )
  }
}

function paymentId(snapshot, accountId, name, amount, rowKey) {
  const text = optionalText(name)
  if (text === null) return '0'
  const method = paymentForName(
    paymentMethodsForAmount(snapshot, accountId, amount),
    text,
    rowKey,
  )
  if (!method) {
    throw new EditorValidationError(
      `Payment method “${text}” is not valid for this account and amount direction.`,
      rowKey,
    )
  }
  return String(method.id)
}

function commonCreate(row, snapshot) {
  const operation = {
    accountId: String(snapshot.account.id),
    date: requiredText(row.date, 'Date', row.key),
    amount: decimalText(row.amount, row.key),
    marked: validateMarked(row.marked, row.key),
  }
  for (const [field, apiField] of [
    ['valueDate', 'valueDate'],
    ['note', 'note'],
    ['paymentReference', 'paymentReference'],
    ['voucher', 'voucher'],
    ['bankReference', 'bankReference'],
  ]) {
    const value = optionalText(row[field])
    if (value !== null) operation[apiField] = value
  }
  partyReference(operation, snapshot, row, true)
  operation.paymentMethodId = paymentId(
    snapshot,
    snapshot.account.id,
    row.paymentMethodName,
    row.amount,
    row.key,
  )
  return operation
}

function createOperation(row, snapshot) {
  const transfer = normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)
  const operation = {
    type: transfer ? 'createTransfer' : 'createTransaction',
    ...commonCreate(row, snapshot),
  }
  if (transfer) {
    const target = accountForName(snapshot, row.subcategoryName, row.key)
    if (!target) {
      throw new EditorValidationError('Select a destination account for the transfer.', row.key)
    }
    operation.targetAccountId = String(target.id)
    operation.targetPaymentMethodId = paymentId(
      snapshot,
      target.id,
      row.transferPaymentMethodName,
      String(-Number(row.amount)),
      row.key,
    )
  } else {
    normalCategoryReference(operation, snapshot, row, true)
  }
  return operation
}

function normalUpdateOperation(row, snapshot) {
  const changes = scalarChanges(row)
  const partyName = optionalText(row.partyName)
  const party = partyName === null ? null : partyForName(snapshot, partyName, row.key)
  if (partyName !== null && !party) {
    throw new EditorValidationError(`Party “${partyName}” does not exist.`, row.key)
  }
  const partyId = party ? String(party.id) : '0'
  if (partyId !== row.original.partyId) changes.partyId = partyId

  const references = {}
  normalCategoryReference(references, snapshot, row, false)
  const categoryId = String(references.categoryId ?? row.original.categoryId)
  const subcategoryId = String(references.subcategoryId ?? '0')
  if (categoryId !== row.original.categoryId) changes.categoryId = categoryId
  if (subcategoryId !== row.original.subcategoryId) changes.subcategoryId = subcategoryId

  const paymentMethodId = paymentId(
    snapshot,
    snapshot.account.id,
    row.paymentMethodName,
    row.amount,
    row.key,
  )
  if (paymentMethodId !== row.original.paymentMethodId) {
    changes.paymentMethodId = paymentMethodId
  }
  if (!Object.keys(changes).length) return null
  return {
    type: 'updateTransaction',
    transactionId: row.transactionId,
    changes,
  }
}

function transferUpdateOperation(row, snapshot) {
  const changes = scalarChanges(row)
  const partyName = optionalText(row.partyName)
  const party = partyName === null ? null : partyForName(snapshot, partyName, row.key)
  if (partyName !== null && !party) {
    throw new EditorValidationError(`Party “${partyName}” does not exist.`, row.key)
  }
  const partyId = party ? String(party.id) : '0'
  if (partyId !== row.original.partyId) changes.partyId = partyId

  const sourcePayment = paymentId(
    snapshot,
    snapshot.account.id,
    row.paymentMethodName,
    row.amount,
    row.key,
  )
  if (sourcePayment !== row.original.paymentMethodId) changes.paymentMethodId = sourcePayment

  const target = accountForName(snapshot, row.subcategoryName, row.key)
  if (!target) throw new EditorValidationError('Select a destination account for the transfer.', row.key)
  if (String(target.id) !== String(row.original.transferAccountId)) {
    changes.targetAccountId = String(target.id)
  }
  const targetPayment = paymentId(
    snapshot,
    target.id,
    row.transferPaymentMethodName,
    String(-Number(row.amount)),
    row.key,
  )
  if (targetPayment !== row.original.transferPaymentMethodId || changes.targetAccountId) {
    changes.targetPaymentMethodId = targetPayment
  }
  if (!Object.keys(changes).length) return null
  return {
    type: 'updateTransfer',
    transactionId: row.transactionId,
    changes,
  }
}

function normalToTransferOperation(row, snapshot) {
  if (!sameFields(row, row.original, COMMON_FIELDS)) {
    throw new EditorValidationError(
      'Save other field changes before converting this transaction to a transfer.',
      row.key,
    )
  }
  const target = accountForName(snapshot, row.subcategoryName, row.key)
  if (!target) throw new EditorValidationError('Select a destination account for the transfer.', row.key)
  return {
    type: 'convertTransactionToTransfer',
    transactionId: row.transactionId,
    targetAccountId: String(target.id),
    paymentMethodId: paymentId(
      snapshot,
      snapshot.account.id,
      row.paymentMethodName,
      row.amount,
      row.key,
    ),
    targetPaymentMethodId: paymentId(
      snapshot,
      target.id,
      row.transferPaymentMethodName,
      String(-Number(row.amount)),
      row.key,
    ),
  }
}

function transferToNormalOperation(row, snapshot) {
  if (!sameFields(row, row.original, COMMON_FIELDS)) {
    throw new EditorValidationError(
      'Save other field changes before converting this transfer to a normal transaction.',
      row.key,
    )
  }
  const references = {}
  normalCategoryReference(references, snapshot, row, false)
  return {
    type: 'convertTransferToTransaction',
    transactionId: row.transactionId,
    categoryId: String(references.categoryId ?? '0'),
    subcategoryId: String(references.subcategoryId ?? '0'),
  }
}

export function buildMutationOperations(rows, snapshot) {
  const operations = []
  const marks = []

  for (const row of rows) {
    if (row.deleted) {
      if (row.isNew) continue
      if (row.protected) {
        throw new EditorValidationError('This protected transaction cannot be deleted here.', row.key)
      }
      operations.push({
        type: row.isTransfer ? 'deleteTransfer' : 'deleteTransaction',
        transactionId: row.transactionId,
      })
      continue
    }

    if (!row.isNew && Number(row.marked) !== Number(row.original.marked)) {
      if (!row.quickMarkable) {
        throw new EditorValidationError(
          'Telepointed or reconciled transactions cannot be changed with the quick checkbox.',
          row.key,
        )
      }
      marks.push([row.transactionId, validateMarked(row.marked, row.key, true)])
    }

    if (row.protected) {
      if (!sameNonMarkedValues(row, row.original)) {
        throw new EditorValidationError(
          'This transaction is read-only because its Grisbi structure is not safely editable.',
          row.key,
        )
      }
      continue
    }

    if (row.isNew) {
      operations.push(createOperation(row, snapshot))
      continue
    }

    const currentlyTransfer = normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)
    let operation = null
    if (!row.original.isTransfer && currentlyTransfer) {
      operation = normalToTransferOperation(row, snapshot)
    } else if (row.original.isTransfer && !currentlyTransfer) {
      operation = transferToNormalOperation(row, snapshot)
    } else if (row.original.isTransfer) {
      operation = transferUpdateOperation(row, snapshot)
    } else {
      operation = normalUpdateOperation(row, snapshot)
    }
    if (operation) operations.push(operation)
  }

  if (marks.length) {
    operations.push({ type: 'setTransactionMarks', marks })
  }
  return operations
}

export function allowReconciledMutations(operations) {
  return operations.map(operation => {
    if ([
      'updateTransfer',
      'deleteTransfer',
      'convertTransactionToTransfer',
      'convertTransferToTransaction',
    ].includes(operation.type)) {
      return { ...operation, allowReconciled: true }
    }
    return operation
  })
}

export function applyPartyCompletion(row, snapshot) {
  const party = partyForName(snapshot, row.partyName, row.key)
  if (!party) return false
  const hint = snapshot.completionByPartyId?.[String(party.id)]
  if (!hint) return false

  let changed = false
  const empty = field => optionalText(row[field]) === null
  if (empty('amount') || Number(row.amount) === 0) {
    row.amount = hint.amount
    changed = true
  }
  if (empty('categoryName')) {
    if (hint.transferAccountId) {
      const target = snapshot.accounts.find(item => String(item.id) === String(hint.transferAccountId))
      if (target) {
        row.categoryName = TRANSFER_CATEGORY
        row.subcategoryName = target.name
        changed = true
      }
    } else {
      const category = snapshot.categories.find(item => String(item.id) === String(hint.categoryId))
      if (category) {
        row.categoryName = category.name
        const subcategory = category.subcategories.find(item => String(item.id) === String(hint.subcategoryId))
        if (subcategory && empty('subcategoryName')) row.subcategoryName = subcategory.name
        changed = true
      }
    }
  }
  if (empty('paymentMethodName') && hint.paymentMethodId !== '0') {
    const method = snapshot.paymentMethods.find(item => String(item.id) === String(hint.paymentMethodId))
    if (method) {
      row.paymentMethodName = method.name
      changed = true
    }
  }
  for (const [field, hintField] of [
    ['note', 'note'],
    ['paymentReference', 'paymentReference'],
    ['voucher', 'voucher'],
    ['bankReference', 'bankReference'],
  ]) {
    if (empty(field) && hint[hintField]) {
      row[field] = hint[hintField]
      changed = true
    }
  }
  if (normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY) && empty('transferPaymentMethodName')) {
    const target = accountForName(snapshot, row.subcategoryName, row.key)
    const method = target ? accountDefaultPayment(snapshot, target.id, String(-Number(row.amount))) : null
    if (method) {
      row.transferPaymentMethodName = method.name
      changed = true
    }
  }
  return changed
}

export function onAmountDirectionChanged(row, snapshot) {
  const current = paymentForName(snapshot.paymentMethods, row.paymentMethodName, row.key)
  const allowed = paymentMethodsForAmount(snapshot, snapshot.account.id, row.amount)
  if (!current || !allowed.some(item => item.id === current.id)) {
    row.paymentMethodName = accountDefaultPayment(snapshot, snapshot.account.id, row.amount)?.name ?? ''
  }
  if (normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)) {
    const target = accountForName(snapshot, row.subcategoryName, row.key)
    if (target) {
      row.transferPaymentMethodName = accountDefaultPayment(
        snapshot,
        target.id,
        String(-Number(row.amount)),
      )?.name ?? ''
    }
  }
}

export function sameEditableValues(row, original = row.original) {
  if (!original) return false
  return sameNonMarkedValues(row, original)
    && Number(row.marked) === Number(original.marked)
}

export function hasPendingChanges(rows) {
  return rows.some(row => row.deleted || row.isNew || !sameEditableValues(row))
}

export function calculateTotals(rows, precision = 2, initialBalance = '0') {
  let total = Number(initialBalance)
  let marked = 0
  for (const row of rows) {
    if (row.deleted) continue
    const amount = Number(row.amount)
    if (!Number.isFinite(amount)) continue
    total += amount
    if (Number(row.marked) === 1) marked += amount
  }
  return {
    totalAmount: total.toFixed(precision),
    totalMarkedAmount: marked.toFixed(precision),
  }
}
