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
            class="checkbox-wrapper-13"
            :class="{ 'even-row': index % 2 === 0, 'odd-row': index % 2!== 0, 'bright-row': !transaction.isEditing }"
          >
            <td><strong>{{ transaction['Transaction Number'] }}</strong></td>
            <td>
              <input
                v-model="transaction.Date"
                type="text"
                :disabled="!transaction.isEditing"
              >
            </td>
            <td>
              <input
                v-model="transaction.Amount"
                type="number"
                :disabled="!transaction.isEditing"
              >
            </td>
            <td>
              <input
                v-model="transaction.Party"
                list="Partes"
                :disabled="!transaction.isEditing"
              >
              <datalist id="Partes">
                <option
                  v-for="party in parties"
                  :key="party.id"
                  :value="party.name"
                >
                  {{ party.name }}
                </option>
              </datalist>
            </td>
            <td>
              <input
                v-model="transaction.Category"
                type="text"
                :disabled="!transaction.isEditing"
              > (<input
                v-model="transaction.Subcategory"
                type="text"
                :disabled="!transaction.isEditing"
              >)
            </td>
            <td>
              <input
                v-model="transaction['Payment Method']"
                list="Payment_methods"
                :disabled="!transaction.isEditing"
              >
              <datalist id="Payment_methods">
                <option
                  v-for=" payment_method in transactions.payment_methods"
                  :key="payment_method.id"
                  :value="payment_method.name"
                >
                  {{ payment_method.name }}
                </option>
              </datalist>
            </td>
            <td>
              <input
                v-model="transaction.Note"
                type="text"
                :disabled="!transaction.isEditing"
              >
            </td>
            <td>
              <input
                type="checkbox"
                :checked="transaction.Marked === 1"
                :disabled="!transaction.isEditing"
                @change="transaction.Marked = $event.target.checked ? 1 : 0"
              >
            </td>
            <td>
              <input
                type="text"
                :value="transaction['Bank Reference']"
                :disabled="!transaction.isEditing"
                @input="event => transaction['Bank Reference'] = event.target.value"
              >
            </td>

            <td>
              <input
                v-model="transaction['Split Transaction']"
                type="checkbox"
                :disabled="!transaction.isEditing"
              >
            </td>
            <td>
              <button
                v-if="!transaction.isEditing"
                @click="transaction.isEditing = true"
              >
                Edit
              </button>
              <button
                v-else
                @click="saveTransaction(transaction)"
              >
                Save
              </button>
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
const parties = ref([])

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

// Fetch parties from API
const fetchParties = async () => {
  const data = { filePath: store.state.filePath, filePassword: store.state.filePassword };
  const jsonData = JSON.stringify(data);
  const requestOptions = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: jsonData,
  };
  try {
    const response = await fetch('/apps/ncgrisbi/api/parties', requestOptions);
    const data = await response.json();
    parties.value = data;
  } catch (error) {
    console.error('Failed to fetch parties:', error);
  }
};

// Call fetchTransactions function when component is mounted
onMounted(fetchParties);
onMounted(fetchTransactions)

// Watch for changes to route.params.id and refetch transactions if it changes
watch(() => route.params.id, (newId) => {
  selectedAccountId.value = newId
  fetchTransactions()
})

const saveTransaction = async (transaction) => {
  const data = {
    filePath: store.state.filePath,
    filePassword: store.state.filePassword,
    transactionDataJson: JSON.stringify(transaction), // Send the transaction object as a JSON string
  };

  const requestOptions = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  };

  try {
    const response = await fetch('/apps/ncgrisbi/api/savetransaction', requestOptions);
    if (response.ok) {
      transaction.isEditing = false; // Exit edit mode on successful save
    }
  } catch (error) {
    console.error('Failed to save transaction:', error);
  }
};

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
    'Bank Reference': null,
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

.bright-row input{
 color: #ffffff;
 border-color: #bbbbbb;
}

.checkbox-wrapper-13 input[type=checkbox] {
      --active: #275EFE;
      --active-inner: #fff;
      --focus: 2px rgba(39, 94, 254, .3);
      --border: #BBC1E1;
      --border-hover: #275EFE;
      --background: #fff;
      --disabled: #F6F8FF;
      --disabled-inner: #E1E6F9;
      -webkit-appearance: none;
      -moz-appearance: none;
      height: 21px;
      min-height: 21px;
      outline: none;
      display: inline-block;
      vertical-align: top;
      position: relative;
      margin: 0;
      cursor: pointer;
      border: 1px solid var(--bc, var(--border));
      background: var(--b, var(--background));
      transition: background 0.3s, border-color 0.3s, box-shadow 0.2s;
}
.checkbox-wrapper-13 input[type=checkbox]:after {
    content: "";
      display: block;
      left: 0;
      top: 0;
      position: absolute;
      transition: transform var(--d-t, 0.3s) var(--d-t-e, ease), opacity var(--d-o, 0.2s);
}
.checkbox-wrapper-13 input[type=checkbox]:checked {
      --b: var(--active);
      --bc: var(--active);
      --d-o: .3s;
      --d-t: .6s;
      --d-t-e: cubic-bezier(.2, .85, .32, 1.2);
}
.checkbox-wrapper-13 input[type=checkbox]:disabled {
      --b: var(--disabled);
      cursor: not-allowed;
      opacity: 0.9;
}
.checkbox-wrapper-13 input[type=checkbox]:disabled:checked {
      --b: #1b307e;
      --bc: var(--border);
}
.checkbox-wrapper-13 input[type=checkbox]:disabled + label {
      cursor: not-allowed;
}
.checkbox-wrapper-13 input[type=checkbox]:hover:not(:checked):not(:disabled) {
      --bc: var(--border-hover);
}
.checkbox-wrapper-13 input[type=checkbox]:focus {
      box-shadow: 0 0 0 var(--focus);
}
.checkbox-wrapper-13 input[type=checkbox]:not(.switch) {
      width: 21px;
}
.checkbox-wrapper-13 input[type=checkbox]:not(.switch):after {
      opacity: var(--o, 0);
}
.checkbox-wrapper-13 input[type=checkbox]:not(.switch):checked {
      --o: 1;
}
.checkbox-wrapper-13 input[type=checkbox] + label {
      display: inline-block;
      vertical-align: middle;
      cursor: pointer;
      margin-left: 4px;
}

.checkbox-wrapper-13 input[type=checkbox]:not(.switch) {
      border-radius: 7px;
}
.checkbox-wrapper-13 input[type=checkbox]:not(.switch):after {
      width: 5px;
      height: 9px;
      border: 2px solid var(--active-inner);
      border-top: 0;
      border-left: 0;
      left: 7px;
      top: 4px;
      transform: rotate(var(--r, 20deg));
}
.checkbox-wrapper-13 input[type=checkbox]:not(.switch):checked {
      --r: 43deg;
}

.checkbox-wrapper-13 * {
    box-sizing: inherit;
}
.checkbox-wrapper-13 *:before,
.checkbox-wrapper-13 *:after {
    box-sizing: inherit;
}

</style>
