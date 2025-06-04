<template>
  <NcAppContent>
    <template v-if="loading">
      <NcLoadingIcon :size="32" />
      <p>Loading Transactions...</p>
    </template>
    <template v-else>
      <h2>Account Information</h2>
      <ul>
        <li>
          <strong>Account Name:</strong> {{ transactions.account_name }}
        </li>
        <li>
          <strong>Account ID:</strong> {{ transactions.account_id }}
        </li>
      </ul>
      <h3>Totals:</h3>
      <ul>
        <li>
          <strong>Total Amount:</strong> {{ transactions.total_amount }}
        </li>
        <li>
          <strong>Total Marked Amount:</strong> {{ transactions.total_marked_amount }}
        </li>
      </ul>
      <h3>Transactions:</h3>
      <table>
        <thead>
          <tr>
            <th>Transaction Number</th>
            <th>Date</th>
            <th>Amount</th>
            <th>Party</th>
            <th>Category</th>
            <th>Subcategory</th>
            <th>Bank Reference</th>
            <th>Note</th>
            <th>Payment Method</th>
            <th>Marked</th>
            <th>Split Transaction</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="transaction in transactions.transactions.slice().reverse()"
            :key="transaction['Transaction Number']"
          >
            <td>{{ transaction['Transaction Number'] }}</td>
            <td>{{ transaction.Date }}</td>
            <td>{{ formatCurrency(transaction.Amount, transaction.Currency).formatted }}</td>
            <td>{{ transaction.Party }}</td>
            <td>{{ transaction.Category }}</td>
            <td>{{ transaction.Subcategory }}</td>
            <td>{{ transaction['Bank Reference'] }}</td>
            <td>{{ transaction.Note }}</td>
            <td>{{ transaction['Payment Method'] }}</td>
            <td>{{ transaction.Marked }}</td>
            <td>{{ transaction['Split Transaction'] }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </NcAppContent>
</template>

<script setup>
import { NcAppContent, NcLoadingIcon } from '@nextcloud/vue'
import { ref, onMounted, watch } from 'vue'
import { formatCurrency } from '@/utils/format'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'

const store = useStore()
const route = useRoute()
const transactions = ref({})
const loading = ref(true)
const selectedAccountId = ref(route.params.id)

// Fetch transactions from API
const fetchTransactions = async () => {
  loading.value = true

  const data = { filePath: store.state.filePath, filePassword: store.state.filePassword }
  const jsonData = JSON.stringify(data)
  const requestOptions = { 
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: jsonData
  }
  try {
    const response = await fetch('/apps/ncgrisbi/api/account/' + selectedAccountId.value, requestOptions)
    transactions.value = await response.json()
  } catch (error) {
    console.error('Failed to fetch transactions:', error)
  }
  loading.value = false
}

// Call fetchTransactions function when component is mounted
onMounted(fetchTransactions)

// Watch for changes to route.params.id and refetch transactions if it changes
watch(() => route.params.id, (newId) => {
  selectedAccountId.value = newId
  fetchTransactions()
})
</script>

<style scoped>
</style>
