<template>
  <div class="editor-backdrop" @mousedown.self="$emit('cancel')">
    <section class="transaction-panel" role="dialog" aria-modal="true" :aria-label="title">
      <header class="panel-header">
        <h2>{{ title }}</h2>
        <button
          type="button"
          class="icon-button"
          aria-label="Close transaction editor"
          @click="$emit('cancel')"
        >
          ×
        </button>
      </header>

      <div class="panel-body">
        <div v-if="editorError" class="editor-error" role="alert">
          {{ editorError }}
        </div>
        <div v-if="completionTrace" class="completion-notice">
          <span>Filled from the latest transaction for this party.</span>
          <button type="button" @click="undoCompletion">Undo</button>
        </div>

        <div class="field-grid common-fields">
          <label :class="{ invalid: fieldInvalid('date') }">
            <span>Date</span>
            <input
              ref="dateInput"
              v-model="localDraft.date"
              type="text"
              inputmode="numeric"
              placeholder="MM/DD/YYYY"
              :aria-invalid="fieldInvalid('date') ? 'true' : undefined"
              :aria-describedby="fieldInvalid('date') ? 'transaction-date-error' : undefined"
              @input="clearFieldError('date')"
            >
            <small v-if="fieldInvalid('date')" id="transaction-date-error" class="field-error">
              {{ fieldError.message }}
            </small>
          </label>
          <label :class="[{ autofilled: isAutoFilled('amount') }, { invalid: fieldInvalid('amount') }]">
            <span>Amount</span>
            <input
              ref="amountInput"
              v-model="localDraft.amount"
              type="number"
              step="any"
              inputmode="decimal"
              :aria-invalid="fieldInvalid('amount') ? 'true' : undefined"
              :aria-describedby="fieldInvalid('amount') ? 'transaction-amount-error' : undefined"
              @input="clearFieldError('amount')"
              @change="amountChanged"
            >
            <small v-if="fieldInvalid('amount')" id="transaction-amount-error" class="field-error">
              {{ fieldError.message }}
            </small>
          </label>

          <TransactionAutocomplete
            ref="partyField"
            :model-value="localDraft.partyName"
            :selected-id="localDraft.partySelectionId"
            :items="snapshot.parties"
            :recent-ids="recentSelections.party"
            label="Party"
            placeholder="Select or create a party"
            create-label="Create party"
            allow-create
            :autofocus="autoFocusParty"
            :error="fieldInvalid('partyName')"
            :error-message="fieldInvalid('partyName') ? fieldError.message : ''"
            :class="{ autofilled: isAutoFilled('partyName') }"
            @update:model-value="partyInput"
            @select="partySelected"
            @create="partyCreated"
            @clear="partyCleared"
          />

          <TransactionAutocomplete
            ref="categoryField"
            :model-value="localDraft.categoryName"
            :selected-id="localDraft.categorySelectionId"
            :items="categoryChoices"
            :recent-ids="recentSelections.category"
            label="Category"
            placeholder="Select, create, or choose Transfer"
            create-label="Create category"
            allow-create
            :error="fieldInvalid('categoryName')"
            :error-message="fieldInvalid('categoryName') ? fieldError.message : ''"
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
              ref="transferAccountField"
              :model-value="localDraft.subcategoryName"
              :selected-id="localDraft.transferAccountSelectionId"
              :items="transferAccounts"
              :recent-ids="recentSelections.transferAccount"
              label="Destination account"
              placeholder="Choose another account"
              :error="fieldInvalid('transferAccount')"
              :error-message="fieldInvalid('transferAccount') ? fieldError.message : ''"
              @update:model-value="transferAccountInput"
              @select="transferAccountSelected"
              @clear="transferAccountCleared"
            />
            <TransactionAutocomplete
              ref="paymentField"
              :model-value="localDraft.paymentMethodName"
              :selected-id="localDraft.paymentMethodSelectionId"
              :items="sourcePaymentChoices"
              :recent-ids="recentSelections.payment"
              label="Source payment method"
              placeholder="Choose payment method"
              :error="fieldInvalid('paymentMethodName')"
              :error-message="fieldInvalid('paymentMethodName') ? fieldError.message : ''"
              @update:model-value="sourcePaymentInput"
              @select="sourcePaymentSelected"
              @clear="sourcePaymentCleared"
            />
            <TransactionAutocomplete
              ref="transferPaymentField"
              :model-value="localDraft.transferPaymentMethodName"
              :selected-id="localDraft.transferPaymentMethodSelectionId"
              :items="targetPaymentChoices"
              :recent-ids="recentSelections.transferPayment"
              label="Destination payment method"
              placeholder="Choose counterpart method"
              :error="fieldInvalid('transferPaymentMethodName')"
              :error-message="fieldInvalid('transferPaymentMethodName') ? fieldError.message : ''"
              @update:model-value="targetPaymentInput"
              @select="targetPaymentSelected"
              @clear="targetPaymentCleared"
            />
          </div>
          <p class="transfer-summary">
            {{ snapshot.account.name }}: {{ localDraft.amount || '0' }} {{ snapshot.account.currency.code }} ·
            {{ targetAccount?.name || 'destination' }}: {{ oppositeAmount }}
          </p>
        </section>

        <div v-else class="field-grid">
          <TransactionAutocomplete
            ref="subcategoryField"
            :model-value="localDraft.subcategoryName"
            :selected-id="localDraft.subcategorySelectionId"
            :items="subcategoryChoices"
            :recent-ids="recentSelections.subcategory"
            label="Subcategory"
            placeholder="Select or create a subcategory"
            create-label="Create subcategory"
            allow-create
            :error="fieldInvalid('subcategoryName')"
            :error-message="fieldInvalid('subcategoryName') ? fieldError.message : ''"
            :class="{ autofilled: isAutoFilled('subcategoryName') }"
            @update:model-value="subcategoryInput"
            @select="subcategorySelected"
            @create="subcategoryCreated"
            @clear="subcategoryCleared"
          />
          <TransactionAutocomplete
            ref="paymentField"
            :model-value="localDraft.paymentMethodName"
            :selected-id="localDraft.paymentMethodSelectionId"
            :items="sourcePaymentChoices"
            :recent-ids="recentSelections.payment"
            label="Payment method"
            placeholder="Choose payment method"
            :error="fieldInvalid('paymentMethodName')"
            :error-message="fieldInvalid('paymentMethodName') ? fieldError.message : ''"
            :class="{ autofilled: isAutoFilled('paymentMethodName') }"
            @update:model-value="sourcePaymentInput"
            @select="sourcePaymentSelected"
            @clear="sourcePaymentCleared"
          />
        </div>

        <label class="note-field" :class="{ autofilled: isAutoFilled('note') }">
          <span>Note</span>
          <textarea v-model="localDraft.note" rows="3" placeholder="Optional note"></textarea>
        </label>

        <div class="marked-field" :class="{ invalid: fieldInvalid('marked') }">
          <span>Bank check status</span>
          <label v-if="localDraft.isNew || localDraft.quickMarkable" class="checkbox-label">
            <input v-model="checked" type="checkbox" @change="clearFieldError('marked')">
            <span>{{ checked ? 'Checked' : 'Unchecked' }}</span>
          </label>
          <span v-else class="locked-state">
            {{ Number(localDraft.marked) === 3 ? 'Reconciled — locked' : 'Telepointed — locked' }}
          </span>
          <small v-if="fieldInvalid('marked')" class="field-error">{{ fieldError.message }}</small>
        </div>

        <details ref="advancedFields" class="advanced-fields">
          <summary>Advanced fields</summary>
          <div class="field-grid">
            <label :class="{ invalid: fieldInvalid('valueDate') }">
              <span>Value date</span>
              <input
                ref="valueDateInput"
                v-model="localDraft.valueDate"
                type="text"
                inputmode="numeric"
                placeholder="MM/DD/YYYY"
                :aria-invalid="fieldInvalid('valueDate') ? 'true' : undefined"
                @input="clearFieldError('valueDate')"
              >
              <small v-if="fieldInvalid('valueDate')" class="field-error">{{ fieldError.message }}</small>
            </label>
            <label :class="{ autofilled: isAutoFilled('paymentReference') }">
              <span>Payment reference</span>
              <input v-model="localDraft.paymentReference" type="text">
            </label>
            <label :class="{ autofilled: isAutoFilled('voucher') }">
              <span>Voucher</span>
              <input v-model="localDraft.voucher" type="text">
            </label>
            <label :class="{ autofilled: isAutoFilled('bankReference') }">
              <span>Bank reference</span>
              <input v-model="localDraft.bankReference" type="text">
            </label>
          </div>
        </details>
      </div>

      <footer class="panel-footer">
        <button type="button" @click="$emit('cancel')">Cancel</button>
        <button type="button" class="primary" @click="apply(false)">
          <span class="desktop-label">Save draft</span>
          <span class="mobile-label">Save</span>
        </button>
        <button type="button" class="primary secondary-action" @click="apply(true)">
          <span class="desktop-label">Save draft & add another</span>
          <span class="mobile-label">Save & add</span>
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
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

const emit = defineEmits(['update:draft', 'apply', 'apply-add', 'cancel', 'recent'])
const editorError = ref('')
const completionTrace = ref(null)
const autoFilledFields = ref([])
const fieldError = reactive({ field: '', message: '' })
const dateInput = ref(null)
const amountInput = ref(null)
const partyField = ref(null)
const categoryField = ref(null)
const subcategoryField = ref(null)
const paymentField = ref(null)
const transferAccountField = ref(null)
const transferPaymentField = ref(null)
const valueDateInput = ref(null)
const advancedFields = ref(null)

function clone(value) {
  if (typeof structuredClone === 'function') return structuredClone(value)
  return JSON.parse(JSON.stringify(value))
}

const localDraft = reactive(clone(props.draft))

watch(
  localDraft,
  value => emit('update:draft', clone(value)),
  { deep: true, flush: 'sync' },
)

const title = computed(() => localDraft.isNew ? 'New transaction' : 'Edit transaction')
const isTransfer = computed(() => normalizeName(localDraft.categoryName) === normalizeName(TRANSFER_CATEGORY))
const categoryChoices = computed(() => [
  { id: '__transfer__', name: TRANSFER_CATEGORY, isTransfer: true, secondary: 'Account transfer' },
  ...props.snapshot.categories,
])
const transferAccounts = computed(() => props.snapshot.accounts
  .filter(item => !item.closed && String(item.id) !== String(props.snapshot.account.id)))
const currentCategory = computed(() => props.snapshot.categories.find(item =>
  String(item.id) === String(localDraft.categorySelectionId ?? '')
  || normalizeName(item.name) === normalizeName(localDraft.categoryName)))
const subcategoryChoices = computed(() => currentCategory.value?.subcategories ?? [])
const sourcePaymentChoices = computed(() => paymentMethodsForAmount(
  props.snapshot,
  props.snapshot.account.id,
  localDraft.amount,
))
const targetAccount = computed(() => transferAccounts.value.find(item =>
  String(item.id) === String(localDraft.transferAccountSelectionId ?? '')
  || normalizeName(item.name) === normalizeName(localDraft.subcategoryName)))
const targetPaymentChoices = computed(() => targetAccount.value
  ? paymentMethodsForAmount(props.snapshot, targetAccount.value.id, String(-Number(localDraft.amount)))
  : [])
const oppositeAmount = computed(() => {
  const amount = Number(localDraft.amount)
  if (!Number.isFinite(amount)) return '—'
  return `${(-amount).toFixed(props.snapshot.account.currency.precision)} ${props.snapshot.account.currency.code}`
})
const checked = computed({
  get: () => Number(localDraft.marked) === 1,
  set: value => setDraftMarked(localDraft, value),
})

function fieldInvalid(field) {
  return fieldError.field === field
}

function clearFieldError(field) {
  if (fieldError.field !== field) return
  fieldError.field = ''
  fieldError.message = ''
  editorError.value = ''
}

function inferErrorField(message) {
  const text = String(message ?? '')
  if (/^Date\b/u.test(text)) return 'date'
  if (/^Value date\b/u.test(text)) return 'valueDate'
  if (/^Amount\b/u.test(text)) return 'amount'
  if (/^Party\b/u.test(text)) return 'partyName'
  if (/^Category\b/u.test(text) || /^A subcategory\b/u.test(text)) return 'categoryName'
  if (/^Subcategory\b/u.test(text)) return 'subcategoryName'
  if (/^Destination account\b/u.test(text) || /^Select a destination account\b/u.test(text)) return 'transferAccount'
  if (/^Destination payment method\b/u.test(text)) return 'transferPaymentMethodName'
  if (/^Payment method\b/u.test(text)) return 'paymentMethodName'
  if (/marked|checked|unchecked|reconciled|telepointed/iu.test(text)) return 'marked'
  return ''
}

async function focusInvalidField(field) {
  if (!field) return
  if (field === 'valueDate') advancedFields.value.open = true
  await nextTick()
  const targets = {
    date: dateInput.value,
    valueDate: valueDateInput.value,
    amount: amountInput.value,
    partyName: partyField.value,
    categoryName: categoryField.value,
    subcategoryName: subcategoryField.value,
    paymentMethodName: paymentField.value,
    transferAccount: transferAccountField.value,
    transferPaymentMethodName: transferPaymentField.value,
  }
  targets[field]?.focus?.()
}

function remember(kind, item) {
  if (item?.id != null) emit('recent', { kind, id: String(item.id) })
}

function isAutoFilled(field) {
  return autoFilledFields.value.includes(field)
}

function partyInput(value) {
  clearFieldError('partyName')
  updateSelectionText(localDraft, 'party', value, props.snapshot.parties)
  completionTrace.value = null
  autoFilledFields.value = []
}

function partySelected(item) {
  clearFieldError('partyName')
  setSelectedItem(localDraft, 'party', item)
  remember('party', item)
  completionTrace.value = applyPartyCompletionTrace(localDraft, props.snapshot)
  autoFilledFields.value = completionTrace.value?.fields ?? []
  onAmountDirectionChanged(localDraft, props.snapshot)
  syncSelectionIds(localDraft, props.snapshot)
}

function partyCreated(value) { partyInput(value) }
function partyCleared() { partyInput('') }

function categoryInput(value) {
  clearFieldError('categoryName')
  updateSelectionText(localDraft, 'category', value, categoryChoices.value)
  resetCategoryDependentFields(localDraft)
}

function categorySelected(item) {
  clearFieldError('categoryName')
  setSelectedItem(localDraft, 'category', item)
  remember('category', item)
  onAmountDirectionChanged(localDraft, props.snapshot)
  syncSelectionIds(localDraft, props.snapshot)
}

function categoryCreated(value) { categoryInput(value) }
function categoryCleared() { categoryInput('') }

function subcategoryInput(value) {
  clearFieldError('subcategoryName')
  updateSelectionText(localDraft, 'subcategory', value, subcategoryChoices.value)
}

function subcategorySelected(item) {
  clearFieldError('subcategoryName')
  setSelectedItem(localDraft, 'subcategory', item)
  remember('subcategory', item)
}

function subcategoryCreated(value) { subcategoryInput(value) }
function subcategoryCleared() { subcategoryInput('') }

function sourcePaymentInput(value) {
  clearFieldError('paymentMethodName')
  updateSelectionText(localDraft, 'payment', value, sourcePaymentChoices.value)
}

function sourcePaymentSelected(item) {
  clearFieldError('paymentMethodName')
  setSelectedItem(localDraft, 'payment', item)
  remember('payment', item)
}

function sourcePaymentCleared() { sourcePaymentInput('') }

function transferAccountInput(value) {
  clearFieldError('transferAccount')
  updateSelectionText(localDraft, 'transferAccount', value, transferAccounts.value)
  resetTransferPaymentFields(localDraft)
}

function transferAccountSelected(item) {
  clearFieldError('transferAccount')
  setSelectedItem(localDraft, 'transferAccount', item)
  remember('transferAccount', item)
  onAmountDirectionChanged(localDraft, props.snapshot)
  syncSelectionIds(localDraft, props.snapshot)
}

function transferAccountCleared() { transferAccountInput('') }

function targetPaymentInput(value) {
  clearFieldError('transferPaymentMethodName')
  updateSelectionText(localDraft, 'transferPayment', value, targetPaymentChoices.value)
}

function targetPaymentSelected(item) {
  clearFieldError('transferPaymentMethodName')
  setSelectedItem(localDraft, 'transferPayment', item)
  remember('transferPayment', item)
}

function targetPaymentCleared() { targetPaymentInput('') }

function amountChanged() {
  clearFieldError('amount')
  onAmountDirectionChanged(localDraft, props.snapshot)
  syncSelectionIds(localDraft, props.snapshot)
}

function undoCompletion() {
  undoPartyCompletion(localDraft, completionTrace.value, props.snapshot)
  completionTrace.value = null
  autoFilledFields.value = []
}

async function apply(addAnother) {
  editorError.value = ''
  fieldError.field = ''
  fieldError.message = ''
  try {
    buildResponsiveMutationOperations([localDraft], props.snapshot)
  } catch (error) {
    editorError.value = error.message
    fieldError.field = inferErrorField(error.message)
    fieldError.message = error.message
    await focusInvalidField(fieldError.field)
    return
  }
  emit(addAnother ? 'apply-add' : 'apply', clone(localDraft))
}
</script>

<style scoped>
.editor-backdrop { position: absolute; z-index: 80; inset: 0; overflow: hidden; background: rgb(0 0 0 / 24%); }
.transaction-panel { position: absolute; inset-block: 0; inset-inline-end: 0; width: min(540px, 94vw); display: grid; grid-template-rows: auto minmax(0, 1fr) auto; background: var(--color-main-background); box-shadow: -8px 0 28px rgb(0 0 0 / 22%); }
.panel-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; min-height: 48px; padding: 6px 12px; border-bottom: 1px solid var(--color-border); }
.panel-header h2 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 1.12rem; }
.icon-button { flex: none; width: 38px; height: 38px; border: 0; border-radius: 50%; background: transparent; font-size: 25px; cursor: pointer; }
.icon-button:hover { background: var(--color-background-hover); }
.panel-body { min-height: 0; overflow-y: auto; padding: 14px 16px; display: grid; align-content: start; gap: 15px; }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.common-fields > :nth-child(n + 3) { grid-column: 1 / -1; }
label { display: grid; gap: 6px; min-width: 0; font-weight: 600; }
label input, label textarea { width: 100%; min-height: 40px; box-sizing: border-box; font-weight: 400; }
label textarea { resize: vertical; padding: 8px; }
label.invalid input, .marked-field.invalid { border-color: var(--color-error); }
label.invalid input { box-shadow: 0 0 0 1px var(--color-error); }
.field-error { color: var(--color-error-text); font-weight: 500; }
.note-field { display: grid; }
.autofilled { padding: 7px; margin: -7px; border-radius: var(--border-radius); background: var(--color-primary-light); }
.completion-notice, .editor-error { display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 9px 11px; border-radius: var(--border-radius-large); }
.completion-notice { background: var(--color-primary-light); }
.editor-error { background: var(--color-error-light); color: var(--color-error-text); }
.transfer-section { display: grid; gap: 12px; padding: 12px; border: 1px solid var(--color-primary-element); border-radius: var(--border-radius-large); }
.section-heading { display: flex; justify-content: space-between; gap: 12px; }
.section-heading h3, .section-heading p { margin: 0; }
.section-heading p { opacity: .7; }
.transfer-summary { margin: 0; padding-top: 9px; border-top: 1px solid var(--color-border); }
.marked-field { display: grid; gap: 8px; padding: 1px; border: 1px solid transparent; border-radius: var(--border-radius); font-weight: 600; }
.checkbox-label { display: flex; align-items: center; gap: 9px; font-weight: 400; }
.checkbox-label input { width: 22px; height: 22px; min-height: 0; }
.locked-state { padding: 9px 11px; border-radius: var(--border-radius); background: var(--color-background-dark); }
.advanced-fields { border-top: 1px solid var(--color-border); padding-top: 10px; }
.advanced-fields summary { cursor: pointer; font-weight: 600; margin-bottom: 12px; }
.panel-footer { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-top: 1px solid var(--color-border); background: var(--color-main-background); }
.panel-footer button { flex: 1 1 0; min-width: 0; min-height: 40px; padding: 6px 8px; white-space: nowrap; }
.panel-footer .primary { background: var(--color-primary-element); color: var(--color-primary-element-text); border-color: transparent; }
.mobile-label { display: none; }
@media (max-width: 700px) {
  .editor-backdrop { background: var(--color-main-background); }
  .transaction-panel { width: 100%; inset: 0; box-shadow: none; }
  .panel-header { min-height: 44px; padding: 4px 8px 4px 12px; }
  .panel-body { padding: 11px 12px; gap: 12px; }
  .field-grid { grid-template-columns: 1fr; gap: 10px; }
  .common-fields > * { grid-column: 1; }
  label input, label textarea { min-height: 44px; font-size: 16px; }
  .panel-footer { position: sticky; bottom: 0; gap: 4px; padding: 6px; }
  .panel-footer button { min-height: 43px; padding: 5px 4px; font-size: .86rem; }
  .desktop-label { display: none; }
  .mobile-label { display: inline; }
}
</style>
