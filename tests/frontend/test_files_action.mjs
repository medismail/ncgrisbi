import assert from 'node:assert/strict'
import { isReadableGsbFile } from '../../src/domain/gsbFileRecognition.mjs'

// Keep checks independent of a running Nextcloud instance: these values model
// the Files API's FileType.File and Permission.READ constants.
const FILE = 'file'
const FOLDER = 'folder'
const READ = 1
const WRITE = 2
const node = (path, mime = 'application/x-gsb', permissions = READ, type = FILE) => ({
  path, mime, permissions, type,
})

assert.equal(isReadableGsbFile(node('/alice/files/Budget.gsb'), READ, FILE), true)
assert.equal(isReadableGsbFile(node('/alice/files/Épargne.GSB'), READ, FILE), true)
assert.equal(isReadableGsbFile(node('/alice/files/old.gsb', 'application/octet-stream'), READ, FILE), true)
assert.equal(isReadableGsbFile(node('/alice/files/report.gsb', 'text/plain'), READ, FILE), true)
assert.equal(isReadableGsbFile(node('/alice/files/report.gsb.bak'), READ, FILE), false)
assert.equal(isReadableGsbFile(node('/alice/files/report.xml'), READ, FILE), false)
assert.equal(isReadableGsbFile(node('/alice/files/report.gsb', 'application/x-gsb', WRITE), READ, FILE), false)
assert.equal(isReadableGsbFile(node('/alice/files/report.gsb', 'application/x-gsb', READ, FOLDER), READ, FILE), false)
assert.equal(isReadableGsbFile(null, READ, FILE), false)

console.log('Files action recognition tests passed')
