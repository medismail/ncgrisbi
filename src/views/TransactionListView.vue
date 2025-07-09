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
          <strong>Total Amount:</strong> {{ formatCurrency(transactions.total_amount, transactions.currency, languageCode).formatted }}
        </li>
        <li>
          <strong>Total Marked Amount:</strong> {{ formatCurrency(transactions.total_marked_amount, transactions.currency, languageCode).formatted }}
        </li>
      </ul>
      <h3>Transactions:</h3>
      <table class="transaction-table">
        <thead>
          <tr>
            <th class="transaction-number">
              #
            </th>
            <th>Date</th>
            <th>Amount</th>
            <th>Party</th>
            <th>Category (Subcategory)</th>
            <th>Payment Method</th>
            <th>Note</th>
            <th>Marked</th>
            <th>Bank Reference</th>
            <th>Split Transaction</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(transaction, index) in transactions.transactions.slice().reverse()"
            :key="index"
            :class="{ 'even-row': index % 2 === 0, 'odd-row': index % 2!== 0 }"
          >
            <td><strong>{{ transaction['Transaction Number'] }}</strong></td>
            <td><input type="text" v-model="transaction.Date" :disabled="!transaction.isEditing" /></td>
            <td><input type="number" v-model="transaction.Amount" :disabled="!transaction.isEditing" /></td>
            <td><input type="text" v-model="transaction.Party" :disabled="!transaction.isEditing" /></td>
            <td><input type="text" v-model="transaction.Category" :disabled="!transaction.isEditing" /> (<input type="text" v-model="transaction.Subcategory" :disabled="!transaction.isEditing" />)</td>
            <td><input type="text" v-model="transaction['Payment Method']" :disabled="!transaction.isEditing" /></td>
            <td><input type="text" v-model="transaction.Note" :disabled="!transaction.isEditing" /></td>
            <td><input type="checkbox" v-model="transaction.Marked" :disabled="!transaction.isEditing" /></td>
            <td><input type="text" v-model="transaction['Bank Reference']" :disabled="!transaction.isEditing" /></td>
            <td><input type="checkbox" v-model="transaction['Split Transaction']" :disabled="!transaction.isEditing" /></td>
            <td>
              <button v-if="!transaction.isEditing" @click="transaction.isEditing = true">Edit</button>
              <button v-else @click="transaction.isEditing = false">Save</button>
            </td>
          </tr>
        </tbody>
      </table>
      <button @click="addNewTransaction">
        Add Transaction
      </button>
    </template>
  </NcAppContent>
</template>

<script setup>
import { NcAppContent, NcLoadingIcon } from '@nextcloud/vue'
import { ref, onMounted, watch } from 'vue'
import { formatCurrency } from '@/utils/format'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { getLanguage } from '@nextcloud/l10n'

const store = useStore()
const route = useRoute()
const transactions = ref({})
const loading = ref(true)
const selectedAccountId = ref(route.params.id)
const languageCode = ref('en')

// Fetch transactions from API
const fetchTransactions = async () => {
  loading.value = true

  languageCode.value = getLanguage()
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
    const data = await response.json();
    // Initialize isEditing property for each transaction
    if (data && data.transactions) {
      data.transactions.forEach(transaction => {
        transaction.isEditing = false;
      });
    }
    transactions.value = data;
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

const addNewTransaction = () => {
  const newTransaction = {
    'Transaction Number': transactions.value.transactions.length + 1, // Simple increment for now
    Date: '',
    Amount: 0,
    Party: '',
    Category: '',
    Subcategory: '',
    'Payment Method': '',
    Note: '',
    Marked: false,
    'Bank Reference': '',
    'Split Transaction': false,
    isEditing: true // New transactions are in edit mode by default
  }
  transactions.value.transactions.push(newTransaction)
}
</script>

<style scoped>
.transaction-table {
  border-collapse: collapse;
  width: 100%;
}

.transaction-table th,.transaction-table td {
  border: 1px solid #ccc;
  padding: 10px;
  text-align: left;
}

.transaction-number {
  max-width: 90px;
  white-space: normal;
}

.transaction-table tr td:nth-child(3) {
  text-align: right;
}

/*.transaction-table th {
  background-color: #f0f0f0;
}

.even-row {
  background-color: #f9f9f9;
}

.odd-row {
  background-color: #fff;
}*/
</style>
