<template>
  <NcAppContent>
    <div v-if="loading" class="loading"><NcLoadingIcon :size="32" /><p>Loading transactions…</p></div>
    <div v-else-if="snapshot" class="editor">
      <div v-if="message" class="message" :class="messageType">
        {{ message }}
        <button v-if="conflict" type="button" @click="reloadAfterConflict">Reload current file</button>
      </div>
      <header class="account-header">
        <div><h2>{{ snapshot.account.name }}</h2><p>Account {{ snapshot.account.id }} · ETag {{ etag }}</p></div>
        <div class="totals"><strong>{{ totals.totalAmount }} {{ snapshot.account.currency.code }}</strong><span>Marked: {{ totals.totalMarkedAmount }} {{ snapshot.account.currency.code }}</span></div>
      </header>
      <div class="toolbar">
        <button type="button" :disabled="saving || conflict" @click="addTransaction">Add transaction</button>
        <button type="button" :disabled="saving || conflict || !pendingChanges" @click="saveChanges">{{ saving ? 'Saving…' : 'Save changes' }}</button>
        <button type="button" :disabled="saving" @click="reloadSnapshot">Discard and reload</button>
      </div>

      <datalist id="p5-parties"><option v-for="party in snapshot.parties" :key="party.id" :value="party.name" /></datalist>
      <datalist id="p5-categories"><option :value="TRANSFER_CATEGORY" /><option v-for="category in snapshot.categories" :key="category.id" :value="category.name" /></datalist>

      <div class="grid-scroll">
        <div class="grid-row header">
          <span>#</span><span>Date</span><span>Amount</span><span>Party</span><span>Category</span><span>Subcategory / destination</span><span>Payment</span><span>Contra payment</span><span>Note</span><span>Marked</span><span>Bank ref.</span><span>Status</span><span>Actions</span>
        </div>
        <DynamicScroller class="scroller" :items="displayedRows" :min-item-size="48" key-field="key">
          <template #default="{ item: row, active, index }">
            <DynamicScrollerItem :item="row" :active="active" :data-index="index" class="grid-row body" :class="{ deleted: row.deleted, protected: row.protected }">
              <span>{{ row.transactionId || 'new' }}</span>
              <span><input v-model="row.date" :disabled="!isEditable(row)" size="10"></span>
              <span><input v-model="row.amount" :disabled="!isEditable(row)" type="number" step="any" @change="amountChanged(row)"></span>
              <span><input v-model="row.partyName" :disabled="!isEditable(row)" list="p5-parties" @change="completeParty(row)"></span>
              <span><input v-model="row.categoryName" :disabled="!isEditable(row)" list="p5-categories" @change="categoryChanged(row)"></span>
              <span>
                <input v-model="row.subcategoryName" :disabled="!isEditable(row)" :list="`p5-sub-${row.key}`" @change="destinationChanged(row)">
                <datalist :id="`p5-sub-${row.key}`"><option v-for="item in subcategoryChoices(row)" :key="item.id" :value="item.name" /></datalist>
              </span>
              <span>
                <input v-model="row.paymentMethodName" :disabled="!isEditable(row)" :list="`p5-pay-${row.key}`">
                <datalist :id="`p5-pay-${row.key}`"><option v-for="item in sourcePayments(row)" :key="item.id" :value="item.name" /></datalist>
              </span>
              <span>
                <template v-if="isTransferRow(row)">
                  <input v-model="row.transferPaymentMethodName" :disabled="!isEditable(row)" :list="`p5-contra-${row.key}`">
                  <datalist :id="`p5-contra-${row.key}`"><option v-for="item in targetPayments(row)" :key="item.id" :value="item.name" /></datalist>
                </template>
                <span v-else>—</span>
              </span>
              <span><input v-model="row.note" :disabled="!isEditable(row)"></span>
              <span>
                <input
                  type="checkbox"
                  :checked="Number(row.marked) === 1"
                  :disabled="saving || conflict || row.deleted || (!row.isNew && !row.quickMarkable)"
                  :title="markTitle(row)"
                  @change="quickMarkChanged(row, $event)"
                >
              </span>
              <span><input v-model="row.bankReference" :disabled="!isEditable(row)"></span>
              <span class="status"><span v-if="row.deleted">Pending deletion</span><span v-else-if="row.protected">Read-only: {{ row.protectionReasons.join(', ') }}</span><span v-else-if="row.isTransfer">Transfer</span><span v-else-if="row.isNew">New</span><span v-else-if="row.editing">Editing</span><span v-else>Saved</span></span>
              <span class="actions">
                <button v-if="row.deleted" type="button" @click="row.deleted = false">Undo</button>
                <template v-else-if="!row.protected">
                  <button v-if="!row.editing" type="button" @click="row.editing = true">Edit</button>
                  <button v-else-if="!row.isNew" type="button" @click="cancelEdit(row)">Cancel</button>
                  <button type="button" @click="removeTransaction(row)">Delete</button>
                </template>
              </span>
            </DynamicScrollerItem>
          </template>
        </DynamicScroller>
      </div>
    </div>
  </NcAppContent>
</template>

<script setup>
import { NcAppContent, NcLoadingIcon } from '@nextcloud/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import {
  TRANSFER_CATEGORY, allowReconciledMutations, applyPartyCompletion, buildMutationOperations,
  calculateTotals, createDrafts, hasPendingChanges, newTransactionDraft, normalizeName,
  onAmountDirectionChanged, paymentMethodsForAmount,
} from '@/domain/transactionEditor.mjs'
import { apiError, fetchEditorSnapshot, mutateDocument } from '@/services/gsbApi'

const store = useStore(); const route = useRoute(); const router = useRouter()
const loading = ref(true); const saving = ref(false); const snapshot = ref(null); const rows = ref([]); const etag = ref('')
const selectedAccountId = ref(String(route.params.id)); const message = ref(''); const messageType = ref('info'); const conflict = ref(false)
let newSequence = 0; let revertingRoute = false
const displayedRows = computed(() => [...rows.value].reverse())
const pendingChanges = computed(() => hasPendingChanges(rows.value))
const totals = computed(() => calculateTotals(rows.value, snapshot.value?.account?.currency?.precision ?? 2))
function setMessage(text, type = 'info') { message.value = text; messageType.value = type }
async function loadSnapshot() {
  loading.value = true; conflict.value = false
  try {
    const response = await fetchEditorSnapshot({ accountId: selectedAccountId.value, filePath: store.state.filePath, filePassword: store.state.filePassword })
    snapshot.value = response.snapshot; etag.value = response.document.etag; rows.value = createDrafts(response.snapshot)
    if (response.snapshot.warnings?.length) {
      setMessage(`Opened with ${response.snapshot.warnings.length} Grisbi compatibility warning(s). Affected rows are read-only.`, 'warning')
    } else setMessage('')
  } catch (error) { const failure = apiError(error); setMessage(failure.message, 'error') } finally { loading.value = false }
}
function isEditable(row) { return !row.deleted && !row.protected && row.editing }
function isTransferRow(row) { return normalizeName(row.categoryName) === normalizeName(TRANSFER_CATEGORY) }
function subcategoryChoices(row) {
  if (isTransferRow(row)) return snapshot.value.accounts.filter(item => !item.closed && item.id !== snapshot.value.account.id)
  const category = snapshot.value.categories.find(item => normalizeName(item.name) === normalizeName(row.categoryName))
  return category?.subcategories ?? []
}
function sourcePayments(row) { return paymentMethodsForAmount(snapshot.value, snapshot.value.account.id, row.amount) }
function targetAccount(row) { return snapshot.value.accounts.find(item => normalizeName(item.name) === normalizeName(row.subcategoryName)) }
function targetPayments(row) { const target = targetAccount(row); return target ? paymentMethodsForAmount(snapshot.value, target.id, String(-Number(row.amount))) : [] }
function today() { const value = new Date(); return `${String(value.getMonth() + 1).padStart(2, '0')}/${String(value.getDate()).padStart(2, '0')}/${value.getFullYear()}` }
function addTransaction() { newSequence += 1; rows.value.push(newTransactionDraft(snapshot.value, `new-${newSequence}`, today())) }
function cancelEdit(row) { Object.assign(row, row.original); row.editing = false }
function removeTransaction(row) { if (row.isNew) rows.value = rows.value.filter(item => item.key !== row.key); else { row.deleted = true; row.editing = false } }
function completeParty(row) { if (row.isNew) applyPartyCompletion(row, snapshot.value); onAmountDirectionChanged(row, snapshot.value) }
function amountChanged(row) { onAmountDirectionChanged(row, snapshot.value) }
function categoryChanged(row) { row.subcategoryName = ''; row.transferPaymentMethodName = '' }
function destinationChanged(row) { if (isTransferRow(row)) onAmountDirectionChanged(row, snapshot.value) }
function quickMarkChanged(row, event) { row.marked = event.target.checked ? 1 : 0 }
function markTitle(row) {
  if (row.isNew || row.quickMarkable) return 'Check or uncheck this transaction without opening the editor.'
  if (Number(row.marked) === 2) return 'Telepointed transactions require the dedicated reconciliation workflow.'
  if (Number(row.marked) === 3) return 'Reconciled transactions require the dedicated reconciliation workflow.'
  return 'This marked state cannot be changed here.'
}
async function submitOperations(operations, confirmed = false) {
  try {
    const response = await mutateDocument({ filePath: store.state.filePath, filePassword: store.state.filePassword, baseEtag: etag.value, operations })
    etag.value = response.document.etag; setMessage('Transactions saved successfully.', 'success'); await loadSnapshot()
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
    setMessage(conflict.value ? 'The GSB file changed elsewhere. Your draft is preserved; reload before saving again.' : failure.message, 'error')
    return false
  }
}
async function saveChanges() {
  let operations
  try { operations = buildMutationOperations(rows.value, snapshot.value) } catch (error) { setMessage(error.message, 'error'); return }
  if (!operations.length) { setMessage('There are no validated changes to save.'); return }
  saving.value = true
  try { await submitOperations(operations) } finally { saving.value = false }
}
async function reloadSnapshot() { if (pendingChanges.value && !window.confirm('Discard all unsaved transaction changes?')) return; await loadSnapshot() }
async function reloadAfterConflict() { if (!window.confirm('Reload the current file and discard this local draft?')) return; await loadSnapshot() }
onMounted(loadSnapshot)
watch(() => route.params.id, async newId => {
  if (revertingRoute) { revertingRoute = false; return }
  if (pendingChanges.value && !window.confirm('Discard unsaved changes and switch accounts?')) { revertingRoute = true; await router.replace({ name: 'Account', params: { id: selectedAccountId.value } }); return }
  selectedAccountId.value = String(newId); await loadSnapshot()
})
</script>

<style scoped>
.editor { padding: 16px; min-width: 0; }
.loading { display: flex; gap: 12px; align-items: center; justify-content: center; min-height: 240px; }
.account-header { display: flex; justify-content: space-between; gap: 24px; }
.account-header h2 { margin-bottom: 4px; }.account-header p { opacity: .7; }.totals { display: flex; flex-direction: column; text-align: right; }
.toolbar { display: flex; gap: 8px; margin: 16px 0; }.message { margin-bottom: 12px; padding: 10px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); }.message.error { border-color: var(--color-error); }.message.warning { border-color: var(--color-warning); }.message.success { border-color: var(--color-success); }
.grid-scroll { overflow-x: auto; }.grid-row { display: grid; grid-template-columns: 60px 110px 110px 170px 150px 190px 145px 145px 180px 65px 145px 150px 140px; gap: 4px; align-items: center; min-width: 1900px; padding: 4px; box-sizing: border-box; }
.header { font-weight: bold; background: var(--color-background-dark); border-bottom: 1px solid var(--color-border); }.scroller { height: 62vh; min-width: 1900px; }.body { border-bottom: 1px solid var(--color-border); }.body:nth-child(even) { background: var(--color-background-darker); }.body input:not([type='checkbox']) { width: 100%; box-sizing: border-box; }.deleted { opacity: .55; text-decoration: line-through; }.protected { background: var(--color-background-dark); }.status { font-size: .9em; }.actions { white-space: nowrap; }.actions button { margin-right: 4px; }
</style>
