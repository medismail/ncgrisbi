<template>
  <NcAppNavigation>
    <template #header>
      <NcAppNavigationNew placeholder="Add new account" />
    </template>
    <template #list>
      <NcAppNavigationItem
        v-for="account in accounts"
        :key="account.id"
        :name="account.name"
        :to="`/account/${account.id}`"
        :allow-collapse="true"
        :open="false"
      >
        <template #icon>
          <Bank v-if="account.type === 'BANK'" />
          <AccountCreditCard v-else-if="account.type === 'ASSET'" />
          <CreditCard v-else-if="account.type === 'LIABILITIES'" />
          <Cash v-else />
        </template>
        <template #default>
          <NcAppNavigationItem
            :name="formatCurrency(account.total.total_marked_amount,account.currency,languageCode).formatted"
          />
        </template>
      </NcAppNavigationItem>
    </template>
    <template #footer>
      <button @click="closeFile">
        Close File
      </button>
    </template>
  </NcAppNavigation>

  <NcAppContent
    id="app-content"
    app-name="ncgrisbi"
  >
    <router-view />
  </NcAppContent>
</template>

<script setup>
import {
  NcAppNavigation,
  NcAppContent,
  NcAppNavigationItem,
  NcAppNavigationNew
} from '@nextcloud/vue'

import { ref, onMounted } from 'vue'
import Bank from 'vue-material-design-icons/Bank.vue'
import AccountCreditCard from 'vue-material-design-icons/AccountCreditCard.vue'
import CreditCard from 'vue-material-design-icons/CreditCard.vue'
import Cash from 'vue-material-design-icons/Cash.vue'
import { formatCurrency } from '@/utils/format'
import { useStore } from 'vuex'
import { useRoute, useRouter } from 'vue-router'
import { getLanguage } from '@nextcloud/l10n'

const store = useStore()
const route = useRoute()
const router = useRouter()
const accounts = ref([])
const loading = ref(false)
const languageCode = ref('en')

const closeFile = () => {
  store.commit('setFilePath', '')
  store.commit('setFilePassword', '')
  router.push('/')
}
function safeParse(jsonStr) {
  if (!jsonStr) return []
  try {
    return JSON.parse(jsonStr)
  } catch (error) {
    return []
  }
}

function addToStorage(path) {
  const storedFiles = localStorage.getItem('historyfiles') || ''
  var historyfiles = safeParse(storedFiles)
  let newPath = { "name": path }
  var contains = historyfiles.some(elem =>{return JSON.stringify(newPath) === JSON.stringify(elem)})
  if (!contains) {
    historyfiles.push(newPath)
    localStorage.setItem('historyfiles', JSON.stringify(historyfiles))
  }
}

const fetchAccounts = async () => {
  loading.value = true
  languageCode.value = getLanguage()
  if (route.query && Object.keys(route.query).length > 0) {
    store.commit('setFilePath', route.query.file)
  }
  if (store.state.filePassword == '') {
    await store.dispatch('checkPassword')
    if (store.state.isEncrypted) {
      router.push('/typepass')
      return
    }
  }
  await store.dispatch('fetchAccounts')
  if (typeof store.state.accounts.Error !== 'undefined') {
    console.log(store.state.accounts.Error)
    router.push('/typepass')
  }
  accounts.value = store.state.accounts
  addToStorage(store.state.filePath)
  loading.value = false
}

onMounted(fetchAccounts)
</script>
