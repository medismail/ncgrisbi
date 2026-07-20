<template>
  <NcAppContent>
    <div v-if="loading" class="loading">
      <NcLoadingIcon :size="32" />
      <p>Loading transactions…</p>
    </div>

    <main v-else-if="snapshot" class="workspace">
      <header class="account-header">
        <div class="account-title">
          <h1>{{ snapshot.account.name }}</h1>
          <span>{{ displayedRows.length }} transactions</span>
        </div>
        <div class="totals" aria-label="Account totals">
          <strong>{{ totals.totalAmount }} {{ snapshot.account.currency.code }}</strong>
          <span>Checked: {{ totals.totalMarkedAmount }} {{ snapshot.account.currency.code }}</span>
        </div>
      </header>

      <div v-if="message" class="message" :class="messageType" role="status">
        <span>{{ message }}</span>
        <button v-if="conflict" type="button" @click="reloadAfterConflict">Reload current file</button>
      </div>

      <section class="toolbar" aria-label="Transaction actions">
        <div class="toolbar-group primary-actions">
          <button type="button" class="primary-button" :disabled="saving || conflict" @click="addTransaction">
            Add transaction
          </button>
          <button
            type="button"
            class="save-button"
            :disabled="saving || conflict || !pendingChanges"
            @click="saveChanges"
          >
            {{ saving ? 'Saving…' : `Save all to file${pendingSummary.total ? ` (${pendingSummary.total})` : ''}` }}
          </button>
          <button type="button" :disabled="saving" @click="reloadSnapshot">Discard pending</button>
        </div>

        <div class="toolbar-group view-actions">
          <span class="toolbar-label">Rows</span>
          <div class="segmented" role="group" aria-label="Transaction row detail">
            <button type="button" :class="{ active: displayMode === 'compact' }" @click="displayMode = 'compact'">Compact</button>
            <button type="button" :class="{ active: displayMode === 'detailed' }" @click="displayMode = 'detailed'">Detailed</button>
          </div>
          <label class="filter-control">
            <span>Bank status</span>
            <select v-model="markFilter">
              <option value="all">All</option>
              <option value="unchecked">Unchecked</option>
              <option value="checked">Checked</option>
              <option value="locked">Telepointed / reconciled</option>
            </select>
          </label>
        </div>
      </section>

      <div v-if="pendingChanges" class="pending-banner">
        <strong>{{ pendingSummary.total }} pending change{{ pendingSummary.total === 1 ? '' : 's' }}</strong>
        <span v-if="pendingSummary.created">{{ pendingSummary.created }} new</span>
        <span v-if="pendingSummary.edited">{{ pendingSummary.edited }} edited</span>
        <span v-if="pendingSummary.marked">{{ pendingSummary.marked }} checked/unchecked</span>
        <span v-if="pendingSummary.deleted">{{ pendingSummary.deleted }} deleted</span>
        <small>All changes remain in this browser until the single file save.</small>
      </div>

      <section class="transaction-list" :class="`mode-${displayMode}`" aria-label="Transactions">
        <div class="transaction-header" aria-hidden="true">
          <span>Date</span>
          <span>Party</span>
          <span class="category-column">Category</span>
          <span class="amount-column">Amount</span>
          <span class="mark-column">Marked</span>
          <span>Status</span>
          <span>Actions</span>
        </div>

        <DynamicScroller
          class="scroller"
          :items="displayedRows"
          :min-item-size="displayMode === 'detailed' ? 88 : 58"
          key-field="key"
        >
          <template #default="{ item: row, active, index }">
            <DynamicScrollerItem
              :item="row"
              :active="active"
              :data-index="index"
              :size-dependencies="[displayMode, row.note, row.categoryName, row.subcategoryName, row.deleted]"
              class="transaction-row"
              :class="rowClasses(row)"
            >
              <div
                class="row-content"
                :tabindex="canOpen(row) ? 0 : -1"
                :role="canOpen(row) ? 'button' : undefined"
                @click="canOpen(row) && openEditor(row)"
                @keydown.enter.prevent="canOpen(row) && openEditor(row)"
              >
                <span class="date-cell">{{ shortDate(row.date) }}</span>
                <span class="party-cell">{{ row.partyName || 'No party' }}</span>
                <span class="category-cell">
                  <strong>{{ categoryLabel(row) }}</strong>
                  <small v-if="row.subcategoryName">{{ row.subcategoryName }}</small>
                </span>
                <span class="amount-cell" :class="{ credit: Number(row.amount) > 0, debit: Number(row.amount) < 0 }">
                  {{ formatAmount(row.amount) }}
                </span>
                <span class="mark-cell" @click.stop @keydown.stop>
                  <input
                    v-if="row.isNew || row.quickMarkable"
                    type="checkbox"
                    :checked="Number(row.marked) === 1"
                    :disabled="saving || conflict || row.deleted"
                    :title="markTitle(row)"
                    :aria-label="`Mark transaction ${row.transactionId || 'new'}`"
                    @change="quickMarkChanged(row, $event)"
                  >
                  <span v-else-if="Number(row.marked) === 2" class="state-icon telepointed" title="Telepointed">T</span>
                  <span v-else class="state-icon reconciled" title="Reconciled">R</span>
                </span>
                <span class="status-cell" :title="statusTitle(row)">{{ statusLabel(row) }}</span>
                <span class="actions-cell" @click.stop>
                  <button v-if="row.deleted" type="button" @click="undoDelete(row)">Undo</button>
                  <template v-else>
                    <button type="button" :disabled="!canOpen(row)" @click="openEditor(row)">Edit</button>
                    <button type="button" :disabled="row.protected" @click="removeTransaction(row)">Delete</button>
                  </template>
                </span>

                <span v-if="displayMode === 'detailed'" class="detail-line">
                  <span v-if="row.paymentMethodName"><strong>Payment:</strong> {{ row.paymentMethodName }}</span>
                  <span v-if="row.isTransfer && row.transferPaymentMethodName"><strong>Counterpart:</strong> {{ row.transferPaymentMethodName }}</span>
                  <span v-if="row.note" class="detail-note"><strong>Note:</strong> {{ row.note }}</span>
                  <span v-if="row.bankReference"><strong>Bank ref:</strong> {{ row.bankReference }}</span>
                </span>
              </div>
            </DynamicScrollerItem>
          </template>
        </DynamicScroller>

        <div v-if="!displayedRows.length" class="empty-state">
          No transactions match this bank-status filter.
        </div>
      </section>

      <button
        type="button"
        class="mobile-add"
        :disabled="saving || conflict"
        aria-label="Add transaction"
        @click="addTransaction"
      >
        +
      </button>

      <TransactionEditorPanel
        v-if="editorDraft"
        :draft="editorDraft"
        :snapshot="snapshot"
        :recent-selections="recentSelections"
        :auto-focus-party="editorDraft.isNew"
        @apply="applyActiveDraft(false)"
        @apply-add="applyActiveDraft(true)"
        @cancel="cancelActiveEditor"
        @recent="rememberSelection"
      />
    </main>
  </NcAppContent>
</template>

<script setup>
import { NcAppContent, NcLoadingIcon } from '@nextcloud/vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import TransactionEditorPanel from '@/components/transactions/TransactionEditorPanel.vue'
import {
  TRANSFER_CATEGORY,
  applyEditorDraft,
  buildResponsiveMutationOperations,
  calculateTotals,
  cloneEditorDraft,
  createResponsiveDrafts,
  editorDraftChanged,
  hasResponsivePendingChanges,
  newResponsiveDraft,
  normalizeName,
  pendingChangeSummary,
  preferredDisplayMode,
  sameResponsiveValues,
} from '@/domain/responsiveEditor.mjs'
import { allowReconciledMutations } from '@/domain/transactionEditor.mjs'
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
const displayMode = ref('compact')
const markFilter = ref('all')
const editorDraft = ref(null)
const editorBaseline = ref(null)
const editorRowKey = ref(null)
const recentSelections = reactive({
  party: [], category: [], subcategory: [], payment: [],
  transferAccount: [], transferPayment: [],
})
let newSequence = 0
let revertingRoute = false

const filteredRows = computed(() => rows.value.filter(row => {
  if (markFilter.value === 'unchecked') return Number(row.marked) === 0
  if (markFilter.value === 'checked') return Number(row.marked) === 1
  if (markFilter.value === 'locked') return [2, 3].includes(Number(row.marked))
  return true
}))
const displayedRows = computed(() => [...filteredRows.value].reverse())
const pendingChanges = computed(() => hasResponsivePendingChanges(rows.value)
  || editorDraftChanged(editorDraft.value, editorBaseline.value))
const pendingSummary = computed(() => {
  const prospective = rowsWithActiveDraft()
  return pendingChangeSummary(prospective)
})
const totals = computed(() => calculateTotals(
  rowsWithActiveDraft(),
  snapshot.value?.account?.currency?.precision ?? 2,
))

function setMessage(text, type = 'info') {
  message.value = text
  messageType.value = type
}

function clone(value) {
  if (typeof structuredClone === 'function') return structuredClone(value)
  return JSON.parse(JSON.stringify(value))
}

function rowsWithActiveDraft() {
  if (!editorDraft.value || !editorRowKey.value) return rows.value
  return rows.value.map(row => row.key === editorRowKey.value ? clone(editorDraft.value) : row)
}

async function loadSnapshot() {
  loading.value = true
  conflict.value = false
  closeEditorState()
  try {
    const response = await fetchEditorSnapshot({
      accountId: selectedAccountId.value,
      filePath: store.state.filePath,
      filePassword: store.state.filePassword,
    })
    snapshot.value = response.snapshot
    etag.value = response.document.etag
    rows.value = createResponsiveDrafts(response.snapshot)
    displayMode.value = preferredDisplayMode(response.snapshot.preferences)
    markFilter.value = 'all'
    if (response.snapshot.warnings?.length) {
      setMessage(
        `Opened with ${response.snapshot.warnings.length} Grisbi compatibility warning(s). Affected rows remain visible and read-only.`,
        'warning',
      )
    } else {
      setMessage('')
    }
  } catch (error) {
    const failure = apiError(error)
    setMessage(failure.message, 'error')
  } finally {
    loading.value = false
  }
}

function today() {
  const value = new Date()
  return `${String(value.getMonth() + 1).padStart(2, '0')}/${String(value.getDate()).padStart(2, '0')}/${value.getFullYear()}`
}

function canOpen(row) {
  return !row.deleted && !row.protected
}

function addTransaction() {
  if (!requestCloseEditor()) return
  newSequence += 1
  const row = newResponsiveDraft(snapshot.value, `new-${newSequence}`, today())
  rows.value.push(row)
  openEditor(row)
}

function openEditor(row) {
  if (!canOpen(row)) return
  if (editorRowKey.value === row.key) return
  if (!requestCloseEditor()) return
  editorRowKey.value = row.key
  editorDraft.value = cloneEditorDraft(row)
  editorBaseline.value = clone(editorDraft.value)
}

function closeEditorState() {
  editorDraft.value = null
  editorBaseline.value = null
  editorRowKey.value = null
}

function requestCloseEditor() {
  if (!editorDraft.value) return true
  if (editorDraftChanged(editorDraft.value, editorBaseline.value)
    && !window.confirm('Discard changes made in the open transaction editor?')) {
    return false
  }
  const row = rows.value.find(item => item.key === editorRowKey.value)
  if (row?.isNew && !row.locallyApplied) rows.value = rows.value.filter(item => item.key !== row.key)
  closeEditorState()
  return true
}

function cancelActiveEditor() {
  requestCloseEditor()
}

function applyActiveDraft(addAnother) {
  const target = rows.value.find(item => item.key === editorRowKey.value)
  if (!target || !editorDraft.value) return
  applyEditorDraft(target, editorDraft.value)
  closeEditorState()
  if (addAnother) addTransaction()
}

function rememberSelection({ kind, id }) {
  if (!recentSelections[kind]) return
  recentSelections[kind] = [String(id), ...recentSelections[kind].filter(item => item !== String(id))].slice(0, 8)
}

function removeTransaction(row) {
  if (editorRowKey.value === row.key && !requestCloseEditor()) return
  if (row.isNew) rows.value = rows.value.filter(item => item.key !== row.key)
  else row.deleted = true
}

function undoDelete(row) {
  row.deleted = false
}

function quickMarkChanged(row, event) {
  row.marked = event.target.checked ? 1 : 0
}

function markTitle(row) {
  if (row.isNew || row.quickMarkable) return 'Check or uncheck now; the file is written only when Save all is pressed.'
  if (Number(row.marked) === 2) return 'Telepointed transaction: use a reconciliation workflow to change this state.'
  return 'Reconciled transaction: this state is locked here.'
}

function categoryLabel(row) {
  if (normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)) return 'Transfer'
  return row.categoryName || 'Uncategorized'
}

function shortDate(value) {
  const parts = String(value ?? '').split('/')
  if (parts.length !== 3) return value || '—'
  return `${parts[1]}/${parts[0]}/${parts[2]}`
}

function formatAmount(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return value
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: snapshot.value.account.currency.precision,
    maximumFractionDigits: snapshot.value.account.currency.precision,
  }).format(number)
}

function statusLabel(row) {
  if (row.deleted) return 'Delete pending'
  if (row.protected) return 'Read only'
  if (row.isNew) return row.locallyApplied ? 'New pending' : 'New'
  if (!sameResponsiveValues(row)) return 'Changed'
  if (row.isTransfer) return 'Transfer'
  return 'Saved'
}

function statusTitle(row) {
  if (row.protected) return `Read-only Grisbi structure: ${row.protectionReasons.join(', ')}`
  if (row.isNew || !sameResponsiveValues(row) || row.deleted) return 'This change has not been written to the GSB file yet.'
  return row.isTransfer ? 'Reciprocal account transfer' : 'Saved transaction'
}

function rowClasses(row) {
  return {
    deleted: row.deleted,
    protected: row.protected,
    pending: row.isNew || row.deleted || (!row.isNew && !sameResponsiveValues(row)),
    transfer: row.isTransfer,
  }
}

async function submitOperations(operations, confirmed = false) {
  try {
    const response = await mutateDocument({
      filePath: store.state.filePath,
      filePassword: store.state.filePassword,
      baseEtag: etag.value,
      operations,
    })
    etag.value = response.document.etag
    setMessage('All pending transactions were saved in one file write.', 'success')
    await loadSnapshot()
    return true
  } catch (error) {
    const failure = apiError(error)
    if (failure.code === 'confirmation-required' && !confirmed) {
      const ids = failure.details?.transactionIds ?? []
      const suffix = ids.length ? ` Transactions: ${ids.join(', ')}.` : ''
      if (window.confirm(`This change affects reconciled transfer data.${suffix} Continue?`)) {
        return submitOperations(allowReconciledMutations(operations), true)
      }
      setMessage('The reconciled transfer was not changed.', 'warning')
      return false
    }
    conflict.value = failure.code === 'etag-conflict'
    setMessage(
      conflict.value
        ? 'The GSB file changed elsewhere. All local drafts are preserved; reload before saving again.'
        : failure.message,
      'error',
    )
    return false
  }
}

async function saveChanges() {
  const prospectiveRows = rowsWithActiveDraft()
  let operations
  try {
    operations = buildResponsiveMutationOperations(prospectiveRows, snapshot.value)
  } catch (error) {
    setMessage(error.message, 'error')
    return
  }
  if (!operations.length) {
    setMessage('There are no validated pending changes to save.')
    return
  }

  if (editorDraft.value) {
    const target = rows.value.find(item => item.key === editorRowKey.value)
    if (target) applyEditorDraft(target, editorDraft.value)
    closeEditorState()
  }

  saving.value = true
  try {
    await submitOperations(operations)
  } finally {
    saving.value = false
  }
}

async function reloadSnapshot() {
  if (pendingChanges.value && !window.confirm('Discard every pending new, edited, deleted and marked transaction?')) return
  await loadSnapshot()
}

async function reloadAfterConflict() {
  if (!window.confirm('Reload the current file and discard all local drafts?')) return
  await loadSnapshot()
}

onMounted(loadSnapshot)
watch(() => route.params.id, async newId => {
  if (revertingRoute) {
    revertingRoute = false
    return
  }
  if (pendingChanges.value && !window.confirm('Discard all pending transactions and switch accounts?')) {
    revertingRoute = true
    await router.replace({ name: 'Account', params: { id: selectedAccountId.value } })
    return
  }
  selectedAccountId.value = String(newId)
  await loadSnapshot()
})
</script>

<style scoped>
.workspace { min-width: 0; height: 100%; display: grid; grid-template-rows: auto auto auto auto minmax(0, 1fr); padding: 14px 16px 16px; box-sizing: border-box; }
.loading { display: flex; gap: 12px; align-items: center; justify-content: center; min-height: 240px; }
.account-header { position: sticky; z-index: 20; top: 0; display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 8px 0 12px; background: var(--color-main-background); }
.account-title { min-width: 0; }
.account-title h1 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 1.45rem; }
.account-title span { opacity: .65; }
.totals { display: grid; text-align: end; white-space: nowrap; }
.totals strong { font-size: 1.2rem; }
.message { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; padding: 10px 12px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); }
.message.error { border-color: var(--color-error); }
.message.warning { border-color: var(--color-warning); }
.message.success { border-color: var(--color-success); }
.toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 10px; }
.toolbar-group { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; }
.toolbar button, .toolbar select { min-height: 36px; }
.primary-button, .save-button { font-weight: 600; }
.save-button { background: var(--color-primary-element); color: var(--color-primary-element-text); border-color: transparent; }
.toolbar-label { font-weight: 600; }
.segmented { display: inline-flex; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); overflow: hidden; }
.segmented button { border: 0; border-radius: 0; }
.segmented button.active { background: var(--color-primary-element); color: var(--color-primary-element-text); }
.filter-control { display: flex; align-items: center; gap: 6px; }
.pending-banner { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; margin-bottom: 10px; padding: 8px 12px; border-radius: var(--border-radius-large); background: var(--color-primary-light); }
.pending-banner small { flex-basis: 100%; opacity: .72; }
.transaction-list { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); border: 1px solid var(--color-border); border-radius: var(--border-radius-large); overflow: hidden; }
.transaction-header, .row-content { display: grid; grid-template-columns: 100px minmax(150px, 1.35fr) minmax(150px, 1.2fr) 120px 72px 110px 130px; column-gap: 10px; align-items: center; }
.transaction-header { padding: 9px 12px; font-weight: 600; background: var(--color-background-dark); border-bottom: 1px solid var(--color-border); }
.amount-column, .amount-cell { text-align: end; }
.mark-column, .mark-cell { text-align: center; }
.scroller { min-height: 0; height: 100%; }
.transaction-row { border-bottom: 1px solid var(--color-border); background: var(--color-main-background); }
.transaction-row:nth-child(even) { background: var(--color-background-darker); }
.transaction-row.pending { box-shadow: inset 4px 0 0 var(--color-primary-element); }
.transaction-row.protected { background: var(--color-background-dark); }
.transaction-row.deleted { opacity: .58; text-decoration: line-through; }
.row-content { min-height: 58px; padding: 7px 12px; box-sizing: border-box; cursor: default; }
.row-content[role='button'] { cursor: pointer; }
.row-content[role='button']:hover, .row-content[role='button']:focus { background: var(--color-background-hover); outline: none; }
.party-cell, .category-cell, .detail-note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.category-cell { display: grid; }
.category-cell small { opacity: .7; }
.amount-cell { font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }
.amount-cell.credit { color: var(--color-success); }
.amount-cell.debit { color: var(--color-text-maxcontrast); }
.mark-cell input { width: 22px; height: 22px; cursor: pointer; }
.state-icon { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; font-size: .78rem; font-weight: 700; }
.telepointed { background: var(--color-warning); color: #000; }
.reconciled { background: var(--color-success); color: #fff; }
.status-cell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .86rem; }
.actions-cell { display: flex; gap: 5px; justify-content: flex-end; }
.actions-cell button { min-height: 32px; padding: 4px 8px; }
.detail-line { grid-column: 2 / -1; display: flex; gap: 8px 18px; min-width: 0; padding-top: 6px; opacity: .78; font-size: .9rem; }
.mode-detailed .row-content { min-height: 88px; align-content: center; }
.empty-state { padding: 28px; text-align: center; opacity: .7; }
.mobile-add { display: none; }
@media (max-width: 900px) {
  .workspace { padding: 10px; grid-template-rows: auto auto auto auto minmax(0, 1fr); }
  .account-header { gap: 10px; }
  .account-title h1 { font-size: 1.2rem; }
  .totals { font-size: .9rem; }
  .toolbar { align-items: stretch; }
  .primary-actions { width: 100%; }
  .primary-actions button { flex: 1; }
  .view-actions { width: 100%; justify-content: space-between; }
  .transaction-header { display: none; }
  .transaction-list { grid-template-rows: minmax(0, 1fr); border-inline: 0; border-radius: 0; }
  .row-content { grid-template-columns: 68px minmax(0, 1fr) 95px 42px 82px; grid-template-areas:
    'date party amount mark status'
    'category category category actions actions'
    'detail detail detail detail detail';
    gap: 4px 8px; min-height: 68px; padding: 9px 8px; }
  .date-cell { grid-area: date; font-size: .88rem; }
  .party-cell { grid-area: party; font-weight: 600; }
  .category-cell { grid-area: category; display: flex; gap: 5px; font-size: .88rem; }
  .category-cell small::before { content: '› '; }
  .amount-cell { grid-area: amount; }
  .mark-cell { grid-area: mark; }
  .status-cell { grid-area: status; text-align: end; font-size: .76rem; }
  .actions-cell { grid-area: actions; }
  .actions-cell button { min-height: 30px; }
  .detail-line { grid-area: detail; padding-top: 4px; overflow: hidden; white-space: nowrap; }
  .mode-compact .category-cell, .mode-compact .actions-cell { display: none; }
  .mode-compact .row-content { grid-template-areas: 'date party amount mark status'; min-height: 58px; }
  .mode-detailed .row-content { min-height: 94px; }
  .mobile-add { position: fixed; z-index: 40; display: grid; place-items: center; inset-inline-end: 18px; bottom: 18px; width: 56px; height: 56px; border: 0; border-radius: 50%; background: var(--color-primary-element); color: var(--color-primary-element-text); box-shadow: 0 5px 18px rgb(0 0 0 / 28%); font-size: 30px; }
}
@media (max-width: 540px) {
  .account-header { align-items: flex-start; }
  .totals strong { font-size: 1rem; }
  .message { align-items: flex-start; }
  .view-actions { align-items: flex-end; }
  .filter-control { display: grid; gap: 2px; }
  .pending-banner small { display: none; }
  .primary-actions button:nth-child(3) { flex-basis: 100%; }
}
</style>
