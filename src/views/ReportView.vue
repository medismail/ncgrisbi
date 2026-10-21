<template>
  <main class="report-view">
    <div v-if="loading" class="report-state" role="status">
      <NcLoadingIcon :size="32" />
      <p>Calculating report…</p>
    </div>
    <NcEmptyContent
      v-else-if="error"
      name="Unable to display report"
      :description="error"
    >
      <template #action>
        <NcButton @click="loadReport">Retry</NcButton>
      </template>
    </NcEmptyContent>
    <template v-else-if="snapshot">
      <header class="report-header">
        <div>
          <h1>{{ reportName }}</h1>
          <p>{{ periodLabel }}</p>
        </div>
        <NcButton @click="toggleAll">
          {{ allExpanded ? 'Hide all transactions' : 'Show all transactions' }}
        </NcButton>
      </header>
      <p v-if="pendingChanges" class="draft-warning" role="status">
        This report uses saved transactions. Unsaved account edits are not included.
      </p>
      <section
        v-for="section in sections"
        :key="section.key"
        class="report-section"
        :aria-label="section.title"
      >
        <header class="section-heading">
          <h2>{{ section.title }}</h2>
          <strong :class="section.key">{{ money(snapshot[section.key].total) }}</strong>
        </header>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Category / Subcategory</th>
                <th scope="col" class="numeric">Transactions</th>
                <th scope="col" class="numeric">Amount</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(category, ci) in snapshot[section.key].categories" :key="`${section.key}-${ci}`">
                <tr class="category-row">
                  <th scope="row">
                    <button
                      type="button"
                      class="expand"
                      :aria-expanded="categoryIsExpanded(section.key, ci)"
                      @click="toggleCategory(section.key, ci)"
                    >
                      <span aria-hidden="true">{{ categoryIsExpanded(section.key, ci) ? '▾' : '▸' }}</span>
                      {{ category.name }}
                    </button>
                  </th>
                  <td class="numeric">{{ category.count }}</td>
                  <td class="numeric">{{ money(category.amount) }}</td>
                </tr>
                <template v-if="categoryIsExpanded(section.key, ci)">
                  <template v-for="(leaf, li) in category.subcategories" :key="`${section.key}-${ci}-${li}`">
                  <tr class="subcategory-row">
                    <th scope="row">
                      <button
                        class="expand indent"
                        type="button"
                        :aria-expanded="isExpanded(leafKey(section.key, ci, li))"
                        @click="toggleLeaf(leafKey(section.key, ci, li))"
                      >
                        <span aria-hidden="true">{{ isExpanded(leafKey(section.key, ci, li)) ? '▾' : '▸' }}</span>
                        {{ leaf.name }}
                      </button>
                    </th>
                    <td class="numeric">{{ leaf.count }}</td>
                    <td class="numeric">{{ money(leaf.amount) }}</td>
                  </tr>
                  <template v-if="isExpanded(leafKey(section.key, ci, li))">
                    <tr v-for="txIndex in leaf.transactions" :key="`tx-${section.key}-${ci}-${li}-${txIndex}`" class="transaction-row">
                      <td>{{ transactionDescription(txIndex) }}</td>
                      <td class="numeric"></td>
                      <td class="numeric">{{ transactionAmount(txIndex) }}</td>
                    </tr>
                  </template>
                </template>
                </template>
              </template>
              <template v-if="snapshot[section.key].uncategorized">
                <tr class="category-row">
                  <th scope="row">
                    <button
                      class="expand"
                      type="button"
                      :aria-expanded="isExpanded(`${section.key}-uncategorized`)"
                      @click="toggleLeaf(`${section.key}-uncategorized`)"
                    >
                      <span aria-hidden="true">{{ isExpanded(`${section.key}-uncategorized`) ? '▾' : '▸' }}</span>
                      No category
                    </button>
                  </th>
                  <td class="numeric">{{ snapshot[section.key].uncategorized.count }}</td>
                  <td class="numeric">{{ money(snapshot[section.key].uncategorized.amount) }}</td>
                </tr>
                <template v-if="isExpanded(`${section.key}-uncategorized`)">
                  <tr
                    v-for="txIndex in snapshot[section.key].uncategorized.transactions"
                    :key="`tx-${section.key}-none-${txIndex}`"
                    class="transaction-row"
                  >
                    <td>{{ transactionDescription(txIndex) }}</td>
                    <td class="numeric"></td>
                    <td class="numeric">{{ transactionAmount(txIndex) }}</td>
                  </tr>
                </template>
              </template>
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Total {{ section.title.toLowerCase() }}</th>
                <td class="numeric">{{ snapshot[section.key].count }}</td>
                <td class="numeric">{{ money(snapshot[section.key].total) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
      <footer class="difference">
        <div>
          <h2>Final difference</h2>
          <p>Income − Expenses</p>
        </div>
        <strong :class="{ negative: Number(snapshot.difference) < 0 }">
          {{ money(snapshot.difference) }}
        </strong>
      </footer>
    </template>
  </main>
</template>

<script setup>
import { NcButton, NcEmptyContent, NcLoadingIcon } from '@nextcloud/vue'
import { getLanguage } from '@nextcloud/l10n'
import { computed, reactive, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { apiError, fetchReportSnapshot } from '../services/gsbApi'

const props = defineProps({
  id: { type: String, required: true },
})
const store = useStore()
const language = getLanguage()
const loading = ref(false)
const error = ref('')
const snapshot = ref(null)
const expanded = reactive({})
const collapsedCategories = reactive({})
let requestNumber = 0
const sections = [
  { key: 'income', title: 'Income' },
  { key: 'expenses', title: 'Expenses' },
]
const reportName = computed(() => store.state.reports.find(
  item => String(item.id) === String(props.id)
)?.name || 'Report')
const pendingChanges = computed(() => store.state.transactionPending.active)
const periodLabel = computed(() => {
  const period = snapshot.value?.period
  if (!period) return ''
  if (!period.from && !period.to) return 'All dates'
  return [period.from || 'Beginning', period.to || 'Today'].join(' – ')
})

function money(value) {
  const currency = snapshot.value?.currency || 'EUR'
  const number = Number(value)
  if (!Number.isFinite(number)) return String(value)
  try {
    return new Intl.NumberFormat(language, { style: 'currency', currency }).format(number)
  } catch {
    return `${value} ${currency}`
  }
}

function leafKey(side, ci, li) {
  return `${side}-${ci}-${li}`
}

function isExpanded(key) {
  return Boolean(expanded[key])
}

function toggleLeaf(key) {
  expanded[key] = !isExpanded(key)
}

function categoryKey(side, ci) {
  return `${side}-${ci}`
}

function categoryIsExpanded(side, ci) {
  return !collapsedCategories[categoryKey(side, ci)]
}

function toggleCategory(side, ci) {
  const key = categoryKey(side, ci)
  collapsedCategories[key] = !collapsedCategories[key]
}

const expansionKeys = computed(() => {
  if (!snapshot.value) return []
  const keys = []
  for (const { key } of sections) {
    snapshot.value[key].categories.forEach((cat, ci) => {
      cat.subcategories.forEach((_, li) => keys.push(leafKey(key, ci, li)))
    })
    if (snapshot.value[key].uncategorized) keys.push(`${key}-uncategorized`)
  }
  return keys
})
const allExpanded = computed(() =>
  expansionKeys.value.length > 0
  && expansionKeys.value.every(isExpanded)
  && sections.every(({ key }) => snapshot.value[key].categories.every(
    (_, ci) => categoryIsExpanded(key, ci)
  ))
)
function toggleAll() {
  const next = !allExpanded.value
  expansionKeys.value.forEach(key => { expanded[key] = next })
  if (next) {
    // Show all transactions also reveals any previously collapsed subcategories.
    for (const key of Object.keys(collapsedCategories)) delete collapsedCategories[key]
  }
}

function transaction(txIndex) {
  return snapshot.value?.transactions?.[txIndex] || null
}
function transactionDescription(txIndex) {
  const tx = transaction(txIndex)
  if (!tx) return ''
  return [tx.date, tx.payee || `Transaction ${tx.id}`].filter(Boolean).join(' · ')
}
function transactionAmount(txIndex) {
  const tx = transaction(txIndex)
  return tx ? money(tx.amount) : ''
}

async function loadReport() {
  const serial = ++requestNumber
  snapshot.value = null
  error.value = ''
  loading.value = true
  for (const key of Object.keys(expanded)) delete expanded[key]
  for (const key of Object.keys(collapsedCategories)) delete collapsedCategories[key]
  try {
    if (!store.state.filePath) throw new Error('Select a Grisbi file before opening reports.')
    const result = await fetchReportSnapshot({
      reportId: props.id,
      filePath: store.state.filePath,
      filePassword: store.state.filePassword,
    })
    if (serial === requestNumber) snapshot.value = result.snapshot
  } catch (cause) {
    if (serial === requestNumber) error.value = apiError(cause).message
  } finally {
    if (serial === requestNumber) loading.value = false
  }
}

watch(() => [props.id, store.state.filePath], loadReport, { immediate: true })
</script>

<style scoped>
.report-view { display: grid; gap: 20px; padding: 20px; min-width: 0; }
.report-state { min-height: 240px; display: grid; place-content: center; justify-items: center; gap: 10px; }
.report-header, .section-heading, .difference { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.report-header { flex-wrap: wrap; }
.report-header h1 { margin: 0; font-size: 1.5rem; }
.report-header p, .difference p { margin: 4px 0 0; color: var(--color-text-maxcontrast); }
.report-section { display: grid; gap: 10px; min-width: 0; }
.section-heading h2, .difference h2 { margin: 0; font-size: 1.2rem; }
.section-heading strong { font-size: 1.3rem; font-variant-numeric: tabular-nums; }
.income { color: var(--color-success-text); }
.expenses, .negative { color: var(--color-error-text); }
.table-scroll { overflow-x: auto; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); }
table { width: 100%; border-collapse: collapse; min-width: 420px; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); text-align: left; }
thead, tfoot { background: var(--color-background-dark); }
tbody th { font-weight: normal; }
.category-row { font-weight: 600; background: var(--color-background-hover); }
.subcategory-row { color: var(--color-main-text); }
.transaction-row { color: var(--color-text-maxcontrast); font-size: .9rem; }
.transaction-row td:first-child { padding-left: 48px; }
.numeric { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.expand { text-align: left; display: inline-flex; align-items: center; gap: 8px; width: 100%; padding: 3px 0; border: 0; background: transparent; color: inherit; cursor: pointer; font: inherit; }
.expand:focus-visible { outline: 2px solid var(--color-primary-element); }
.indent { padding-left: 20px; }
.difference { padding: 18px; border-top: 2px solid var(--color-border); }
.difference strong { font-size: 1.6rem; font-variant-numeric: tabular-nums; }
.draft-warning { padding: 10px 14px; border: 1px solid var(--color-warning); border-radius: var(--border-radius); }
@media (max-width: 600px) { .report-view { padding: 12px; } .difference { padding: 12px 0; } }
</style>
