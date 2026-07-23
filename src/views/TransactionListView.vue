<template>
  <NcAppContent>
    <div v-if="loading" class="loading">
      <NcLoadingIcon :size="32" />
      <p>Loading transactions…</p>
    </div>

    <main v-else-if="snapshot" class="workspace">
      <header class="account-header">
        <div class="account-primary">
          <h1>{{ snapshot.account.name }}</h1>
          <span>{{ displayedRows.length }} transactions</span>
        </div>

        <div class="account-secondary">
          <div class="totals" aria-label="Account totals">
            <strong>{{ totals.totalAmount }} {{ snapshot.account.currency.code }}</strong>
            <span>Checked: {{ totals.totalMarkedAmount }} {{ snapshot.account.currency.code }}</span>
            <span
              v-if="pendingSummary.total"
              class="pending-count"
              :title="pendingDescription"
            >
              {{ pendingSummary.total }} pending
            </span>

            <NcPopover
              v-if="compatibilityWarnings.length"
              popup-role="dialog"
              popover-base-class="ncgrisbi-compatibility-popover"
            >
              <template #trigger="{ attrs }">
                <button
                  v-bind="attrs"
                  type="button"
                  class="compatibility-warning"
                  :aria-label="`Show ${compatibilityWarnings.length} compatibility warnings`"
                >
                  {{ compatibilityWarnings.length }} read-only
                </button>
              </template>
              <div
                class="compatibility-popover"
                role="dialog"
                aria-labelledby="compatibility-popover-title"
              >
                <h2 id="compatibility-popover-title">Compatibility warnings</h2>
                <p>
                  These transactions use Grisbi structures that are not safely editable here.
                  Other transactions remain fully editable.
                </p>
                <ul>
                  <li v-for="warning in compatibilityWarnings" :key="warning.key">
                    <strong v-if="warning.transactionId">Transaction {{ warning.transactionId }}:</strong>
                    {{ warning.message }}
                  </li>
                </ul>
              </div>
            </NcPopover>
          </div>

          <div v-if="message" class="header-message" :class="messageType" role="status">
            <span>{{ message }}</span>
            <button v-if="conflict" type="button" @click="reloadAfterConflict">
              Reload & discard drafts
            </button>
          </div>
        </div>

        <div class="header-controls" aria-label="Transaction view and actions">
          <button
            type="button"
            class="display-toggle"
            :aria-label="displayMode === 'compact' ? 'Switch to detailed rows' : 'Switch to compact rows'"
            :aria-pressed="displayMode === 'detailed'"
            @click="toggleDisplayMode"
          >
            <span :class="{ active: displayMode === 'compact' }">Compact</span>
            <span :class="{ active: displayMode === 'detailed' }">Details</span>
          </button>

          <label class="compact-control bank-filter">
            <span>Bank status</span>
            <select v-model="markFilter" aria-label="Bank status filter">
              <option value="all">All statuses</option>
              <option value="unchecked">Unchecked</option>
              <option value="checked">Checked</option>
              <option value="locked">Telepointed / reconciled</option>
            </select>
          </label>

          <details class="action-menu">
            <summary aria-label="Transaction actions" title="Transaction actions">+</summary>
            <div class="action-popover">
              <button type="button" :disabled="saving || conflict" @click="runAction('add', $event)">
                Add transaction
              </button>
              <button type="button" @click="runAction('search', $event)">
                Search transactions
              </button>
              <button
                type="button"
                :disabled="saving || conflict || !pendingChanges"
                @click="runAction('save', $event)"
              >
                {{ saving ? 'Saving…' : `Save all${pendingSummary.total ? ` (${pendingSummary.total})` : ''}` }}
              </button>
              <button
                type="button"
                :disabled="saving || !pendingChanges"
                @click="runAction('discard', $event)"
              >
                Discard pending
              </button>
            </div>
          </details>

          <form
            v-if="searchOpen"
            class="search-popover"
            role="search"
            @submit.prevent
            @keydown.esc.prevent="closeSearch"
          >
            <svg class="search-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9.5 3a6.5 6.5 0 1 0 3.98 11.64L19.85 21 21 19.85l-6.36-6.37A6.5 6.5 0 0 0 9.5 3Zm0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Z" />
            </svg>
            <input
              ref="searchInput"
              v-model="searchQuery"
              type="search"
              autocomplete="off"
              placeholder="Search party, note or reference"
              aria-label="Search party, note or reference"
            >
            <button
              type="button"
              class="search-close"
              aria-label="Close and clear search"
              title="Close and clear search"
              @click="closeSearch"
            >
              ×
            </button>
          </form>
        </div>
      </header>

      <section
        ref="transactionList"
        class="transaction-list"
        :class="`mode-${displayMode}`"
        aria-label="Transactions"
      >
        <div class="transaction-header" aria-hidden="true">
          <span>Date</span>
          <span>Party</span>
          <span>Category</span>
          <span class="amount-column">Amount</span>
          <span class="mark-column">Marked</span>
          <span>Status</span>
          <span>Actions</span>
        </div>

        <DynamicScroller
          ref="scroller"
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
                :data-row-key="row.key"
                :tabindex="row.key === selectedRowKey ? 0 : -1"
                :role="canOpen(row) ? 'button' : undefined"
                :aria-selected="row.key === selectedRowKey"
                :aria-invalid="row.key === validationErrorKey ? 'true' : undefined"
                @click="handleRowClick(row)"
                @focus="selectRow(row)"
                @keydown="handleRowKeydown($event, row)"
              >
                <span class="date-cell">
                  <span class="date-desktop">{{ shortDate(row.date) }}</span>
                  <span class="date-mobile">{{ mobileDate(row.date) }}</span>
                </span>
                <span class="party-cell" :title="row.partyName || 'No party'">
                  {{ row.partyName || 'No party' }}
                </span>
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
                    @focus="selectRow(row)"
                    @change="quickMarkChanged(row, $event)"
                  >
                  <span v-else-if="Number(row.marked) === 2" class="state-icon telepointed" title="Telepointed">T</span>
                  <span v-else class="state-icon reconciled" title="Reconciled">R</span>
                </span>
                <span class="status-cell" :title="statusTitle(row)">{{ statusLabel(row) }}</span>
                <span class="actions-cell" @click.stop @keydown.stop>
                  <button v-if="row.deleted" type="button" @click="undoDelete(row)">Undo</button>
                  <template v-else>
                    <button
                      type="button"
                      class="row-action-button"
                      :disabled="!canOpen(row)"
                      :aria-label="`Edit transaction ${row.transactionId || 'new'}`"
                      title="Edit"
                      @click="openEditor(row)"
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Zm17.71-10.04a1 1 0 0 0 0-1.42l-2.5-2.5a1 1 0 0 0-1.42 0l-1.96 1.96 3.75 3.75 2.13-1.79Z" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="row-action-button delete-action"
                      :disabled="row.protected"
                      :aria-label="`Delete transaction ${row.transactionId || 'new'}`"
                      title="Delete"
                      @click="removeTransaction(row)"
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12Zm3.46-8.12 1.41-1.41L12 10.59l1.12-1.12 1.41 1.41L13.41 12l1.12 1.12-1.41 1.41L12 13.41l-1.12 1.12-1.41-1.41L10.59 12l-1.13-1.12ZM15.5 4l-1-1h-5l-1 1H5v2h14V4h-3.5Z" />
                      </svg>
                    </button>
                  </template>
                </span>

                <span v-if="displayMode === 'detailed'" class="detail-line">
                  <span v-if="row.note" class="detail-note"><strong>Note:</strong> {{ row.note }}</span>
                  <span v-if="row.paymentMethodName"><strong>Payment:</strong> {{ row.paymentMethodName }}</span>
                  <span v-if="row.isTransfer && row.transferPaymentMethodName"><strong>Counterpart:</strong> {{ row.transferPaymentMethodName }}</span>
                  <span v-if="row.paymentReference"><strong>Payment ref:</strong> {{ row.paymentReference }}</span>
                  <span v-if="row.bankReference"><strong>Bank ref:</strong> {{ row.bankReference }}</span>
                </span>
              </div>
            </DynamicScrollerItem>
          </template>
        </DynamicScroller>

        <div v-if="!displayedRows.length" class="empty-state">
          {{ emptyMessage }}
        </div>
      </section>

      <TransactionEditorPanel
        v-if="editorDraft"
        v-model:draft="editorDraft"
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
import { NcAppContent, NcLoadingIcon, NcPopover } from '@nextcloud/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import TransactionEditorPanel from '@/components/transactions/TransactionEditorPanel.vue'
import { sortTransactionsRecentFirst } from '@/domain/transactionOrdering.mjs'
import { matchesTransactionSearch } from '@/domain/transactionSearch.mjs'
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
const searchOpen = ref(false)
const searchQuery = ref('')
const searchInput = ref(null)
const scroller = ref(null)
const transactionList = ref(null)
const selectedRowKey = ref(null)
const validationErrorKey = ref(null)
const validationErrorMessage = ref('')
const editorDraft = ref(null)
const editorBaseline = ref(null)
const editorRowKey = ref(null)
const recentSelections = reactive({
  party: [], category: [], subcategory: [], payment: [],
  transferAccount: [], transferPayment: [],
})
let newSequence = 0
let revertingRoute = false

const orderedRows = computed(() => sortTransactionsRecentFirst(rows.value))
const displayedRows = computed(() => orderedRows.value.filter(row => {
  if (markFilter.value === 'unchecked' && Number(row.marked) !== 0) return false
  if (markFilter.value === 'checked' && Number(row.marked) !== 1) return false
  if (markFilter.value === 'locked' && ![2, 3].includes(Number(row.marked))) return false
  return matchesTransactionSearch(row, searchQuery.value)
}))
const pendingChanges = computed(() => hasResponsivePendingChanges(rows.value)
  || editorDraftChanged(editorDraft.value, editorBaseline.value))
const pendingSummary = computed(() => pendingChangeSummary(rowsWithActiveDraft()))
const pendingDescription = computed(() => [
  pendingSummary.value.created ? `${pendingSummary.value.created} new` : '',
  pendingSummary.value.edited ? `${pendingSummary.value.edited} edited` : '',
  pendingSummary.value.marked ? `${pendingSummary.value.marked} checked/unchecked` : '',
  pendingSummary.value.deleted ? `${pendingSummary.value.deleted} deleted` : '',
].filter(Boolean).join(', '))
const totals = computed(() => calculateTotals(
  rowsWithActiveDraft(),
  snapshot.value?.account?.currency?.precision ?? 2,
))
const emptyMessage = computed(() => searchQuery.value.trim()
  ? 'No transactions match this search and bank-status filter.'
  : 'No transactions match this bank-status filter.')
const compatibilityWarnings = computed(() => (snapshot.value?.warnings ?? []).map((warning, index) => ({
  key: `${warning?.transactionId ?? warning?.id ?? 'warning'}-${index}`,
  transactionId: warning?.transactionId ?? warning?.id ?? '',
  message: typeof warning === 'string'
    ? warning
    : warning?.message ?? warning?.code ?? 'Unsupported Grisbi structure.',
})))

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

function syncSharedPendingState() {
  store.commit('setTransactionPending', {
    active: pendingChanges.value,
    total: pendingSummary.value.total,
    description: pendingDescription.value || (pendingChanges.value ? 'open transaction editor changes' : ''),
  })
}

async function loadSnapshot() {
  loading.value = true
  conflict.value = false
  validationErrorKey.value = null
  validationErrorMessage.value = ''
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
    searchQuery.value = ''
    searchOpen.value = false
    selectedRowKey.value = null
    setMessage('')
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

function clearValidationFor(row) {
  if (validationErrorKey.value !== row?.key) return
  validationErrorKey.value = null
  validationErrorMessage.value = ''
}

function addTransaction() {
  if (!requestCloseEditor()) return
  newSequence += 1
  const row = newResponsiveDraft(snapshot.value, `new-${newSequence}`, today())
  rows.value.push(row)
  selectedRowKey.value = row.key
  openEditor(row)
}

function openEditor(row) {
  if (!canOpen(row)) return
  if (editorRowKey.value === row.key) return
  if (!requestCloseEditor()) return
  clearValidationFor(row)
  selectedRowKey.value = row.key
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

async function cancelActiveEditor() {
  const key = editorRowKey.value
  if (!requestCloseEditor()) return
  if (key) await focusRow(key)
}

async function applyActiveDraft(addAnother) {
  const key = editorRowKey.value
  const target = rows.value.find(item => item.key === key)
  if (!target || !editorDraft.value) return
  applyEditorDraft(target, editorDraft.value)
  clearValidationFor(target)
  closeEditorState()
  if (addAnother) addTransaction()
  else if (key) await focusRow(key)
}

function rememberSelection({ kind, id }) {
  if (!recentSelections[kind]) return
  recentSelections[kind] = [String(id), ...recentSelections[kind].filter(item => item !== String(id))].slice(0, 8)
}

function removeTransaction(row) {
  selectRow(row)
  clearValidationFor(row)
  if (editorRowKey.value === row.key && !requestCloseEditor()) return
  if (row.isNew) rows.value = rows.value.filter(item => item.key !== row.key)
  else row.deleted = true
}

function undoDelete(row) {
  row.deleted = false
  selectRow(row)
}

function quickMarkChanged(row, event) {
  row.marked = event.target.checked ? 1 : 0
  selectRow(row)
  clearValidationFor(row)
}

function toggleRowMarked(row) {
  if (saving.value || conflict.value || row.deleted) return
  if (!(row.isNew || row.quickMarkable) || ![0, 1].includes(Number(row.marked))) {
    setMessage(markTitle(row), 'warning')
    return
  }
  row.marked = Number(row.marked) === 1 ? 0 : 1
  clearValidationFor(row)
}

function markTitle(row) {
  if (row.isNew || row.quickMarkable) return 'Check or uncheck now; the file is written only when Save all is pressed.'
  if (Number(row.marked) === 2) return 'Telepointed transaction: use a reconciliation workflow to change this state.'
  return 'Reconciled transaction: this state is locked here.'
}

function categoryLabel(row) {
  if (row.isTransfer || normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY)) return 'Transfer'
  return row.categoryName || 'Uncategorized'
}

function dateParts(value) {
  const parts = String(value ?? '').split('/')
  return parts.length === 3 ? parts : null
}

function shortDate(value) {
  const parts = dateParts(value)
  if (!parts) return value || '—'
  return `${parts[1]}/${parts[0]}/${parts[2]}`
}

function mobileDate(value) {
  const parts = dateParts(value)
  if (!parts) return value || '—'
  return `${Number(parts[1])}/${Number(parts[0])}/${String(parts[2]).slice(-2)}`
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
  if (row.isNew) return 'Pending'
  if (!sameResponsiveValues(row)) return 'Changed'
  return 'Saved'
}

function statusTitle(row) {
  if (row.protected) return `Read-only Grisbi structure: ${row.protectionReasons.join(', ')}`
  if (row.key === validationErrorKey.value) return validationErrorMessage.value
  if (row.isNew || !sameResponsiveValues(row) || row.deleted) return 'This change has not been written to the GSB file yet.'
  return 'Saved transaction'
}

function rowClasses(row) {
  return {
    deleted: row.deleted,
    protected: row.protected,
    pending: row.isNew || row.deleted || (!row.isNew && !sameResponsiveValues(row)),
    selected: row.key === selectedRowKey.value,
    'validation-error': row.key === validationErrorKey.value,
    transfer: row.isTransfer,
  }
}

function toggleDisplayMode() {
  displayMode.value = displayMode.value === 'compact' ? 'detailed' : 'compact'
}

function closeActionMenu(event) {
  event.currentTarget.closest('details')?.removeAttribute('open')
}

async function openSearch() {
  searchOpen.value = true
  await nextTick()
  searchInput.value?.focus()
  searchInput.value?.select()
}

function closeSearch() {
  searchQuery.value = ''
  searchOpen.value = false
}

function runAction(action, event) {
  closeActionMenu(event)
  if (action === 'add') addTransaction()
  else if (action === 'search') openSearch()
  else if (action === 'save') saveChanges()
  else if (action === 'discard') reloadSnapshot()
}

function selectRow(row) {
  selectedRowKey.value = row.key
}

function rowElement(key) {
  return [...(transactionList.value?.querySelectorAll('[data-row-key]') ?? [])]
    .find(element => element.dataset.rowKey === String(key))
}

async function focusRow(key) {
  selectedRowKey.value = key
  await nextTick()
  const index = displayedRows.value.findIndex(row => row.key === key)
  if (index < 0) return
  scroller.value?.scrollToItem?.(index)
  await nextTick()
  rowElement(key)?.focus()
}

async function moveSelection(offset) {
  if (!displayedRows.value.length) return
  const current = displayedRows.value.findIndex(row => row.key === selectedRowKey.value)
  const initial = current < 0 ? 0 : current
  const target = Math.min(displayedRows.value.length - 1, Math.max(0, initial + offset))
  await focusRow(displayedRows.value[target].key)
}

async function moveSelectionTo(edge) {
  if (!displayedRows.value.length) return
  const index = edge === 'start' ? 0 : displayedRows.value.length - 1
  await focusRow(displayedRows.value[index].key)
}

function handleRowClick(row) {
  selectRow(row)
  if (canOpen(row)) openEditor(row)
}

function handleRowKeydown(event, row) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    moveSelection(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    moveSelection(-1)
  } else if (event.key === 'Home') {
    event.preventDefault()
    moveSelectionTo('start')
  } else if (event.key === 'End') {
    event.preventDefault()
    moveSelectionTo('end')
  } else if (event.key === 'Enter') {
    event.preventDefault()
    if (canOpen(row)) openEditor(row)
  } else if (event.key === ' ' || event.code === 'Space') {
    event.preventDefault()
    toggleRowMarked(row)
  }
}

function discardPrompt(context) {
  const count = pendingSummary.value.total
  const details = pendingDescription.value || 'open editor changes'
  return `${context} This will permanently discard ${count} local pending change${count === 1 ? '' : 's'} (${details}). This cannot be undone.`
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
    validationErrorKey.value = null
    validationErrorMessage.value = ''
    await loadSnapshot()
    setMessage('All pending transactions were saved in one file write.', 'success')
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
        ? `The GSB file changed elsewhere. ${pendingSummary.value.total} local draft change${pendingSummary.value.total === 1 ? '' : 's'} remain preserved in this browser.`
        : failure.message,
      'error',
    )
    return false
  }
}

async function revealValidationError(error) {
  validationErrorKey.value = error.rowKey ?? null
  validationErrorMessage.value = error.message
  setMessage(error.rowKey ? `Transaction validation failed: ${error.message}` : error.message, 'error')
  if (!error.rowKey) return
  markFilter.value = 'all'
  searchQuery.value = ''
  searchOpen.value = false
  await nextTick()
  await focusRow(error.rowKey)
}

async function saveChanges() {
  const prospectiveRows = rowsWithActiveDraft()
  let operations
  try {
    operations = buildResponsiveMutationOperations(prospectiveRows, snapshot.value)
  } catch (error) {
    await revealValidationError(error)
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
  if (pendingChanges.value && !window.confirm(discardPrompt('Reload the GSB file from disk?'))) return
  await loadSnapshot()
}

async function reloadAfterConflict() {
  if (!window.confirm(discardPrompt('Reload the latest GSB file after the ETag conflict?'))) return
  await loadSnapshot()
}

function handleGlobalKeydown(event) {
  if (event.key !== 'Escape' || !editorDraft.value) return
  event.preventDefault()
  cancelActiveEditor()
}

function handleBeforeUnload(event) {
  if (!store.state.transactionPending.active) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
  window.addEventListener('beforeunload', handleBeforeUnload)
  loadSnapshot()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  store.commit('setTransactionPending', { active: false, total: 0, description: '' })
})

onBeforeRouteLeave(() => {
  if (!store.state.transactionPending.active) return true
  if (!window.confirm(discardPrompt('Leave this transaction view?'))) return false
  store.commit('setTransactionPending', { active: false, total: 0, description: '' })
  return true
})

watch(
  () => [pendingChanges.value, pendingSummary.value.total, pendingDescription.value],
  syncSharedPendingState,
  { immediate: true },
)

watch(displayedRows, currentRows => {
  if (!currentRows.length) {
    selectedRowKey.value = null
    return
  }
  if (!currentRows.some(row => row.key === selectedRowKey.value)) {
    selectedRowKey.value = currentRows[0].key
  }
})

watch(() => route.params.id, async newId => {
  if (revertingRoute) {
    revertingRoute = false
    return
  }
  if (pendingChanges.value && !window.confirm(discardPrompt(`Switch to account ${String(newId)}?`))) {
    revertingRoute = true
    await router.replace({ name: 'Account', params: { id: selectedAccountId.value } })
    return
  }
  selectedAccountId.value = String(newId)
  await loadSnapshot()
})
</script>

<style scoped>
.workspace { position: relative; min-width: 0; height: 100%; display: grid; grid-template-rows: auto minmax(0, 1fr); padding: 8px 12px 12px; box-sizing: border-box; }
.loading { display: flex; gap: 12px; align-items: center; justify-content: center; min-height: 240px; }
.account-header { position: sticky; z-index: 20; top: 0; display: grid; grid-template-rows: auto auto auto; gap: 3px; padding: 3px 0 7px; background: var(--color-main-background); }
.account-primary { display: flex; align-items: baseline; gap: 10px; min-width: 0; padding-inline: 33px; }
.account-primary h1 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 1.3rem; line-height: 1.25; }
.account-primary > span { flex: none; opacity: .65; font-size: .86rem; white-space: nowrap; }
.account-secondary { display: flex; align-items: center; gap: 10px; min-width: 0; min-height: 27px; padding-inline: 33px; }
.totals { display: flex; align-items: center; gap: 8px; white-space: nowrap; font-size: .9rem; }
.totals strong { font-size: 1rem; }
.pending-count, .compatibility-warning { padding: 2px 7px; border: 0; border-radius: 999px; font-weight: 600; }
.pending-count { background: var(--color-primary-light); color: var(--color-primary-text); }
.compatibility-warning { min-height: 25px; background: var(--color-warning); color: #000; cursor: pointer; }
.compatibility-popover { display: grid; gap: 10px; width: min(420px, calc(100vw - 32px)); max-height: min(440px, 70vh); overflow-y: auto; padding: 14px; box-sizing: border-box; }
.compatibility-popover h2, .compatibility-popover p, .compatibility-popover ul { margin: 0; }
.compatibility-popover ul { display: grid; gap: 8px; padding-inline-start: 20px; }
.header-message { display: flex; flex: 1; align-items: center; justify-content: flex-end; gap: 6px; min-width: 0; font-size: .84rem; }
.header-message > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.header-message.error { color: var(--color-error-text); }
.header-message.warning { color: var(--color-warning-text); }
.header-message.success { color: var(--color-success-text); }
.header-message button { min-height: 26px; padding: 2px 7px; }
.header-controls { position: relative; display: flex; align-items: center; gap: 8px; min-width: 0; }
.display-toggle { display: inline-flex; flex: none; min-height: 32px; padding: 2px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); background: var(--color-main-background); }
.display-toggle span { display: grid; place-items: center; min-width: 66px; padding: 3px 7px; border-radius: calc(var(--border-radius-large) - 2px); font-size: .84rem; font-weight: 600; }
.display-toggle span.active { background: var(--color-primary-element); color: var(--color-primary-element-text); }
.compact-control { display: flex; align-items: center; gap: 5px; min-width: 0; font-size: .86rem; font-weight: 600; }
.compact-control select { min-height: 32px; max-width: 220px; }
.bank-filter { flex: 1; }
.bank-filter select { width: min(100%, 240px); }
.action-menu { position: relative; flex: none; }
.action-menu > summary { display: grid; place-items: center; width: 34px; height: 34px; padding: 0; border: 0; border-radius: 50%; background: var(--color-primary-element); color: var(--color-primary-element-text); cursor: pointer; font-size: 25px; line-height: 1; list-style: none; }
.action-menu > summary::-webkit-details-marker { display: none; }
.action-popover { position: absolute; z-index: 70; inset-inline-end: 0; top: calc(100% + 5px); display: grid; width: 190px; padding: 6px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); background: var(--color-main-background); box-shadow: 0 5px 18px rgb(0 0 0 / 22%); }
.action-popover button { justify-content: flex-start; min-height: 36px; width: 100%; }
.search-popover { position: absolute; z-index: 69; inset-inline-end: 42px; top: calc(100% + 5px); display: grid; grid-template-columns: 24px minmax(0, 1fr) 34px; align-items: center; width: min(420px, calc(100vw - 24px)); min-height: 42px; padding: 5px 6px 5px 10px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); background: var(--color-main-background); box-shadow: 0 5px 18px rgb(0 0 0 / 22%); box-sizing: border-box; }
.search-popover input { width: 100%; min-width: 0; min-height: 34px; border: 0; background: transparent; }
.search-popover input:focus { outline: none; }
.search-icon { width: 20px; height: 20px; fill: currentColor; opacity: .7; }
.search-close { display: grid; place-items: center; width: 32px; height: 32px; padding: 0; border: 0; border-radius: 50%; background: transparent; font-size: 23px; }
.transaction-list { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); border: 1px solid var(--color-border); border-radius: var(--border-radius-large); overflow: hidden; }
.transaction-header, .row-content { display: grid; grid-template-columns: 100px minmax(150px, 1.35fr) minmax(150px, 1.2fr) 120px 72px 110px 76px; column-gap: 10px; align-items: center; }
.transaction-header { padding: 9px 12px; font-weight: 600; background: var(--color-background-dark); border-bottom: 1px solid var(--color-border); }
.amount-column, .amount-cell { text-align: end; }
.mark-column, .mark-cell { text-align: center; }
.scroller { min-height: 0; height: 100%; }
.transaction-row { border-bottom: 1px solid var(--color-border); background: var(--color-main-background); }
.transaction-row:nth-child(even) { background: var(--color-background-darker); }
.transaction-row.pending { box-shadow: inset 4px 0 0 var(--color-primary-element); }
.transaction-row.protected { background: var(--color-background-dark); }
.transaction-row.deleted { opacity: .58; text-decoration: line-through; }
.transaction-row.selected .row-content { background: var(--color-background-hover); }
.transaction-row.validation-error { box-shadow: inset 4px 0 0 var(--color-error); }
.transaction-row.validation-error .row-content { background: var(--color-error-light); }
.row-content { min-height: 58px; padding: 7px 12px; box-sizing: border-box; cursor: default; }
.row-content[role='button'] { cursor: pointer; }
.row-content:focus { outline: 2px solid var(--color-primary-element); outline-offset: -2px; }
.party-cell, .category-cell, .detail-note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.category-cell { display: grid; }
.category-cell small { opacity: .7; }
.date-mobile { display: none; }
.amount-cell { font-variant-numeric: tabular-nums; font-weight: 800; white-space: nowrap; }
.amount-cell.credit { color: #096b2d; }
.amount-cell.debit { color: var(--color-text-maxcontrast); }
.mark-cell input { width: 22px; height: 22px; cursor: pointer; }
.state-icon { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; font-size: .78rem; font-weight: 700; }
.telepointed { background: var(--color-warning); color: #000; }
.reconciled { background: var(--color-success); color: #fff; }
.status-cell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .86rem; }
.actions-cell { display: flex; gap: 4px; justify-content: flex-end; }
.actions-cell > button:not(.row-action-button) { min-height: 30px; padding: 3px 7px; }
.row-action-button { display: grid; place-items: center; width: 30px; height: 30px; min-height: 30px; padding: 4px; border-radius: 50%; }
.row-action-button svg { width: 18px; height: 18px; fill: currentColor; }
.delete-action:not(:disabled) { color: var(--color-error); }
.detail-line { grid-column: 2 / -1; display: flex; gap: 8px 18px; min-width: 0; padding-top: 6px; opacity: .78; font-size: .9rem; }
.mode-detailed .row-content { min-height: 88px; align-content: center; }
.empty-state { padding: 28px; text-align: center; opacity: .7; }
:global(body.theme--dark) .amount-cell.credit,
:global(body[data-theme-dark]) .amount-cell.credit,
:global(html[data-theme-dark]) .amount-cell.credit { color: #8ce99a; }
@media (prefers-color-scheme: dark) {
  .amount-cell.credit { color: #8ce99a; }
}
@media (max-width: 900px) {
  .workspace { padding: 5px 8px 8px; }
  .account-primary h1 { font-size: 1.08rem; }
  .account-primary > span, .account-secondary, .compact-control { font-size: .8rem; }
  .totals { gap: 6px; font-size: .8rem; }
  .totals strong { font-size: .92rem; }
  .header-message { font-size: .78rem; }
  .display-toggle span { min-width: 50px; padding-inline: 5px; font-size: .78rem; }
  .compact-control > span { display: none; }
  .compact-control select { max-width: none; min-width: 0; }
  .bank-filter { flex: 1 1 auto; }
  .bank-filter select { width: 100%; }
  .transaction-header { display: none; }
  .transaction-list { grid-template-rows: minmax(0, 1fr); border-inline: 0; border-radius: 0; }
  .row-content { grid-template-columns: 50px minmax(6ch, 1fr) minmax(6ch, 1fr) minmax(0, .65fr) minmax(74px, auto) 34px; grid-template-areas:
    'date party party party amount mark'
    'category category category status actions actions'
    'detail detail detail detail detail detail';
    gap: 4px 6px; min-height: 58px; padding: 8px 6px; }
  .date-cell { grid-area: date; font-size: .82rem; white-space: nowrap; }
  .date-desktop { display: none; }
  .date-mobile { display: inline; }
  .party-cell { grid-area: party; min-width: 12ch; font-weight: 600; }
  .category-cell { grid-area: category; display: flex; gap: 5px; font-size: .84rem; }
  .category-cell small::before { content: '› '; }
  .amount-cell { grid-area: amount; min-width: 74px; }
  .mark-cell { grid-area: mark; min-width: 34px; }
  .status-cell { display: none; grid-area: status; min-width: 0; text-align: center; font-size: .76rem; }
  .actions-cell { grid-area: actions; justify-content: flex-end; }
  .detail-line { grid-area: detail; gap: 6px 14px; padding-top: 3px; overflow: hidden; white-space: nowrap; font-size: .82rem; }
  .mode-compact .category-cell, .mode-compact .actions-cell, .mode-compact .status-cell, .mode-compact .detail-line { display: none; }
  .mode-compact .row-content { grid-template-areas: 'date party party party amount mark'; min-height: 54px; }
  .mode-detailed .status-cell { display: block; }
  .mode-detailed .row-content { min-height: 90px; }
}
@media (max-width: 540px) {
  .account-header { gap: 2px; }
  .account-primary { gap: 6px; }
  .account-primary > span { max-width: 105px; overflow: hidden; text-overflow: ellipsis; }
  .account-secondary { gap: 6px; }
  .totals > span:not(.pending-count) { display: none; }
  .header-message { justify-content: flex-start; }
  .header-controls { gap: 6px; }
  .display-toggle span { min-width: 43px; }
  .search-popover { inset-inline: 0; width: 100%; }
}
</style>
