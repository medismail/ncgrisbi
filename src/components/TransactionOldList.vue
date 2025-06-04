<template>
  <NcAppContent>
    <h3>Transactions for {{ accountId }}</h3>
    <p>Recent transactions for this account.</p>

    <template v-if="loading">
      <NcLoadingIcon :size="32" />
      <p>Loading transactions...</p>
    </template>

    <template v-else>
      <NcEmptyContent
        v-if="transactions.length === 0"
        :icon="Clock"
      >
        <template #desc>
          <p>No transactions found for this account.</p>
        </template>
      </NcEmptyContent>

      <table class="transactions-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Category</th>
            <th class="amount">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(transaction, index) in sortedTransactions"
            :key="index"
          >
            <td>{{ formatDate(transaction.date) }}</td>
            <td>{{ transaction.description }}</td>
            <td>{{ transaction.category }}</td>
            <td 
              class="amount"
              :class="{ negative: transaction.amount < 0 }"
            >
              {{ formatCurrency(transaction.amount) }}
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </NcAppContent>
</template>

<script setup>
import {
  NcAppContent,
  NcEmptyContent,
  NcLoadingIcon,
  Clock
} from '@nextcloud/vue'
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { formatCurrency, formatDate } from '@/utils/format'

const route = useRoute()
const transactions = ref([])
const loading = ref(false)
const accountId = ref(route.params.id)

const sortedTransactions = ref([])

const fetchTransactions = async () => {
  loading.value = true
  try {
    const response = await fetch(`/apps/ncgrisbi/api/transactions/${accountId.value}`)
    transactions.value = await response.json()
  } catch (error) {
    console.error('Failed to fetch transactions:', error)
  }
  loading.value = false
}

watch(
  () => route.params.id,
  (newId) => {
    accountId.value = newId
    fetchTransactions()
  }
)

onMounted(fetchTransactions)
</script>

<style scoped>
.transactions-table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.amount {
  text-align: right;
  font-weight: 600;
}

.negative {
  color: var(--color-error);
}
</style>
