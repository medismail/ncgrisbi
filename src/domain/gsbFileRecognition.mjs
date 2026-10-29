/**
 * Identify readable Grisbi files by extension rather than trusting the
 * instance's cached MIME type. Existing files may predate the MIME mapping.
 *
 * The action is for one ordinary file, not folders or multi-selection.
 */
export function isReadableGsbFile(node, readPermission, fileType) {
  return node != null
    && node.type === fileType
    && typeof node.path === 'string'
    && /\.gsb$/i.test(node.path)
    && (node.permissions & readPermission) !== 0
}
