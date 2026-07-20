<template>
  <div class="editor-backdrop" @mousedown.self="$emit('cancel')">
    <section class="transaction-panel" role="dialog" aria-modal="true" :aria-label="title">
      <header class="panel-header">
        <div>
          <p class="eyebrow">{{ draft.isNew ? 'Pending new transaction' : `Transaction ${draft.transactionId}` }}</p>
          <h2>{{ title }}</h2>
          <p class="local-note">Changes stay local until “Save all to file”.</p>
        </div>
        <button type="button" class="icon-button" aria-label="Close transaction editor" @click="$emit('cancel')">×</button>
      </header>

      <div class="panel-body">
        <div v-if="editorError" class="editor-error" role="alert">{{ editorError }}</div>
        <div v-if="completionTrace" class="completion-notice">
          <span>Filled from the latest transaction for this party.</span>
          <button type="button" @click="undoCompletion">Undo</button>
        </div>

        <div class="field-grid common-fields">
          <label>
            <span>Date</span>
            <input v-model="draft.date" type="text" inputmode="numeric" placeholder="MM/DD/YYYY">
          </label>
          <label :class="{ autofilled: isAutoFilled('amount') }">
            <span>Amount</span>
            <input v-model="draft.amount" type="number" step="any" inputmode="decimal" @change="amountChanged">
          </label>

          <TransactionAutocomplete
            :model-value="draft.partyName"
            :selected-id="draft.partySelectionId"
            :items="snapshot.parties"
            :recent-ids="recentSelections.party"
            label="Party"
            placeholder="Select or create a party"
            create-label="Create party"
            allow-create
            :autofocus="autoFocusParty"
            :class="{ autofilled: isAutoFilled('partyName') }"
            @update:model-value="partyInput"
            @select="partySelected"
            @create="partyCreated"
            @clear="partyCleared"
          />

          <TransactionAutocomplete
            :model-value="draft.categoryName"
            :selected-id="draft.categorySelectionId"
            :items="categoryChoices"
            :recent-ids="recentSelections.category"
            label="Category"
            placeholder="Select, create, or choose Transfer"
            create-label="Create category"
            allow-create
            :class="{ autofilled: isAutoFilled('categoryName') }"
            @update:model-value="categoryInput"
            @select="categorySelected"
            @create="categoryCreated"
            @clear="categoryCleared"
          />
        </div>

        <section v-if="isTransfer" class="transfer-section">
          <div class="section-heading">
            <div>
              <h3>Account transfer</h3>
              <p>Both linked account transactions will be updated together.</p>
            </div>
            <strong>{{ oppositeAmount }}</strong>
          </div>
          <div class="field-grid">
            <TransactionAutocomplete
              :model-value="draft.subcategoryName"
              :selected-id="draft.transferAccountSelectionId"
              :items="transferAccounts"
              :recent-ids="recentSelections.transferAccount"
              label="Destination account"
              placeholder="Choose another account"
              @update:model-value="transferAccountInput"
              @select="transferAccountSelected"
              @clear="transferAccountCleared"
            />
            <TransactionAutocomplete
              :model-value="draft.paymentMethodName"
              :selected-id="draft.paymentMethodSelectionId"
              :items="sourcePaymentChoices"
              :recent-ids="recentSelections.payment"
              label="Source payment method"
              placeholder="Choose payment method"
              @update:model-value="sourcePaymentInput"
              @select="sourcePaymentSelected"
              @clear="sourcePaymentCleared"
            />
            <TransactionAutocomplete
              :model-value="draft.transferPaymentMethodName"
              :selected-id="draft.transferPaymentMethodSelectionId"
              :items="targetPaymentChoices"
              :recent-ids="recentSelections.transferPayment"
              label="Destination payment method"
              placeholder="Choose counterpart method"
              @update:model-value="targetPaymentInput"
              @select="targetPaymentSelected"
              @clear="targetPaymentCleared"
            />
          </div>
          <p class="transfer-summary">
            {{ snapshot.account.name }}: {{ draft.amount || '0' }} {{ snapshot.account.currency.code }} ·
            {{ targetAccount?.name || 'destination' }}: {{ oppositeAmount }}
          </p>
        </section>

        <div v-else class="field-grid">
          <TransactionAutocomplete
            :model-value="draft.subcategoryName"
            :selected-id="draft.subcategorySelectionId"
            :items="subcategoryChoices"
            :recent-ids="recentSelections.subcategory"
            label="Subcategory"
            placeholder="Select or create a subcategory"
            create-label="Create subcategory"
            allow-create
            :class="{ autofilled: isAutoFilled('subcategoryName') }"
            @update:model-value="subcategoryInput"
            @select="subcategorySelected"
            @create="subcategoryCreated"
            @clear="subcategoryCleared"
          />
          <TransactionAutocomplete
            :model-value="draft.paymentMethodName"
            :selected-id="draft.paymentMethodSelectionId"
            :items="sourcePaymentChoices"
            :recent-ids="recentSelections.payment"
            label="Payment method"
            placeholder="Choose payment method"
            :class="{ autofilled: isAutoFilled('paymentMethodName') }"
            @update:model-value="sourcePaymentInput"
            @select="sourcePaymentSelected"
            @clear="sourcePaymentCleared"
          />
        </div>

        <label class="note-field" :class="{ autofilled: isAutoFilled('note') }">
          <span>Note</span>
          <textarea v-model="draft.note" rows="3" placeholder="Optional note"></textarea>
        </label>

        <div class="marked-field">
          <span>Bank check status</span>
          <label v-if="draft.isNew || draft.quickMarkable" class="checkbox-label">
            <input v-model="checked" type="checkbox">
            <span>{{ checked ? 'Checked' : 'Unchecked' }}</span>
          </label>
          <span v-else class="locked-state">
            {{ Number(draft.marked) === 3 ? 'Reconciled — locked' : 'Telepointed — locked' }}
          </span>
        </div>

        <details class="advanced-fields">
          <summary>Advanced fields</summary>
          <div class="field-grid">
            <label>
              <span>Value date</span>
              <input v-model="draft.valueDate" type="text" inputmode="numeric" placeholder="MM/DD/YYYY">
            </label>
            <label :class="{ autofilled: isAutoFilled('paymentReference') }">
              <span>Payment reference</span>
              <input v-model="draft.paymentReference" type="text">
            </label>
            <label :class="{ autofilled: isAutoFilled('voucher') }">
              <span>Voucher</span>
              <input v-model="draft.voucher" type="text">
            </label>
            <label :class="{ autofilled: isAutoFilled('bankReference') }">
              <span>Bank reference</span>
              <input v-model="draft.bankReference" type="text">
            </label>
          </div>
        </details>
      </div>

      <footer class="panel-footer">
        <button type="button" @click="$emit('cancel')">Cancel</button>
        <button type="button" class="primary" @click="apply(false)">Save draft</button>
        <button type="button" class="primary secondary-action" @click="apply(true)">Save draft & add another</button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import TransactionAutocomplete from './TransactionAutocomplete.vue'
import {
  resetCategoryDependentFields,
  resetTransferPaymentFields,
  setDraftMarked,
} from '@/domain/editorDraftMutations.mjs'
import {
  TRANSFER_CATEGORY,
  applyPartyCompletionTrace,
  buildResponsiveMutationOperations,
  normalizeName,
  onAmountDirectionChanged,
  paymentMethodsForAmount,
  setSelectedItem,
  syncSelectionIds,
  undoPartyCompletion,
  updateSelectionText,
} from '@/domain/responsiveEditor.mjs'

const props = defineProps({
  draft: { type: Object, required: true },
  snapshot: { type: Object, required: true },
  recentSelections: {
    type: Object,
    default: () => ({
      party: [], category: [], subcategory: [], payment: [],
      transferAccount: [], transferPayment: [],
    }),
  },
  autoFocusParty: { type: Boolean, default: false },
})

const emit = defineEmits(['apply', 'apply-add', 'cancel', 'recent'])
const editorError = ref('')
const completionTrace = ref(null)
const autoFilledFields = ref([])

const title = computed(() => props.draft.isNew ? 'New transaction' : 'Edit transaction')
const isTransfer = computed(() => normalizeName(props.draft.categoryName) === normalizeName(TRANSFER_CATEGORY))
const categoryChoices = computed(() => [
  { id: '__transfer__', name: TRANSFER_CATEGORY, isTransfer: true, secondary: 'Account transfer' },
  ...props.snapshot.categories,
])
const transferAccounts = computed(() => props.snapshot.accounts
  .filter(item => !item.closed && String(item.id) !== String(props.snapshot.account.id)))
const currentCategory = computed(() => props.snapshot.categories.find(item =>
  String(item.id) === String(props.draft.categorySelectionId ?? '')
  || normalizeName(item.name) === normalizeName(props.draft.categoryName)))
const subcategoryChoices = computed(() => currentCategory.value?.subcategories ?? [])
const sourcePaymentChoices = computed(() => paymentMethodsForAmount(
  props.snapshot,
  props.snapshot.account.id,
  props.draft.amount,
))
const targetAccount = computed(() => transferAccounts.value.find(item =>
  String(item.id) === String(props.draft.transferAccountSelectionId ?? '')
  || normalizeName(item.name) === normalizeName(props.draft.subcategoryName)))
const targetPaymentChoices = computed(() => targetAccount.value
  ? paymentMethodsForAmount(props.snapshot, targetAccount.value.id, String(-Number(props.draft.amount)))
  : [])
const oppositeAmount = computed(() => {
  const amount = Number(props.draft.amount)
  if (!Number.isFinite(amount)) return '—'
  return `${(-amount).toFixed(props.snapshot.account.currency.precision)} ${props.snapshot.account.currency.code}`
})
const checked = computed({
  get: () => Number(props.draft.marked) === 1,
  set: value => setDraftMarked(props.draft, value),
})

function remember(kind, item) {
  if (item?.id != null) emit('recent', { kind, id: String(item.id) })
}

function isAutoFilled(field) {
  return autoFilledFields.value.includes(field)
}

function partyInput(value) {
  updateSelectionText(props.draft, 'party', value, props.snapshot.parties)
  completionTrace.value = null
  autoFilledFields.value = []
}
function partySelected(item) {
  setSelectedItem(props.draft, 'party', item)
  remember('party', item)
  completionTrace.value = applyPartyCompletionTrace(props.draft, props.snapshot)
  autoFilledFields.value = completionTrace.value?.fields ?? []
  onAmountDirectionChanged(props.draft, props.snapshot)
  syncSelectionIds(props.draft, props.snapshot)
}
function partyCreated(value) { partyInput(value) }
function partyCleared() { partyInput('') }

function categoryInput(value) {
  updateSelectionText(props.draft, 'category', value, categoryChoices.value)
  resetCategoryDependentFields(props.draft)
}
function categorySelected(item) {
  setSelectedItem(props.draft, 'category', item)
  remember('category', item)
  onAmountDirectionChanged(props.draft, props.snapshot)
  syncSelectionIds(props.draft, props.snapshot)
}
function categoryCreated(value) { categoryInput(value) }
function categoryCleared() { categoryInput('') }

function subcategoryInput(value) { updateSelectionText(props.draft, 'subcategory', value, subcategoryChoices.value) }
function subcategorySelected(item) { setSelectedItem(props.draft, 'subcategory', item); remember('subcategory', item) }
function subcategoryCreated(value) { subcategoryInput(value) }
function subcategoryCleared() { subcategoryInput('') }

function sourcePaymentInput(value) { updateSelectionText(props.draft, 'payment', value, sourcePaymentChoices.value) }
function sourcePaymentSelected(item) { setSelectedItem(props.draft, 'payment', item); remember('payment', item) }
function sourcePaymentCleared() { sourcePaymentInput('') }

function transferAccountInput(value) {
  updateSelectionText(props.draft, 'transferAccount', value, transferAccounts.value)
  resetTransferPaymentFields(props.draft)
}
function transferAccountSelected(item) {
  setSelectedItem(props.draft, 'transferAccount', item)
  remember('transferAccount', item)
  onAmountDirectionChanged(props.draft, props.snapshot)
  syncSelectionIds(props.draft, props.snapshot)
}
function transferAccountCleared() { transferAccountInput('') }

function targetPaymentInput(value) { updateSelectionText(props.draft, 'transferPayment', value, targetPaymentChoices.value) }
function targetPaymentSelected(item) { setSelectedItem(props.draft, 'transferPayment', item); remember('transferPayment', item) }
function targetPaymentCleared() { targetPaymentInput('') }

function amountChanged() {
  onAmountDirectionChanged(props.draft, props.snapshot)
  syncSelectionIds(props.draft, props.snapshot)
}

function undoCompletion() {
  undoPartyCompletion(props.draft, completionTrace.value, props.snapshot)
  completionTrace.value = null
  autoFilledFields.value = []
}

function apply(addAnother) {
  editorError.value = ''
  try {
    buildResponsiveMutationOperations([props.draft], props.snapshot)
  } catch (error) {
    editorError.value = error.message
    return
  }
  emit(addAnother ? 'apply-add' : 'apply', props.draft)
}
</script>

<style scoped>
.editor-backdrop { position: fixed; z-index: 1050; inset: 0; background: rgb(0 0 0 / 24%); }
.transaction-panel { position: absolute; inset-block: 0; inset-inline-end: 0; width: min(540px, 94vw); display: grid; grid-template-rows: auto 1fr auto; background: var(--color-main-background); box-shadow: -8px 0 28px rgb(0 0 0 / 22%); }
.panel-header { display: flex; justify-content: space-between; gap: 20px; padding: 20px; border-bottom: 1px solid var(--color-border); }
.panel-header h2 { margin: 2px 0 4px; }
.eyebrow { margin: 0; opacity: .65; font-size: .82rem; text-transform: uppercase; letter-spacing: .04em; }
.local-note { margin: 0; opacity: .7; }
.icon-button { width: 40px; height: 40px; border: 0; border-radius: 50%; background: transparent; font-size: 26px; cursor: pointer; }
.icon-button:hover { background: var(--color-background-hover); }
.panel-body { min-height: 0; overflow-y: auto; padding: 20px; display: grid; align-content: start; gap: 18px; }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.common-fields > :nth-child(n + 3) { grid-column: 1 / -1; }
label { display: grid; gap: 6px; min-width: 0; font-weight: 600; }
label input, label textarea { width: 100%; min-height: 40px; box-sizing: border-box; font-weight: 400; }
label textarea { resize: vertical; padding: 8px; }
.note-field { display: grid; }
.autofilled { padding: 7px; margin: -7px; border-radius: var(--border-radius); background: var(--color-primary-light); }
.completion-notice, .editor-error { display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 10px 12px; border-radius: var(--border-radius-large); }
.completion-notice { background: var(--color-primary-light); }
.editor-error { background: var(--color-error-light); color: var(--color-error-text); }
.transfer-section { display: grid; gap: 14px; padding: 14px; border: 1px solid var(--color-primary-element); border-radius: var(--border-radius-large); }
.section-heading { display: flex; justify-content: space-between; gap: 12px; }
.section-heading h3, .section-heading p { margin: 0; }
.section-heading p { opacity: .7; }
.transfer-summary { margin: 0; padding-top: 10px; border-top: 1px solid var(--color-border); }
.marked-field { display: grid; gap: 8px; font-weight: 600; }
.checkbox-label { display: flex; align-items: center; gap: 9px; font-weight: 400; }
.checkbox-label input { width: 22px; height: 22px; min-height: 0; }
.locked-state { padding: 9px 11px; border-radius: var(--border-radius); background: var(--color-background-dark); }
.advanced-fields { border-top: 1px solid var(--color-border); padding-top: 12px; }
.advanced-fields summary { cursor: pointer; font-weight: 600; margin-bottom: 14px; }
.panel-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--color-border); background: var(--color-main-background); }
.panel-footer button { min-height: 40px; padding: 8px 14px; }
.panel-footer .primary { background: var(--color-primary-element); color: var(--color-primary-element-text); border-color: transparent; }
.secondary-action { white-space: nowrap; }
@media (max-width: 700px) {
  .editor-backdrop { background: var(--color-main-background); }
  .transaction-panel { width: 100%; inset: 0; box-shadow: none; }
  .panel-header { padding: 14px 16px; }
  .panel-body { padding: 16px; }
  .field-grid { grid-template-columns: 1fr; }
  .common-fields > * { grid-column: 1; }
  label input, label textarea { min-height: 46px; font-size: 16px; }
  .panel-footer { position: sticky; bottom: 0; display: grid; grid-template-columns: 1fr 1fr; padding: 10px 12px; }
  .panel-footer button { min-height: 46px; }
  .panel-footer .secondary-action { grid-column: 1 / -1; }
}
</style>
