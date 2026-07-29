import axios from '@nextcloud/axios'
import { showError, showSuccess } from '@nextcloud/dialogs'
import { generateUrl } from '@nextcloud/router'
import { decodeCompactSnapshot } from '@/domain/snapshotWire.mjs'

function invalidPayload(message, data) {
  const error = new Error(message)
  error.response = {
    status: 422,
    data: {
      success: false,
      code: data?.code ?? 'invalid-response',
      message: data?.message ?? message,
      details: data,
    },
  }
  return error
}

export async function fetchAccounts({ filePath, filePassword = '' }) {
  const response = await axios.post(generateUrl('/apps/ncgrisbi/api/accounts'), {
    filePath,
    filePassword,
  })
  if (!Array.isArray(response.data)) {
    throw invalidPayload('The Grisbi account response is invalid.', response.data)
  }
  return response.data
}

export async function fetchDocumentState({ filePath }) {
  const response = await axios.get(generateUrl('/apps/ncgrisbi/api/checkencrypted'), {
    params: { filePath },
  })
  const data = response.data ?? {}
  if (!['True', 'False'].includes(String(data.Encrypted))) {
    throw invalidPayload('The Grisbi document state response is invalid.', data)
  }
  return {
    encrypted: String(data.Encrypted) === 'True',
    compressed: Boolean(data.Compressed),
    etag: data.etag ?? '',
  }
}

export async function fetchEditorSnapshot({ accountId, filePath, filePassword }) {
  const url = generateUrl('/apps/ncgrisbi/api/editor/account/{accountId}', {
    accountId: String(accountId),
  })
  const response = await axios.post(url, { filePath, filePassword })
  return {
    ...response.data,
    snapshot: decodeCompactSnapshot(response.data.snapshot),
  }
}

export async function mutateDocument({ filePath, filePassword, baseEtag, operations }) {
  try {
    const response = await axios.post(generateUrl('/apps/ncgrisbi/api/mutations'), {
      filePath,
      filePassword,
      baseEtag,
      operations,
    })
    showSuccess('All pending transactions were saved.')
    return response.data
  } catch (error) {
    const failure = apiError(error)
    if (failure.code !== 'confirmation-required') {
      showError(failure.message, { timeout: 7000 })
    }
    throw error
  }
}

export function apiError(error) {
  const data = error?.response?.data ?? {}
  return {
    status: error?.response?.status ?? 0,
    code: data.code ?? 'request-failed',
    message: data.message ?? error?.message ?? 'The request failed.',
    currentEtag: data.currentEtag ?? null,
    details: data.details ?? null,
  }
}
