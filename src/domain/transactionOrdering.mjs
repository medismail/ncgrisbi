const TEXT_COLLATOR = new Intl.Collator(undefined, {
  sensitivity: 'base',
  numeric: true,
})

function dateKey(value) {
  const text = String(value ?? '').trim()
  let match = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/u)
  if (match) {
    const [, month, day, year] = match
    return Number(year) * 10000 + Number(month) * 100 + Number(day)
  }
  match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/u)
  if (match) {
    const [, year, month, day] = match
    return Number(year) * 10000 + Number(month) * 100 + Number(day)
  }
  return 0
}

function integerText(value) {
  const text = String(value ?? '').trim()
  if (!/^\d+$/u.test(text)) return null
  return text.replace(/^0+(?=\d)/u, '')
}

function compareIntegerTextDesc(left, right) {
  if (left.length !== right.length) return right.length - left.length
  if (left === right) return 0
  return left > right ? -1 : 1
}

function localSequence(row) {
  const match = String(row?.key ?? '').match(/(?:^|-)new-(\d+)$/u)
  return match ? Number(match[1]) : 0
}

function normalizedText(value) {
  return String(value ?? '').normalize('NFKC').trim().replace(/\s+/gu, ' ')
}

function baseOrderingRecord(row, index) {
  return {
    row,
    index,
    date: dateKey(row?.date),
    number: integerText(row?.transactionId ?? row?.id),
    sequence: localSequence(row),
    key: String(row?.key ?? row?.id ?? ''),
  }
}

function orderingRecord(row, index, mode) {
  const record = baseOrderingRecord(row, index)
  if (mode === 'party') {
    record.primary = normalizedText(row?.partyName)
  } else if (mode === 'category') {
    record.primary = row?.isTransfer
      ? 'Transfer'
      : normalizedText(row?.categoryName)
    record.secondary = normalizedText(row?.subcategoryName)
  }
  return record
}

function compareTextMissingLast(left, right) {
  if (!left && !right) return 0
  if (!left) return 1
  if (!right) return -1
  return TEXT_COLLATOR.compare(left, right)
}

function compareRecentRecords(left, right) {
  const dateDifference = right.date - left.date
  if (dateDifference) return dateDifference

  if (left.number !== null && right.number !== null) {
    const numberDifference = compareIntegerTextDesc(left.number, right.number)
    if (numberDifference) return numberDifference
  } else if (left.number === null && right.number !== null) {
    return -1
  } else if (left.number !== null && right.number === null) {
    return 1
  }

  const sequenceDifference = right.sequence - left.sequence
  if (sequenceDifference) return sequenceDifference
  const keyDifference = right.key.localeCompare(left.key)
  return keyDifference || right.index - left.index
}

function comparePartyRecords(left, right) {
  const partyDifference = compareTextMissingLast(left.primary, right.primary)
  return partyDifference || compareRecentRecords(left, right)
}

function compareCategoryRecords(left, right) {
  const categoryDifference = compareTextMissingLast(left.primary, right.primary)
  if (categoryDifference) return categoryDifference

  const subcategoryDifference = compareTextMissingLast(left.secondary, right.secondary)
  return subcategoryDifference || compareRecentRecords(left, right)
}

export function compareTransactionsRecentFirst(left, right) {
  return compareRecentRecords(
    orderingRecord(left, 0, 'date'),
    orderingRecord(right, 0, 'date'),
  )
}

export function sortTransactions(rows, mode = 'date') {
  const normalizedMode = ['party', 'category'].includes(mode) ? mode : 'date'
  const compare = normalizedMode === 'party'
    ? comparePartyRecords
    : normalizedMode === 'category'
      ? compareCategoryRecords
      : compareRecentRecords

  return rows
    .map((row, index) => orderingRecord(row, index, normalizedMode))
    .sort(compare)
    .map(record => record.row)
}

export function sortTransactionsRecentFirst(rows) {
  return sortTransactions(rows, 'date')
}
