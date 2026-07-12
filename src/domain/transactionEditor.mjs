export class EditorValidationError extends Error {
  constructor(message, rowKey = null) {
    super(message)
    this.name = 'EditorValidationError'
    this.rowKey = rowKey
  }
}

export function normalizeName(value) {
  return String(value ?? '')
    .normalize('NFKC')
    .trim()
    .replace(/\s+/gu, ' ')
    .toLowerCase()
}

function optionalText(value) {
  const text = String(value ?? '').trim()
  return text === '' ? null : text
}

function requiredText(value, field, rowKey) {
  const text = String(value ?? '').trim()
  if (text === '') {
    throw new EditorValidationError(`${field} is required.`, rowKey)
  }
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
  if (key === '') {
    return null
  }
  const matches = records.filter(record => normalizeName(record.name) === key)
  if (matches.length > 1) {
    throw new EditorValidationError(
      `${label} “${String(name).trim()}” is ambiguous; select it by its exact ID.`,
      rowKey,
    )
  }
  return matches[0] ?? null
}

function categoryForName(snapshot, name, rowKey) {
  return uniqueByName(snapshot.categories, name, 'Category', rowKey)
}

function subcategoryForName(category, name, rowKey) {
  return uniqueByName(category?.subcategories ?? [], name, 'Subcategory', rowKey)
}

function paymentForName(snapshot, name, rowKey) {
  return uniqueByName(snapshot.paymentMethods, name, 'Payment method', rowKey)
}

function partyForName(snapshot, name, rowKey) {
  return uniqueByName(snapshot.parties, name, 'Party', rowKey)
}

function editableValues(source) {
  return {
    date: source.date ?? '',
    valueDate: source.valueDate ?? '',
    amount: String(source.amount ?? ''),
    partyName: source.partyName ?? '',
    categoryName: source.categoryName ?? '',
    subcategoryName: source.subcategoryName ?? '',
    paymentMethodName: source.paymentMethodName ?? '',
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
    ...values,
    original: {
      ...values,
      partyId: String(transaction.partyId ?? '0'),
      categoryId: String(transaction.categoryId ?? '0'),
      subcategoryId: String(transaction.subcategoryId ?? '0'),
      paymentMethodId: String(transaction.paymentMethodId ?? '0'),
    },
  }
}

export function newTransactionDraft(snapshot, key, date) {
  return {
    key,
    transactionId: null,
    isNew: true,
    deleted: false,
    editing: true,
    protected: false,
    protectionReasons: [],
    date,
    valueDate: '',
    amount: '0.00',
    partyName: '',
    categoryName: '',
    subcategoryName: '',
    paymentMethodName: snapshot.paymentMethods[0]?.name ?? '',
    note: '',
    paymentReference: '',
    marked: 0,
    voucher: '',
    bankReference: '',
    original: null,
  }
}

export function createDrafts(snapshot) {
  return snapshot.transactions.map(draftFromTransaction)
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
    if (current !== original) {
      changes[apiField] = current
    }
  }
  const marked = Number(row.marked)
  if (![0, 1, 2, 3].includes(marked)) {
    throw new EditorValidationError('Marked state must be between 0 and 3.', row.key)
  }
  if (marked !== Number(row.original.marked)) {
    changes.marked = marked
  }
  return changes
}

function applyCreateReference(operation, snapshot, row) {
  const partyName = optionalText(row.partyName)
  if (partyName !== null) {
    const party = partyForName(snapshot, partyName, row.key)
    if (party) {
      operation.partyId = String(party.id)
    } else {
      operation.partyName = partyName
      operation.createMissing = true
    }
  }

  const categoryName = optionalText(row.categoryName)
  const subcategoryName = optionalText(row.subcategoryName)
  if (categoryName === null) {
    if (subcategoryName !== null) {
      throw new EditorValidationError(
        'A subcategory cannot be used without a category.',
        row.key,
      )
    }
  } else {
    const category = categoryForName(snapshot, categoryName, row.key)
    if (category) {
      operation.categoryId = String(category.id)
      if (subcategoryName !== null) {
        const subcategory = subcategoryForName(category, subcategoryName, row.key)
        if (subcategory) {
          operation.subcategoryId = String(subcategory.id)
        } else {
          operation.subcategoryName = subcategoryName
          operation.createMissing = true
        }
      }
    } else {
      operation.categoryName = categoryName
      operation.createMissing = true
      if (subcategoryName !== null) {
        operation.subcategoryName = subcategoryName
      }
    }
  }
}

function createOperation(row, snapshot) {
  const operation = {
    type: 'createTransaction',
    accountId: String(snapshot.account.id),
    date: requiredText(row.date, 'Date', row.key),
    amount: decimalText(row.amount, row.key),
    marked: Number(row.marked),
  }
  if (![0, 1, 2, 3].includes(operation.marked)) {
    throw new EditorValidationError('Marked state must be between 0 and 3.', row.key)
  }

  const optionalMappings = [
    ['valueDate', 'valueDate'],
    ['note', 'note'],
    ['paymentReference', 'paymentReference'],
    ['voucher', 'voucher'],
    ['bankReference', 'bankReference'],
  ]
  for (const [draftField, apiField] of optionalMappings) {
    const value = optionalText(row[draftField])
    if (value !== null) {
      operation[apiField] = value
    }
  }

  const paymentName = optionalText(row.paymentMethodName)
  if (paymentName !== null) {
    const payment = paymentForName(snapshot, paymentName, row.key)
    if (!payment) {
      throw new EditorValidationError(
        `Payment method “${paymentName}” does not exist for this account.`,
        row.key,
      )
    }
    operation.paymentMethodId = String(payment.id)
  }

  applyCreateReference(operation, snapshot, row)
  return operation
}

function updateOperation(row, snapshot) {
  const changes = scalarChanges(row)

  const partyName = optionalText(row.partyName)
  const party = partyName === null ? null : partyForName(snapshot, partyName, row.key)
  if (partyName !== null && !party) {
    throw new EditorValidationError(
      `Party “${partyName}” must be created with a new transaction before it can be used in an update.`,
      row.key,
    )
  }
  const partyId = party ? String(party.id) : '0'
  if (partyId !== row.original.partyId) {
    changes.partyId = partyId
  }

  const categoryName = optionalText(row.categoryName)
  const subcategoryName = optionalText(row.subcategoryName)
  let categoryId = '0'
  let subcategoryId = '0'
  if (categoryName !== null) {
    const category = categoryForName(snapshot, categoryName, row.key)
    if (!category) {
      throw new EditorValidationError(
        `Category “${categoryName}” must exist before updating a transaction.`,
        row.key,
      )
    }
    categoryId = String(category.id)
    if (subcategoryName !== null) {
      const subcategory = subcategoryForName(category, subcategoryName, row.key)
      if (!subcategory) {
        throw new EditorValidationError(
          `Subcategory “${subcategoryName}” does not exist in “${categoryName}”.`,
          row.key,
        )
      }
      subcategoryId = String(subcategory.id)
    }
  } else if (subcategoryName !== null) {
    throw new EditorValidationError(
      'A subcategory cannot be used without a category.',
      row.key,
    )
  }
  if (categoryId !== row.original.categoryId) {
    changes.categoryId = categoryId
  }
  if (subcategoryId !== row.original.subcategoryId) {
    changes.subcategoryId = subcategoryId
  }

  const paymentName = optionalText(row.paymentMethodName)
  const payment = paymentName === null ? null : paymentForName(snapshot, paymentName, row.key)
  if (paymentName !== null && !payment) {
    throw new EditorValidationError(
      `Payment method “${paymentName}” does not exist for this account.`,
      row.key,
    )
  }
  const paymentId = payment ? String(payment.id) : '0'
  if (paymentId !== row.original.paymentMethodId) {
    changes.paymentMethodId = paymentId
  }

  if (Object.keys(changes).length === 0) {
    return null
  }
  return {
    type: 'updateTransaction',
    transactionId: row.transactionId,
    changes,
  }
}

export function buildMutationOperations(rows, snapshot) {
  const operations = []
  for (const row of rows) {
    if (row.deleted) {
      if (row.isNew) {
        continue
      }
      if (row.protected) {
        throw new EditorValidationError(
          'Transfer and split transactions cannot be deleted in the normal transaction editor.',
          row.key,
        )
      }
      operations.push({
        type: 'deleteTransaction',
        transactionId: row.transactionId,
      })
      continue
    }

    if (row.protected) {
      if (!sameEditableValues(row, row.original)) {
        throw new EditorValidationError(
          'Transfer and split transactions are read-only in this phase.',
          row.key,
        )
      }
      continue
    }

    if (row.isNew) {
      operations.push(createOperation(row, snapshot))
    } else {
      const operation = updateOperation(row, snapshot)
      if (operation) {
        operations.push(operation)
      }
    }
  }
  return operations
}

export function sameEditableValues(row, original = row.original) {
  if (!original) {
    return false
  }
  const fields = [
    'date',
    'valueDate',
    'amount',
    'partyName',
    'categoryName',
    'subcategoryName',
    'paymentMethodName',
    'note',
    'paymentReference',
    'marked',
    'voucher',
    'bankReference',
  ]
  return fields.every(field => String(row[field] ?? '') === String(original[field] ?? ''))
}

export function hasPendingChanges(rows) {
  return rows.some(row => row.deleted || row.isNew || !sameEditableValues(row))
}

export function calculateTotals(rows, precision = 2) {
  let total = 0
  let marked = 0
  for (const row of rows) {
    if (row.deleted) {
      continue
    }
    const amount = Number(row.amount)
    if (!Number.isFinite(amount)) {
      continue
    }
    total += amount
    if (Number(row.marked) === 1) {
      marked += amount
    }
  }
  return {
    totalAmount: total.toFixed(precision),
    totalMarkedAmount: marked.toFixed(precision),
  }
}
