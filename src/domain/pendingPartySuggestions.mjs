import { normalizeName } from './transactionEditor.mjs'

/**
 * Add party names from locally applied new transactions to the autocomplete.
 * A pending name deliberately has no Grisbi ID: the batch mutation resolves
 * or creates it on Save all. Never insert these pseudo-records into snapshot.
 */
export function partyChoicesWithPending(savedParties, rows) {
  const knownNames = new Set(savedParties.map(party => normalizeName(party.name)))
  const pending = []

  // Latest draft first, including when the same new payee is used more than once.
  for (let index = rows.length - 1; index >= 0; index--) {
    const row = rows[index]
    if (!row.isNew || !row.locallyApplied || row.deleted) continue
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
