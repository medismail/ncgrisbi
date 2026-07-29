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

function orderingRecord(row, index) {
  return {
    row,
    index,
    date: dateKey(row?.date),
    number: integerText(row?.transactionId ?? row?.id),
    sequence: localSequence(row),
    key: String(row?.key ?? row?.id ?? ''),
  }
}

function compareRecords(left, right) {
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

export function compareTransactionsRecentFirst(left, right) {
  return compareRecords(orderingRecord(left, 0), orderingRecord(right, 0))
}

export function sortTransactionsRecentFirst(rows) {
  return rows
    .map(orderingRecord)
    .sort(compareRecords)
    .map(record => record.row)
}
