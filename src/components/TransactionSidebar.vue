<!-- components/TransactionSidebar.vue -->
<template>
  <aside class="app-navigation">
    <h3>Transactions</h3>
    <ul>
      <li
        v-for="tx in transactions"
        :key="tx.id"
      >
        {{ tx.description }} - {{ tx.amount }}
      </li>
    </ul>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const transactions = ref([])

// Fetch transactions for current account
fetch(`/api/transactions/${route.params.id}`)
  .then(res => res.json())
  .then(data => transactions.value = data)
</script>
