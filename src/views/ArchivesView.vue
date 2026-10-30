<template>
  <section class="archives-page" aria-labelledby="archives-title">
    <header class="archives-header">
      <div>
        <h1 id="archives-title">Archives</h1>
        <p>Archived transactions remain in the Grisbi file and continue to count toward account balances.</p>
      </div>
      <button type="button" :aria-expanded="showCreate" aria-controls="archive-creator"
        @click="showCreate = !showCreate">
        {{ showCreate ? 'Close creator' : 'Create archive' }}
      </button>
    </header>

    <section v-if="showCreate" id="archive-creator" class="creator" aria-labelledby="create-title">
      <h2 id="create-title">Create archive by date</h2>
      <p>Preview the transactions first. Related transfers and split transactions are included automatically.</p>
      <form @submit.prevent="previewArchive">
        <label>Archive name
          <input v-model.trim="archiveName" type="text" maxlength="120" required autocomplete="off">
        </label>
        <label>Start date
          <input v-model="startDate" type="date" required>
        </label>
        <label>End date
          <input v-model="endDate" type="date" :min="startDate || undefined" required>
        </label>
        <button type="submit" :disabled="busy || pendingChanges || !archiveName || !startDate || !endDate">
          {{ busy ? 'Checking…' : 'Preview archive' }}
        </button>
      </form>
      <p v-if="pendingChanges" class="notice" role="status">
        Save or discard pending transaction edits before creating an archive.
      </p>
      <div v-if="preview" class="preview" aria-live="polite">
        <h3>Archive preview</h3>
        <p><strong>{{ preview.count }}</strong> transactions · {{ archiveName }}</p>
        <ul>
          <li v-for="account in previewAccounts" :key="account.id">
            {{ account.name }} — {{ account.count }} transactions · {{ account.amount }}
            {{ account.currency }}
          </li>
        </ul>
        <p>Archive creation does not delete transactions or change account balances.</p>
        <button type="button" :disabled="busy || pendingChanges" @click="createArchive">
          {{ busy ? 'Saving…' : 'Confirm and create archive' }}
        </button>
      </div>
    </section>

    <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
    <p v-if="successMessage" class="success" role="status">{{ successMessage }}</p>

    <section aria-labelledby="existing-title">
      <h2 id="existing-title">Saved archives ({{ archives.length }})</h2>
      <p v-if="!archives.length">No archives have been created in this file.</p>
      <ul v-else class="archive-list">
        <li v-for="archive in archives" :key="archive.id" class="archive-card">
          <div class="archive-header">
            <div>
              <h3>{{ archive.name || `Archive ${archive.id}` }}</h3>
              <p>{{ archive.count }} transactions
                <template v-if="archive.startDate && archive.endDate">
                  · {{ archive.startDate }} – {{ archive.endDate }}
                </template>
              </p>
            </div>
          </div>
          <p v-if="!Object.keys(archive.accounts || {}).length">No linked transactions.</p>
          <ul v-else class="archive-accounts">
            <li v-for="account in archiveAccounts(archive)" :key="account.id">
              <button type="button" class="archive-account"
                :aria-expanded="openKey === keyFor(archive.id, account.id)"
                :disabled="busy || pendingChanges"
                @click="toggleAccount(archive.id, account.id)">
                <span>{{ account.name }} · {{ account.count }} transactions ·
                  {{ account.amount }} {{ account.currency }}</span>
                <span aria-hidden="true">{{ openKey === keyFor(archive.id, account.id) ? '−' : '+' }}</span>
              </button>
              <div v-if="openKey === keyFor(archive.id, account.id)" class="archive-details">
                <p v-if="loadingDetails" role="status">Loading archived transactions…</p>
                <template v-else>
                  <p v-if="!details.length">No transactions found.</p>
                  <template v-else>
                    <p class="read-only">Archived transactions are read-only. Viewing them does not change the file.</p>
                    <div class="table-scroll">
                      <table>
                        <caption>Archived transactions — {{ archive.name }} / {{ account.name }}</caption>
                        <thead><tr><th scope="col">Date</th><th scope="col">Party</th>
                          <th scope="col">Category</th><th scope="col">Amount</th></tr></thead>
                        <tbody>
                          <tr v-for="tx in visibleDetails" :key="tx.id">
                            <td>{{ tx.date }}</td>
                            <td>{{ tx.partyName || 'No party' }}</td>
                            <td>{{ [tx.categoryName, tx.subcategoryName].filter(Boolean).join(' / ') || '—' }}</td>
                            <td class="amount">{{ tx.amount }} {{ account.currency }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div class="pagination">
                      <span>{{ page * pageSize + 1 }}–{{ Math.min((page + 1) * pageSize, details.length) }} of {{ details.length }}</span>
                      <button type="button" :disabled="page === 0" @click="page -= 1">Previous</button>
                      <button type="button" :disabled="(page + 1) * pageSize >= details.length"
                        @click="page += 1">Next</button>
                    </div>
                  </template>
                </template>
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </section>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { apiError, fetchArchiveAccount, fetchArchivePreview, mutateDocument } from '@/services/gsbApi'

const store = useStore()
const archives = computed(() => store.state.archives || [])
const accounts = computed(() => store.state.accounts || [])
const pendingChanges = computed(() => store.state.transactionPending.active)
const showCreate = ref(false)
const archiveName = ref('')
const startDate = ref('')
const endDate = ref('')
const preview = ref(null)
const previewEtag = ref(null)
const previewParams = ref('')
const busy = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const openKey = ref('')
const details = ref([])
const loadingDetails = ref(false)
const page = ref(0)
const pageSize = 100

const visibleDetails = computed(() => details.value.slice(page.value * pageSize, (page.value + 1) * pageSize))
const previewAccounts = computed(() => Object.entries(preview.value?.accounts || {}).map(([id, data]) => ({
  id, name: accountName(id), currency: accountCurrency(id), ...data,
})))
function accountName(id) {
  return accounts.value.find(item => String(item.id) === String(id))?.name || `Account ${id}`
}
function accountCurrency(id) {
  const account = accounts.value.find(item => String(item.id) === String(id))
  return account?.currency?.code || account?.currency || ''
}
function archiveAccounts(archive) {
  return Object.entries(archive.accounts || {}).map(([id, data]) => ({
    id, name: accountName(id), currency: accountCurrency(id), ...data,
  }))
}
function keyFor(archiveId, accountId) {
  return `${archiveId}:${accountId}`
}
function apiOptions() {
  return { filePath: store.state.filePath, filePassword: store.state.filePassword }
}
function toGrisbiDate(iso) {
  const [year, month, day] = iso.split('-')
  return `${month}/${day}/${year}`
}
watch([archiveName, startDate, endDate], () => {
  preview.value = null
  previewEtag.value = null
  previewParams.value = ''
  errorMessage.value = ''
})
async function previewArchive() {
  if (pendingChanges.value || busy.value) return
  errorMessage.value = ''
  successMessage.value = ''
  preview.value = null
  busy.value = true
  try {
    const start = toGrisbiDate(startDate.value)
    const end = toGrisbiDate(endDate.value)
    const response = await fetchArchivePreview({
      ...apiOptions(), startDate: start, endDate: end,
    })
    preview.value = response.snapshot
    previewEtag.value = response.document.etag
    previewParams.value = JSON.stringify([archiveName.value, start, end])
  } catch (error) {
    errorMessage.value = apiError(error).message
  } finally {
    busy.value = false
  }
}
async function createArchive() {
  if (!preview.value || !previewEtag.value || pendingChanges.value || busy.value) return
  const start = toGrisbiDate(startDate.value)
  const end = toGrisbiDate(endDate.value)
  if (previewParams.value !== JSON.stringify([archiveName.value, start, end])) return
  if (!window.confirm(`Create archive “${archiveName.value}” with ${preview.value.count} transactions? No transactions will be deleted.`)) return
  errorMessage.value = ''
  busy.value = true
  try {
    await mutateDocument({
      ...apiOptions(),
      baseEtag: previewEtag.value,
      operations: [{ type: 'createArchive', name: archiveName.value, startDate: start, endDate: end }],
    })
    await store.dispatch('fetchAccounts')
    successMessage.value = `Archive “${archiveName.value}” was created.`
    preview.value = null
    previewEtag.value = null
    previewParams.value = ''
    showCreate.value = false
    openKey.value = ''
    details.value = []
    archiveName.value = ''
    startDate.value = ''
    endDate.value = ''
  } catch (error) {
    const problem = apiError(error)
    errorMessage.value = problem.code === 'etag-conflict'
      ? 'The Grisbi file changed since the preview. Preview the archive again.'
      : problem.message
    preview.value = null
  } finally {
    busy.value = false
  }
}
async function toggleAccount(archiveId, accountId) {
  if (pendingChanges.value || busy.value) return
  const key = keyFor(archiveId, accountId)
  if (openKey.value === key) {
    openKey.value = ''
    details.value = []
    return
  }
  openKey.value = key
  page.value = 0
  details.value = []
  errorMessage.value = ''
  loadingDetails.value = true
  try {
    const response = await fetchArchiveAccount({ ...apiOptions(), accountId, archiveId })
    if (openKey.value === key) details.value = response.snapshot.transactions
  } catch (error) {
    errorMessage.value = apiError(error).message
    openKey.value = ''
  } finally {
    loadingDetails.value = false
  }
}
</script>

<style scoped>
.archives-page { padding: 24px; max-width: 1100px; margin: 0 auto; display: grid; gap: 22px; }
.archives-header { display: flex; gap: 20px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
h1, h2, h3 { margin: 0 0 7px; }
p { margin: 4px 0 10px; }
button { cursor: pointer; border: 1px solid var(--color-border); border-radius: 7px; padding: 9px 13px; background: var(--color-main-background); color: var(--color-main-text); }
button:focus-visible, input:focus-visible { outline: 2px solid var(--color-primary-element); outline-offset: 2px; }
button:disabled { opacity: .55; cursor: not-allowed; }
.archives-header > button, form button, .preview button { background: var(--color-primary-element); color: var(--color-primary-element-text); }
.creator, .archive-card { padding: 20px; border: 1px solid var(--color-border); border-radius: 10px; background: var(--color-main-background); }
.creator form { display: flex; align-items: end; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
.creator label { display: grid; gap: 5px; min-width: 170px; flex: 1; }
.creator input { min-height: 37px; padding: 5px; border: 1px solid var(--color-border); border-radius: 5px; color: var(--color-main-text); background: var(--color-main-background); }
.archive-list, .archive-accounts { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.archive-list { gap: 16px; }
.archive-card { display: grid; gap: 12px; }
.archive-account { display: flex; justify-content: space-between; width: 100%; text-align: left; }
.archive-details { margin: 12px 0 0; padding: 12px; background: var(--color-background-hover); border-radius: 7px; }
.table-scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
caption { text-align: left; padding-bottom: 12px; font-weight: 600; }
th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--color-border); }
.amount { text-align: right; font-variant-numeric: tabular-nums; }
.pagination { display: flex; justify-content: end; gap: 10px; align-items: center; padding-top: 12px; }
.preview { padding-top: 15px; }
.notice, .error { color: var(--color-error); }
.success { color: var(--color-success); }
.read-only { font-size: .9rem; }
@media (max-width: 650px) { .archives-page { padding: 14px; } .creator label { min-width: 100%; } }
</style>
