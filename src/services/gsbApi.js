import axios from '@nextcloud/axios'
import { generateUrl } from '@nextcloud/router'

export async function fetchEditorSnapshot({ accountId, filePath, filePassword }) {
  const url = generateUrl('/apps/ncgrisbi/api/editor/account/{accountId}', {
    accountId: String(accountId),
  })
  const response = await axios.post(url, { filePath, filePassword })
  return response.data
}

export async function mutateDocument({ filePath, filePassword, baseEtag, operations }) {
  const response = await axios.post(generateUrl('/apps/ncgrisbi/api/mutations'), {
    filePath,
    filePassword,
    baseEtag,
    operations,
  })
  return response.data
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
