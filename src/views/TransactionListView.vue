<template>
  <NcAppContent>
    <div v-if="loading" class="loading">
      <NcLoadingIcon :size="32" />
      <p>Loading transactions…</p>
    </div>

    <div v-else-if="snapshot" class="editor">
      <div v-if="message" class="message" :class="messageType">
        {{ message }}
        <button v-if="conflict" type="button" @click="reloadAfterConflict">
          Reload current file
        </button>
      </div>

      <header class="account-header">
        <div>
          <h2>{{ snapshot.account.name }}</h2>
          <p>Account {{ snapshot.account.id }} · ETag {{ etag }}</p>
        </div>
        <div class="totals">
          <strong>{{ totals.totalAmount }} {{ snapshot.account.currency.code }}</strong>
          <span>Marked: {{ totals.totalMarkedAmount }} {{ snapshot.account.currency.code }}</span>
        </div>
      </header>

      <div class="toolbar">
        <button type="button" :disabled="saving || conflict" @click="addTransaction">
          Add transaction
        </button>
        <button
          type="button"
          :disabled="saving || conflict || !pendingChanges"
          @click="saveChanges"
        >
          {{ saving ? 'Saving…' : 'Save changes' }}
        </button>
        <button type="button" :disabled="saving" @click="reloadSnapshot">
          Discard and reload
        </button>
      </div>

      <datalist id="phase5-parties">
        <option v-for="party in snapshot.parties" :key="party.id" :value="party.name" />
      </datalist>
      <datalist id="phase5-categories">
        <option v-for="category in snapshot.categories" :key="category.id" :value="category.name" />
      </datalist>
      <datalist id="phase5-payments">
        <option v-for="payment in snapshot.paymentMethods" :key="payment.id" :value="payment.name" />
      </datalist>

      <div class="table-scroll">
        <table class="transactions-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Date</th>
              <th>Amount</th>
              <th>Party</th>
              <th>Category</th>
              <th>Subcategory</th>
              <th>Payment</th>
              <th>Note</th>
              <th>Marked</th>
              <th>Bank reference</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in displayedRows"
              :key="row.key"
              :class="{ deleted: row.deleted, protected: row.protected }"
            >
              <td>{{ row.transactionId || 'new' }}</td>
              <td><input v-model="row.date" :disabled="!isEditable(row)" size="10"></td>
              <td><input v-model="row.amount" :disabled="!isEditable(row)" type="number" step="any"></td>
              <td>
                <input v-model="row.partyName" :disabled="!isEditable(row)" list="phase5-parties">
              </td>
              <td>
                <input
                  v-model="row.categoryName"
                  :disabled="!isEditable(row)"
                  list="phase5-categories"
                  @input="row.subcategoryName = ''"
                >
              </td>
              <td>
                <input
                  v-model="row.subcategoryName"
                  :disabled="!isEditable(row)"
                  :list="`phase5-subcategories-${row.key}`"
                >
                <datalist :id="`phase5-subcategories-${row.key}`">
                  <option
                    v-for="subcategory in subcategoriesFor(row)"
                    :key="subcategory.id"
                    :value="subcategory.name"
                  />
                </datalist>
              </td>
              <td>
                <input
                  v-model="row.paymentMethodName"
                  :disabled="!isEditable(row)"
                  list="phase5-payments"
                >
              </td>
              <td><input v-model="row.note" :disabled="!isEditable(row)"></td>
              <td>
                <input
                  type="checkbox"
                  :checked="Number(row.marked) === 1"
                  :disabled="!isEditable(row)"
                  @change="row.marked = $event.target.checked ? 1 : 0"
                >
              </td>
              <td><input v-model="row.bankReference" :disabled="!isEditable(row)"></td>
              <td>
                <span v-if="row.deleted">Pending deletion</span>
                <span v-else-if="row.protected">
                  Read-only: {{ row.protectionReasons.join(', ') }}
                </span>
                <span v-else-if="row.isNew">New</span>
                <span v-else-if="row.editing">Editing</span>
                <span v-else>Saved</span>
              </td>
              <td class="actions">
                <button v-if="row.deleted" type="button" @click="row.deleted = false">
                  Undo
                </button>
                <template v-else-if="!row.protected">
                  <button v-if="!row.editing" type="button" @click="row.editing = true">
                    Edit
                  </button>
                  <button v-else-if="!row.isNew" type="button" @click="cancelEdit(row)">
                    Cancel
                  </button>
                  <button type="button" @click="removeTransaction(row)">
                    Delete
                  </button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </NcAppContent>
</template>

<script setup>
import { NcAppContent, NcLoadingIcon } from '@nextcloud/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import {
  buildMutationOperations,
  calculateTotals,
  createDrafts,
  hasPendingChanges,
  newTransactionDraft,
  normalizeName,
} from '@/domain/transactionEditor.mjs'
import { apiError, fetchEditorSnapshot, mutateDocument } from '@/services/gsbApi'

const store = useStore()
const route = useRoute()
const router = useRouter()
const loading = ref(true)
const saving = ref(false)
const snapshot = ref(null)
const rows = ref([])
const etag = ref('')
const selectedAccountId = ref(String(route.params.id))
const message = ref('')
const messageType = ref('info')
const conflict = ref(false)
let newSequence = 0
let revertingRoute = false

const displayedRows = computed(() => [...rows.value].reverse())
const pendingChanges = computed(() => hasPendingChanges(rows.value))
const totals = computed(() => calculateTotals(
  rows.value,
  snapshot.value?.account?.currency?.precision ?? 2,
))

function setMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

async function loadSnapshot() {
  loading.value = true
  conflict.value = false
  try {
    const response = await fetchEditorSnapshot({
      accountId: selectedAccountId.value,
      filePath: store.state.filePath,
      filePassword: store.state.filePassword,
    })
    snapshot.value = response.snapshot
    etag.value = response.document.etag
    rows.value = createDrafts(response.snapshot)
    setMessage('')
  } catch (error) {
    const failure = apiError(error)
    setMessage(failure.message, 'error')
  } finally {
    loading.value = false
  }
}

function isEditable(row) {
  return !row.deleted && !row.protected && row.editing
}

function subcategoriesFor(row) {
  const key = normalizeName(row.categoryName)
  const category = snapshot.value.categories.find(item => normalizeName(item.name) === key)
  return category?.subcategories ?? []
}

function today() {
  const value = new Date()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${month}/${day}/${value.getFullYear()}`
}

function addTransaction() {
  newSequence += 1
  rows.value.push(newTransactionDraft(snapshot.value, `new-${newSequence}`, today()))
}

function cancelEdit(row) {
  Object.assign(row, row.original)
  row.editing = false
}

function removeTransaction(row) {
  if (row.isNew) {
    rows.value = rows.value.filter(candidate => candidate.key !== row.key)
  } else {
    row.deleted = true
    row.editing = false
  }
}

async function saveChanges() {
  let operations
  try {
    operations = buildMutationOperations(rows.value, snapshot.value)
  } catch (error) {
    setMessage(error.message, 'error')
    return
  }
  if (operations.length === 0) {
    setMessage('There are no validated changes to save.')
    return
  }

  saving.value = true
  try {
    const response = await mutateDocument({
      filePath: store.state.filePath,
      filePassword: store.state.filePassword,
      baseEtag: etag.value,
      operations,
    })
    etag.value = response.document.etag
    setMessage('Transactions saved successfully.', 'success')
    await loadSnapshot()
  } catch (error) {
    const failure = apiError(error)
    conflict.value = failure.code === 'etag-conflict'
    setMessage(
      conflict.value
        ? 'The GSB file changed elsewhere. Your draft is preserved; reload before saving again.'
        : failure.message,
      'error',
    )
  } finally {
    saving.value = false
  }
}

async function reloadSnapshot() {
  if (pendingChanges.value && !window.confirm('Discard all unsaved transaction changes?')) {
    return
  }
  await loadSnapshot()
}

async function reloadAfterConflict() {
  if (!window.confirm('Reload the current file and discard this local draft?')) {
    return
  }
  await loadSnapshot()
}

onMounted(loadSnapshot)

watch(() => route.params.id, async newId => {
  if (revertingRoute) {
    revertingRoute = false
    return
  }
  if (pendingChanges.value && !window.confirm('Discard unsaved changes and switch accounts?')) {
    revertingRoute = true
    await router.replace({ name: 'Account', params: { id: selectedAccountId.value } })
    return
  }
  selectedAccountId.value = String(newId)
  await loadSnapshot()
})
</script>

<style scoped>
.editor { padding: 16px; }
.loading { display: flex; gap: 12px; align-items: center; justify-content: center; min-height: 240px; }
.account-header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
.account-header h2 { margin-bottom: 4px; }
.account-header p { opacity: .7; }
.totals { display: flex; flex-direction: column; text-align: right; }
.toolbar { display: flex; gap: 8px; margin: 16px 0; }
.message { margin: 0 0 12px; padding: 10px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); }
.message.error { border-color: var(--color-error); }
.message.success { border-color: var(--color-success); }
.message button { margin-left: 12px; }
.table-scroll { overflow: auto; max-height: 65vh; }
.transactions-table { min-width: 1500px; width: 100%; border-collapse: collapse; }
th, td { padding: 5px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
th { position: sticky; top: 0; background: var(--color-main-background); z-index: 1; text-align: left; }
td input:not([type='checkbox']) { width: 100%; min-width: 105px; }
tr.deleted { opacity: .55; text-decoration: line-through; }
tr.protected { background: var(--color-background-dark); }
.actions { white-space: nowrap; }
.actions button { margin-right: 4px; }
</style>
