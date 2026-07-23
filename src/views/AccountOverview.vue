<template>
  <section class="account-overview" aria-labelledby="accounts-overview-title">
    <header class="overview-header">
      <div>
        <h1 id="accounts-overview-title">Accounts overview</h1>
        <p>{{ accounts.length }} account{{ accounts.length === 1 ? '' : 's' }}</p>
      </div>
    </header>

    <NcEmptyContent v-if="!accounts.length" :icon="Bank">
      <template #desc>
        <p>No accounts were found in this Grisbi file.</p>
      </template>
    </NcEmptyContent>

    <template v-else>
      <section class="currency-totals" aria-label="Totals by currency">
        <article v-for="summary in currencyTotals" :key="summary.currency" class="summary-card">
          <span>{{ summary.currency }}</span>
          <strong>{{ money(summary.total, summary.currency) }}</strong>
          <small>Checked: {{ money(summary.marked, summary.currency) }}</small>
          <small>Difference: {{ money(summary.total - summary.marked, summary.currency) }}</small>
        </article>
      </section>

      <ul class="account-grid">
        <li v-for="account in accounts" :key="account.id">
          <RouterLink
            :to="`/account/${account.id}`"
            class="account-card"
            :aria-label="`Open ${account.name} transactions`"
          >
            <header>
              <component :is="accountIcon(account)" :size="24" aria-hidden="true" />
              <div>
                <h2>{{ account.name }}</h2>
                <p>{{ accountType(account.type) }}</p>
              </div>
            </header>

            <dl>
              <div>
                <dt>Balance</dt>
                <dd :class="{ negative: number(account.total?.total_amount) < 0 }">
                  {{ money(account.total?.total_amount, currencyCode(account)) }}
                </dd>
              </div>
              <div>
                <dt>Checked</dt>
                <dd :class="{ negative: number(account.total?.total_marked_amount) < 0 }">
                  {{ money(account.total?.total_marked_amount, currencyCode(account)) }}
                </dd>
              </div>
              <div>
                <dt>Difference</dt>
                <dd :class="{ negative: accountDifference(account) < 0 }">
                  {{ money(accountDifference(account), currencyCode(account)) }}
                </dd>
              </div>
            </dl>
          </RouterLink>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup>
import { NcEmptyContent } from '@nextcloud/vue'
import AccountCreditCard from 'vue-material-design-icons/AccountCreditCard.vue'
import Bank from 'vue-material-design-icons/Bank.vue'
import Cash from 'vue-material-design-icons/Cash.vue'
import CreditCard from 'vue-material-design-icons/CreditCard.vue'
import { computed } from 'vue'
import { useStore } from 'vuex'
import { getLanguage } from '@nextcloud/l10n'

const store = useStore()
const languageCode = getLanguage()
const accounts = computed(() => Array.isArray(store.state.accounts) ? store.state.accounts : [])

function number(value) {
  const result = Number(value)
  return Number.isFinite(result) ? result : 0
}

function currencyCode(account) {
  return String(account?.currency?.code ?? account?.currency ?? 'EUR')
}

function money(amount, currency) {
  return new Intl.NumberFormat(languageCode, {
    style: 'currency',
    currency,
  }).format(number(amount))
}

function accountDifference(account) {
  return number(account.total?.total_amount) - number(account.total?.total_marked_amount)
}

function accountType(type) {
  const labels = {
    BANK: 'Bank account',
    ASSET: 'Asset account',
    LIABILITIES: 'Liability account',
    CASH: 'Cash account',
  }
  return labels[type] ?? 'Account'
}

function accountIcon(account) {
  if (account.type === 'BANK') return Bank
  if (account.type === 'ASSET') return AccountCreditCard
  if (account.type === 'LIABILITIES') return CreditCard
  return Cash
}

const currencyTotals = computed(() => {
  const totals = new Map()
  for (const account of accounts.value) {
    const currency = currencyCode(account)
    const current = totals.get(currency) ?? { currency, total: 0, marked: 0 }
    current.total += number(account.total?.total_amount)
    current.marked += number(account.total?.total_marked_amount)
    totals.set(currency, current)
  }
  return [...totals.values()].sort((left, right) => left.currency.localeCompare(right.currency))
})
</script>

<style scoped>
.account-overview { display: grid; gap: 18px; min-width: 0; padding: 18px; }
.overview-header { display: flex; align-items: end; justify-content: space-between; gap: 16px; }
.overview-header h1, .overview-header p { margin: 0; }
.overview-header h1 { font-size: 1.5rem; }
.overview-header p { margin-top: 4px; color: var(--color-text-maxcontrast); }
.currency-totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
.summary-card { display: grid; gap: 4px; padding: 14px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); background: var(--color-background-dark); }
.summary-card > span { color: var(--color-text-maxcontrast); font-weight: 600; }
.summary-card strong { font-size: 1.25rem; }
.summary-card small { color: var(--color-text-maxcontrast); }
.account-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; margin: 0; padding: 0; list-style: none; }
.account-card { display: grid; gap: 16px; height: 100%; padding: 16px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); background: var(--color-main-background); color: var(--color-main-text); text-decoration: none; box-sizing: border-box; transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease; }
.account-card:hover, .account-card:focus-visible { border-color: var(--color-primary-element); box-shadow: 0 4px 14px rgb(0 0 0 / 12%); transform: translateY(-1px); outline: none; }
.account-card header { display: flex; align-items: center; gap: 11px; }
.account-card h2, .account-card p { margin: 0; }
.account-card h2 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 1.08rem; }
.account-card p { color: var(--color-text-maxcontrast); font-size: .88rem; }
dl { display: grid; gap: 9px; margin: 0; }
dl > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
dt { color: var(--color-text-maxcontrast); }
dd { margin: 0; font-variant-numeric: tabular-nums; font-weight: 700; text-align: end; }
dd.negative { color: var(--color-error-text); }
@media (max-width: 600px) {
  .account-overview { padding: 12px; }
  .account-grid { grid-template-columns: 1fr; }
}
</style>
