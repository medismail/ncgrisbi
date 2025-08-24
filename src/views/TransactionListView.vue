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
          <strong>Total Amount:</strong> {{ formatCurrency(transactions.total_amount, transactions.currency.name, languageCode).formatted }}
        </li>
        <li>
          <strong>Total Marked Amount:</strong> {{ formatCurrency(transactions.total_marked_amount, transactions.currency.name, languageCode).formatted }}
        </li>
      </ul>
      <h3>Transactions:</h3>
      <button @click="addNewTransaction">
        Add Transaction
      </button>
      <button @click="saveTransactions">
        Save Transactions
      </button>
      <button @click="fetchTransactions">
        Cancel changes
      </button>
      <!-- scroll container -->
      <div class="grid-scroll">
        <div class="transaction-wrapper">
          <div class="grid-row header">
            <span class="col-n">#</span>
            <span class="col-date">Date</span>
            <span class="col-amount">Amount</span>
            <span class="col-party">Party</span>
            <span class="col-cat">Category (SubCategory)</span>
            <span class="col-pm">Payment Method</span>
            <span class="col-note">Note</span>
            <span class="col-mark">Marked</span>
            <span class="col-bref">Bank Ref.</span>
            <span class="col-split">Split</span>
            <span class="col-actions">Actions</span>
          </div>
          <DynamicScroller
            class="scroller"
            :items="reversedTransactions"
            :min-item-size="48"
            key-field="Transaction Number"
          >
            <template #default="{ item: t, index, active }">
              <DynamicScrollerItem
                tag="div"
                class="grid-row body checkbox-wrapper-13"
                :class="{ 'bright-row': !t.isEditing }"
                :item="t"
                :active="active"
                :data-index="index"
              >
                <span class="col-n">{{ t['Transaction Number'] }}</span>
                <span class="col-date"><input
                  v-model="t.Date"
                  :disabled="!t.isEditing"
                ></span>
                <span class="col-amount"><input
                  v-model="t.Amount"
                  type="number"
                  :disabled="!t.isEditing"
                ></span>
                <span class="col-party"><input
                                          v-model="t.Party"
                                          :list="'P-'+index"
                                          :disabled="!t.isEditing"
                                          @input="() => onPartyChange(t)"
                                        >
                  <datalist :id="'P-'+index">
                    <option
                      v-for="party in parties"
                      :key="party.id"
                      :value="party.name"
                    > {{ party.name }}
                    </option>
                  </datalist>
                </span>
                <span class="col-cat">
                  <input
                    v-model="t.Category"
                    :list="'C-'+index"
                    :disabled="!t.isEditing"
                    @input="t.Subcategory=''"
                  >
                  <datalist :id="'C-'+index">
                    <option
                      v-for="c in categories"
                      :key="c.id"
                      :value="c.name"
                    > {{ c.name }}
                    </option>
                  </datalist>
                  (<input
                    v-model="t.Subcategory"
                    :list="'S-'+index"
                    :disabled="!t.isEditing"
                  >)
                  <datalist :id="'S-'+index">
                    <option
                      v-for="s in subCategories(t)"
                      :key="s.id"
                      :value="s.name"
                    > {{ s.name }}
                    </option>
                  </datalist>
                </span>
                <span class="col-pm"><input
                                       v-model="t['Payment Method']"
                                       :list="'PM-'+index"
                                       :disabled="!t.isEditing"
                                     >
                  <datalist :id="'PM-'+index">
                    <option
                      v-for=" payment_method in transactions.payment_methods"
                      :key="payment_method.id"
                      :value="payment_method.name"
                    > {{ payment_method.name }}
                    </option>
                  </datalist>
                </span>
                <span class="col-note"><input
                  v-model="t.Note"
                  :value="convertNullStringToEmpty(t.Note)"
                  :disabled="!t.isEditing"
                ></span>
                <span class="col-mark"><input
                  type="checkbox"
                  :checked="t.Marked===1"
                  :disabled="!t.isEditing"
                  @change="t.Marked = $event.target.checked ? 1 : 0"
                ></span>
                <span class="col-bref"><input
                  v-model="t['Bank Reference']"
                  :disabled="!t.isEditing"
                ></span>
                <span class="col-split"><input
                  v-model="t['Split Transaction']"
                  :disabled="!t.isEditing"
                ></span>
                <span class="col-actions">
                  <button
                    v-if="!t.isEditing"
                    @click="editTransaction(t)"
                  >Edit</button>
                  <button
                    v-else
                    @click="deleteTransaction(t['Transaction Number'])"
                  >Delete</button>
                </span>
              </DynamicScrollerItem>
            </template>
          </DynamicScroller>
        </div>
      </div>
    </template>
  </NcAppContent>
</template>

<script setup>
import { NcAppContent, NcLoadingIcon } from '@nextcloud/vue'
import { ref, onMounted, watch, computed } from 'vue'
import { formatCurrency } from '@/utils/format'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { getLanguage } from '@nextcloud/l10n'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
const store = useStore()
const route = useRoute()
const transactions = ref({})
//const reversedTransactions = computed(() => transactions.value.transactions.slice().reverse())
const reversedTransactions = computed(() => [...transactions.value.transactions].reverse())
const loading = ref(true)
const selectedAccountId = ref(route.params.id)
const hasUnsavedChanges = ref(false)
const languageCode = ref('en')
const parties = ref([])
const categories = ref([])
const categoryMap = computed(() => {
  const map = new Map()
  categories.value.forEach(c => map.set(c.name, c.subcategories || []))
  return map
})
const subCategories = transaction => categoryMap.value.get(transaction.Category) ?? []
var transactionsDelete = []

// Fetch transactions from API
const fetchTransactions = async (accountId) => {
  // Check for unsaved changes before fetching new transactions
 if (hasUnsavedChanges.value) {
    if (await showConfirmationDialog()) {
      // If user chooses to save, wait for save to complete before fetching
 await saveTransactions()
    } else {
      // If user cancels the dialog or chooses not to save, don't fetch
      return
    }
  }
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
    hasUnsavedChanges.value = false // Reset unsaved changes flag
    // Initialize isEditing property for each transaction
    if (data && data.transactions) {
      data.transactions.forEach(transaction => {
        transaction.isEditing = false
      })
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

// Fetch categories from API
// Fetch categories from API
const fetchCategories = async () => {
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
    const response = await fetch('/apps/ncgrisbi/api/categories', requestOptions);
    const data = await response.json();
    categories.value = data;
  } catch (error) {
    console.error('Failed to fetch categories:', error);
  }
};

// Show confirmation dialog
const showConfirmationDialog = async () => {
  return new Promise((resolve) => {
    const confirmed = confirm('You have unsaved changes. Do you want to save them before switching accounts?');
    resolve(confirmed);
  });
}

// Call fetchTransactions function when component is mounted
onMounted(fetchParties);
onMounted(fetchCategories);
onMounted(fetchTransactions)

// Watch for changes to route.params.id and refetch transactions if it changes
// Watch for changes to route.params.id and refetch transactions if it changes
watch(() => route.params.id, async (newId) => {
  if (hasUnsavedChanges.value) {
    if (await showConfirmationDialog()) {
      await saveTransactions()
    }
  }
  selectedAccountId.value = newId
  fetchTransactions(newId)
})
watch(() => route.params.id, (newId) => {
  selectedAccountId.value = newId
  fetchTransactions()
})

const saveTransactions = async () => {
  loading.value = true
  const formatedTransactions = []
  const transactionsList = transactions.value.transactions.filter((t) => t.isEditing)
  if (transactionsList.length > 0 || transactionsDelete.length > 0) {
    transactionsList.forEach(transaction => {
      const subcategoryList = subCategories(transaction)
      const formatedTransaction = {
        'Ac': selectedAccountId.value,
        'Nb': transaction['Transaction Number'],
        'Id': "(null)",
        'Dt': transaction['Date'],
        'Dv': "(null)",
        'Cu': transactions.value.currency.id,
        'Am': transaction['Amount'].toString(),
        'Exb': "0",
        'Exr': "0.00",
        'Exf': "0.00",
        'Pa': getTransactionElementId(parties.value, transaction['Party']),
        'Ca': getTransactionElementId(categories.value, transaction['Category']),
        'Sca': getTransactionElementId(subcategoryList, transaction['Subcategory']),
        'Br': transaction['Bank Reference'],
        'No': convertEmptyStringToNull(transaction['Note']),
        'Pn': getTransactionElementId(transactions.value.payment_methods, transaction['Payment Method']),
        'Pc': "(null)",
        'Ma': transaction['Marked'].toString(),
        'Ar': "0",
        'Au': "0",
        'Re': "0",
        'Fi': "0",
        'Bu': "0",
        'Sbu': "0",
        'Vo': "(null)",
        'Ba': "(null)",
        'Trt': transaction['Split Transaction'],
        'Mo': "0"
      }
      formatedTransactions.push(formatedTransaction)
    })

    transactionsDelete.forEach(number => {
      const formatedTransaction = {
        'Nb': number,
        'Delete': "True"
      }
      formatedTransactions.push(formatedTransaction)
    })
    const data = {
      filePath: store.state.filePath,
      filePassword: store.state.filePassword,
      transactionDataJson: JSON.stringify(formatedTransactions), // Send the transaction object as a JSON string
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
        transactionsList.forEach(transaction => {
          transaction.isEditing = false; // Exit edit mode on successful save
          transactions.value.total_amount = transactions.value.total_amount - transaction.originalAmount + transaction.Amount;
          if (transaction.Marked !== transaction.originalMarked) {
            transactions.value.total_marked_amount = transactions.value.total_marked_amount + transaction.Amount
          }
        })
        hasUnsavedChanges.value = false // Reset unsaved changes flag after successful save
        transactionsDelete = []
      }
    } catch (error) {
      console.error('Failed to save transaction:', error);
    }
  }
  loading.value = false
};

// Edit transaction
function editTransaction(t) {
  t.isEditing=true
  t.originalAmount = t.Amount; // Store original amount
  t.originalMarked = t.Marked; // Store original marked status
    transactions.value.total_marked_amount = transactions.value.total_marked_amount - t.Amount
  }
}

// Format date
const formatDate = () => {
  const current = new Date()
  const month = (current.getMonth() + 1).toString().padStart(2, '0')
  const day = current.getDate().toString().padStart(2, '0')
  const year = current.getFullYear()
  return `${month}/${day}/${year}`;
}

// Convert null string to empty string
function convertNullStringToEmpty(str) {
    return str === "(null)" ? "" : str;
}

// Convert empty string to null string
function convertEmptyStringToNull(str) {
    return str === "" ? "(null)" : str;
}

// Add new transaction
const addNewTransaction = () => {
  const newTransaction = {
    'Transaction Number': transactions.value.next_id.toString(),
    Date: formatDate(),
    Amount: 0,
    Currency: 'EUR',
    Party: '',
    Category: '',
    Subcategory: '',
    'Payment Method': '',
    Note: '',
    Marked: 0,
    'Bank Reference': "0",
    'Split Transaction': "0",
    isEditing: true // New transactions are in edit mode by default
  }
  hasUnsavedChanges.value = true // Mark as unsaved changes when adding a new transaction
  transactions.value.next_id = transactions.value.next_id + 1
  transactions.value.transactions.push(newTransaction)
}

// Update Amount Category ans SubCategory on Party changes
function onPartyChange(t) {
  const party = parties.value.find(p => p.name === t.Party)
  if (party) {
    if (t.Amount == 0) { 
      t.Amount = party.last_amount
    }
    if (t.Category == '') {
      t.Category = party.last_category
    }
    if (t.Subcategory == '') {
      t.Subcategory = party.last_subcategory
    }
  }
}

// Get transaction element ID
function getTransactionElementId(g, n) {
  const r = g.find(e => e.name === n)
  return r ? r.id : '0';
}

// Delete transaction
function deleteTransaction(number) {
  if (!transactionsDelete.includes(number)) transactionsDelete.push(number)
  const index = transactions.value.transactions.findIndex(t => t['Transaction Number'] === number)
  transactions.value.transactions.splice(index, 1)
}
</script>

<style scoped>
/* container for both header + body */
.transaction-wrapper {
  display: flex;
  flex-direction: column;
}

.grid-scroll {
  width: 100%;
  overflow-x: auto;   /* horizontal scroll when needed */
}
/* shared grid definition */ .grid-row {
  display: grid;
  grid-template-columns:
    60px               /* #        */
    120px              /* Date     */
    110px              /* Amount   */
    180px              /* Party    */
    340px              /* Category */
    150px              /* Pay-Meth */
    180px              /* Note     */
    60px               /* Marked   */
    140px              /* Bank Ref */
    140px              /* Split    */
    100px;             /* Actions  */
  align-items: center;
  gap: 4px;
}
/* header cosmetics */
.header {
  font-weight: bold;
  background: var(--color-background-dark); border-bottom: 1px solid var(--color-border);
  padding: 6px 4px;
}

/* body cosmetics */
.body:nth-child(even) { background: var(--color-background-darker); }
.body > span { padding: 4px; }

/* keep category + subcategory on one line inside the same cell */
.col-cat {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* scroller height */
.scroller {
  height: 400px;   /* or flex: 1 */
  width: 172%;
}

.bright-row input{
 color: #ffffff;
 border-color: #bbbbbb;
}

.col-amount input{
 text-align: right;
 width: 100px;
}

.col-party input{
 width: 170px;
}

.col-cat input{
 width: 150px;
}

.col-date input{
 width: 110px;
}

.col-pm input{
 width: 140px;
}

.col-note input{
 width: 170px;
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
