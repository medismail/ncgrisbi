/**
 * Fold accents for finding text, not for identifying Grisbi records.
 * Cafe and Café must remain distinct names when creating/reusing parties.
 */
export function normalizeSearchText(value) {
  return String(value ?? '')
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .trim()
    .replace(/\s+/gu, ' ')
    .toLocaleLowerCase()
}
