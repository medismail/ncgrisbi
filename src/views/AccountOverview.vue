<template>
  <div class="account-list">
    <h2>Accounts Overview</h2>

    <template v-if="loading">
      <NcLoadingIcon :size="32" />
      <p>Loading accounts...</p>
    </template>

    <template v-else>
      <NcEmptyContent
        v-if="accounts.length === 0"
        :icon="Bank"
      >
        <template #desc>
          <p>No accounts found. Add an account to get started.</p>
        </template>
      </NcEmptyContent>

      <h3
        v-for="(value, key) in total"
        :key="key"
      >
        Total in {{ key }}: {{ formatCurrency(value, key, languageCode).formatted }}<br>
        Total Pointed: {{ formatCurrency(totalMarked[key], key, languageCode).formatted }}<br>
      </h3>

      <ul class="account-grid">
        <li
          v-for="account in accounts"
          :key="account.id"
          class="account-card"
        >
          <h3>{{ account.name }}</h3>
          <p>Type: {{ account.type }}</p>
          Total: 
          <p
            class="account-balance"
            :class="{ negative: Math.round(account.total.total_amount) < 0 }"
          >
            {{ formatCurrency(account.total.total_amount,account.currency, languageCode).formatted }}
          </p>
          Total Pointed: 
          <p
            class="account-balance"
            :class="{ negative: Math.round(account.total.total_marked_amount) < 0 }"
          >
            {{ formatCurrency(account.total.total_marked_amount,account.currency,languageCode).formatted }}
          </p>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
import {
  NcEmptyContent,
  NcLoadingIcon
} from '@nextcloud/vue'

import { ref, computed, watch } from 'vue'
import Bank from 'vue-material-design-icons/Bank.vue'
import { formatCurrency } from '@/utils/format'
import { useStore } from 'vuex'
import { getLanguage } from '@nextcloud/l10n'

const store = useStore()
const loading = ref(true)
const total = ref({})
const totalMarked = ref({})
const languageCode = ref('en')

const accounts = computed(() => store.state.accounts)

const calculateTotals = (accounts) => {
  const tempTotal = accounts.reduce((acc, account) => {
    acc[account.currency] = (acc[account.currency] || 0) + account.total.total_amount
    return acc
  }, {})
  const tempTotalMarked = accounts.reduce((acc, account) => {
    acc[account.currency] = (acc[account.currency] || 0) + account.total.total_marked_amount
    return acc
  }, {})
  total.value = tempTotal
  totalMarked.value = tempTotalMarked
}

watch(accounts, (newAccounts) => {
    if ((newAccounts)&&(newAccounts.length > 0)) {
      calculateTotals(newAccounts)
      languageCode.value = getLanguage()
    }
    loading.value = false
  },
  { once: true }
)

</script>

<style scoped>
.account-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  list-style: none;
  padding: 0;
}

.account-card {
  background: var(--color-background-darker);
  border-radius: 8px;
  padding: 1rem;
  transition: box-shadow 0.2s;
}

.account-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.account-balance {
  font-size: 1.2em;
  font-weight: 600;
  color: green;
}

.account-balance.negative {
  color: var(--color-error);
}
</style>
