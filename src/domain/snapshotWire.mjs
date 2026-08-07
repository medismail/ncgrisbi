import { sortTransactionsRecentFirst } from './transactionOrdering.mjs'

const TX = {
  id: 0,
  date: 1,
  valueDate: 2,
  amount: 3,
  partyId: 4,
  categoryId: 5,
  subcategoryId: 6,
  paymentMethodId: 7,
  note: 8,
  paymentReference: 9,
  marked: 10,
  voucher: 11,
  bankReference: 12,
  breakdown: 13,
  transferId: 14,
  motherId: 15,
  flags: 16,
  targetAccountId: 17,
  targetPaymentMethodId: 18,
}

const FLAG_BREAKDOWN = 1
const FLAG_SPLIT_CHILD = 2
const FLAG_TRANSFER = 4
const FLAG_BROKEN_TRANSFER = 8
const FLAG_CROSS_CURRENCY = 16

function normalizePartyName(value) {
  return String(value ?? '').normalize('NFKC').trim().replace(/\s+/gu, ' ').toLocaleLowerCase()
}

export function decodeCompactSnapshot(wire) {
  if (!wire || wire.v !== 2 || !Array.isArray(wire.a)) {
    return wire
  }

  const accounts = (wire.A ?? []).map(item => ({
    id: String(item[0]),
    name: item[1] ?? '',
    kind: Number(item[2] ?? 0),
    currencyId: String(item[3] ?? ''),
    defaultDebitMethodId: String(item[4] ?? '0'),
    defaultCreditMethodId: String(item[5] ?? '0'),
    closed: Number(item[6] ?? 0) !== 0,
  }))
  const accountsById = new Map(accounts.map(item => [item.id, item]))

  const parties = (wire.P ?? []).map(item => ({
    id: String(item[0]),
    name: item[1] ?? '',
  }))
  const partiesById = new Map(parties.map(item => [item.id, item]))

  const categories = (wire.C ?? []).map(item => ({
    id: String(item[0]),
    name: item[1] ?? '',
    kind: Number(item[2] ?? 0),
    subcategories: (item[3] ?? []).map(subcategory => ({
      id: String(subcategory[0]),
      name: subcategory[1] ?? '',
    })),
  }))
  const categoriesById = new Map(categories.map(item => [item.id, item]))

  const paymentMethodsByAccount = {}
  const paymentsById = new Map()
  for (const group of wire.M ?? []) {
    const accountId = String(group[0])
    const methods = (group[1] ?? []).map(item => ({
      id: String(item[0]),
      name: item[1] ?? '',
      sign: Number(item[2] ?? 0),
      showEntry: Number(item[3] ?? 0) !== 0,
      automaticNumber: Number(item[4] ?? 0) !== 0,
      currentNumber: item[5] ?? null,
      accountId,
    }))
    paymentMethodsByAccount[accountId] = methods
    for (const method of methods) {
      paymentsById.set(method.id, method)
    }
  }

  const account = {
    id: String(wire.a[0]),
    name: wire.a[1] ?? '',
    kind: Number(wire.a[2] ?? 0),
    currency: {
      id: String(wire.a[3] ?? ''),
      name: wire.a[4] ?? '',
      code: wire.a[5] ?? '',
      symbol: wire.a[6] ?? '',
      precision: Number(wire.a[7] ?? 2),
    },
    totalAmount: String(wire.a[8] ?? '0'),
    totalMarkedAmount: String(wire.a[9] ?? '0'),
    initialBalance: String(wire.a[10] ?? '0'),
  }

  const transactions = (wire.T ?? []).map(item => {
    const partyId = String(item[TX.partyId] ?? '0')
    const categoryId = String(item[TX.categoryId] ?? '0')
    const subcategoryId = String(item[TX.subcategoryId] ?? '0')
    const paymentMethodId = String(item[TX.paymentMethodId] ?? '0')
    const category = categoriesById.get(categoryId)
    const subcategory = category?.subcategories.find(
      candidate => candidate.id === subcategoryId,
    )
    const flags = Number(item[TX.flags] ?? 0)
    const transfer = (flags & FLAG_TRANSFER) !== 0
    const brokenTransfer = (flags & FLAG_BROKEN_TRANSFER) !== 0
    const breakdown = (flags & FLAG_BREAKDOWN) !== 0
    const splitChild = (flags & FLAG_SPLIT_CHILD) !== 0
    const crossCurrency = (flags & FLAG_CROSS_CURRENCY) !== 0
    const targetAccountId = item[TX.targetAccountId] == null
      ? null
      : String(item[TX.targetAccountId])
    const targetPaymentMethodId = item[TX.targetPaymentMethodId] == null
      ? '0'
      : String(item[TX.targetPaymentMethodId])
    const marked = Number(item[TX.marked] ?? 0)

    const protectionReasons = []
    if (breakdown) protectionReasons.push('breakdown')
    if (splitChild) protectionReasons.push('split-child')
    if (brokenTransfer) protectionReasons.push('broken-transfer')
    if (crossCurrency) protectionReasons.push('cross-currency-transfer')

    return {
      id: String(item[TX.id]),
      date: item[TX.date] ?? '',
      valueDate: item[TX.valueDate] ?? null,
      amount: String(item[TX.amount] ?? '0'),
      currencyId: account.currency.id,
      partyId,
      partyName: partiesById.get(partyId)?.name ?? null,
      categoryId,
      categoryName: category?.name ?? null,
      subcategoryId,
      subcategoryName: subcategory?.name ?? null,
      paymentMethodId,
      paymentMethodName: paymentsById.get(paymentMethodId)?.name ?? null,
      note: item[TX.note] ?? null,
      paymentReference: item[TX.paymentReference] ?? null,
      marked,
      quickMarkable: marked === 0 || marked === 1,
      voucher: item[TX.voucher] ?? null,
      bankReference: item[TX.bankReference] ?? null,
      breakdown: String(item[TX.breakdown] ?? '0'),
      transferTransactionId: item[TX.transferId] == null
        ? null
        : String(item[TX.transferId]),
      splitMotherId: item[TX.motherId] == null
        ? null
        : String(item[TX.motherId]),
      isTransfer: transfer,
      transferAccountId: targetAccountId,
      transferAccountName: targetAccountId
        ? accountsById.get(targetAccountId)?.name ?? null
        : null,
      transferPaymentMethodId: targetPaymentMethodId,
      transferPaymentMethodName: paymentsById.get(targetPaymentMethodId)?.name ?? null,
      protected: protectionReasons.length > 0,
      protectionReasons,
    }
  })

  const completionByPartyId = {}
  for (const item of wire.H ?? []) {
    completionByPartyId[String(item[0])] = {
      partyId: String(item[0]),
      sourceAccountId: String(item[1]),
      amount: String(item[2] ?? '0'),
      categoryId: String(item[3] ?? '0'),
      subcategoryId: String(item[4] ?? '0'),
      paymentMethodId: String(item[5] ?? '0'),
      note: item[6] ?? null,
      paymentReference: item[7] ?? null,
      voucher: item[8] ?? null,
      bankReference: item[9] ?? null,
      transferAccountId: item[10] == null ? null : String(item[10]),
      targetPaymentMethodId: item[11] == null ? null : String(item[11]),
    }
  }

  // Always prefer the latest transaction from the account currently being edited.
  // The compact H fallback can come from another account and older XML element
  // truthiness rules could incorrectly select it even when a local transaction exists.
  const completedParties = new Set()
  const preferredPartyIdByName = new Map()
  for (const transaction of sortTransactionsRecentFirst(transactions)) {
    const partyId = String(transaction.partyId ?? '0')
    if (partyId === '0'
      || completedParties.has(partyId)
      || transaction.splitMotherId != null) {
      continue
    }
    completionByPartyId[partyId] = {
      partyId,
      sourceAccountId: account.id,
      amount: transaction.amount,
      categoryId: transaction.isTransfer ? '0' : transaction.categoryId,
      subcategoryId: transaction.isTransfer ? '0' : transaction.subcategoryId,
      paymentMethodId: transaction.paymentMethodId,
      note: transaction.note,
      paymentReference: transaction.paymentReference,
      voucher: transaction.voucher,
      bankReference: transaction.bankReference,
      transferAccountId: transaction.isTransfer ? transaction.transferAccountId : null,
      targetPaymentMethodId: transaction.isTransfer
        ? transaction.transferPaymentMethodId
        : null,
    }
    completedParties.add(partyId)

    const partyNameKey = normalizePartyName(partiesById.get(partyId)?.name)
    if (partyNameKey && !preferredPartyIdByName.has(partyNameKey)) {
      preferredPartyIdByName.set(partyNameKey, partyId)
    }
  }

  // Grisbi files can contain duplicate payee records with the same visible name.
  // Mark the duplicate that has the newest current-account transaction as preferred,
  // so selecting the displayed name cannot silently use another account's history.
  const partyNameCounts = new Map()
  for (const party of parties) {
    const key = normalizePartyName(party.name)
    partyNameCounts.set(key, (partyNameCounts.get(key) ?? 0) + 1)
  }
  for (const party of parties) {
    const key = normalizePartyName(party.name)
    const preferredPartyId = preferredPartyIdByName.get(key) ?? party.id
    const hint = completionByPartyId[party.id]
    const preferred = String(party.id) === String(preferredPartyId)
    const hasCurrentHistory = String(hint?.sourceAccountId ?? '') === String(account.id)
    party.preferredCompletionPartyId = String(preferredPartyId)
    party.completionPriority = preferred && hasCurrentHistory
      ? 0
      : hasCurrentHistory
        ? 1
        : hint
          ? 2
          : 3

    if ((partyNameCounts.get(key) ?? 0) > 1) {
      const sourceAccount = accountsById.get(String(hint?.sourceAccountId ?? ''))
      party.secondary = preferred && hasCurrentHistory
        ? `Latest in ${account.name}`
        : sourceAccount
          ? `Duplicate payee · history from ${sourceAccount.name}`
          : 'Duplicate payee · no previous transaction'
    }
  }

  const preferencesWire = wire.U ?? []
  const preferences = {
    linesPerTransaction: Number(preferencesWire[0] ?? 1),
    twoLinesShowed: Number(preferencesWire[1] ?? 0) !== 0,
    threeLinesShowed: Number(preferencesWire[2] ?? 0) !== 0,
    transactionsView: preferencesWire[3] ?? '',
    transactionColumnWidth: preferencesWire[4] ?? '',
    sortingKindColumn: preferencesWire[5] ?? '',
  }
  const warnings = (wire.W ?? []).map(item => ({
    code: item[0] ?? 'compatibility-warning',
    message: item[1] ?? '',
    tag: item[2] ?? null,
    recordId: item[3] == null ? null : String(item[3]),
    severity: 'warning',
  }))

  return {
    wireVersion: 2,
    account,
    accounts,
    parties,
    categories,
    paymentMethods: paymentMethodsByAccount[account.id] ?? [],
    paymentMethodsByAccount,
    transactions,
    completionByPartyId,
    preferences,
    warnings,
  }
}
