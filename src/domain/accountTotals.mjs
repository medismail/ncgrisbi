function finiteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function snapshotAccountTotals(account) {
  const id = String(account?.id ?? '')
  const totalAmount = finiteNumber(account?.totalAmount)
  const totalMarkedAmount = finiteNumber(account?.totalMarkedAmount)
  if (!id || totalAmount === null || totalMarkedAmount === null) return {}
  return {
    [id]: {
      total_amount: totalAmount,
      total_marked_amount: totalMarkedAmount,
    },
  }
}

export function mergeAccountTotals(accounts, totalsByAccount) {
  if (!Array.isArray(accounts) || !totalsByAccount || typeof totalsByAccount !== 'object') {
    return Array.isArray(accounts) ? accounts : []
  }

  let changed = false
  const next = accounts.map(account => {
    const totals = totalsByAccount[String(account?.id ?? '')]
    if (!totals || typeof totals !== 'object') return account

    const totalAmount = finiteNumber(totals.total_amount)
    const totalMarkedAmount = finiteNumber(totals.total_marked_amount)
    if (totalAmount === null || totalMarkedAmount === null) return account

    const currentTotal = finiteNumber(account?.total?.total_amount)
    const currentMarked = finiteNumber(account?.total?.total_marked_amount)
    if (currentTotal === totalAmount && currentMarked === totalMarkedAmount) {
      return account
    }

    changed = true
    return {
      ...account,
      total: {
        ...(account?.total ?? {}),
        total_amount: totalAmount,
        total_marked_amount: totalMarkedAmount,
      },
    }
  })

  return changed ? next : accounts
}
