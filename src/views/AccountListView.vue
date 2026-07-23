<template>
  <NcAppNavigation>
    <template #list>
      <NcAppNavigationItem
        name="Accounts overview"
        :active="route.name === 'Accounts'"
        @click.prevent="openOverview"
      >
        <template #icon>
          <ViewDashboard :size="20" />
        </template>
      </NcAppNavigationItem>

      <NcAppNavigationItem
        v-for="account in accounts"
        :key="account.id"
        :name="account.name"
        :to="`/account/${account.id}`"
        :allow-collapse="true"
        :open="false"
      >
        <template #icon>
          <Bank v-if="account.type === 'BANK'" :size="20" />
          <AccountCreditCard v-else-if="account.type === 'ASSET'" :size="20" />
          <CreditCard v-else-if="account.type === 'LIABILITIES'" :size="20" />
          <Cash v-else :size="20" />
        </template>
        <template #default>
          <NcAppNavigationItem
            :name="accountTotalsLabel(account)"
            :title="accountTotalsLabel(account)"
          />
        </template>
      </NcAppNavigationItem>
    </template>

    <template #footer>
      <NcButton @click="closeFile">Close file</NcButton>
    </template>
  </NcAppNavigation>

  <NcAppContent id="app-content" app-name="ncgrisbi">
    <div v-if="initializing || loading" class="shell-state" role="status">
      <NcLoadingIcon :size="32" />
      <p>Loading Grisbi accounts…</p>
    </div>

    <NcEmptyContent
      v-else-if="accountError"
      name="Unable to load accounts"
      :description="accountError.message"
    >
      <template #icon>
        <AlertCircle :size="64" />
      </template>
      <template #action>
        <div class="error-actions">
          <NcButton @click="fetchAccounts">Retry</NcButton>
          <NcButton v-if="isEncrypted" @click="enterPassword">Enter password</NcButton>
          <NcButton @click="closeFile">Choose another file</NcButton>
        </div>
      </template>
    </NcEmptyContent>

    <router-view v-else />
  </NcAppContent>
</template>

<script setup>
import {
  NcAppContent,
  NcAppNavigation,
  NcAppNavigationItem,
  NcButton,
  NcEmptyContent,
  NcLoadingIcon,
} from '@nextcloud/vue'
import { getLanguage } from '@nextcloud/l10n'
import AccountCreditCard from 'vue-material-design-icons/AccountCreditCard.vue'
import AlertCircle from 'vue-material-design-icons/AlertCircle.vue'
import Bank from 'vue-material-design-icons/Bank.vue'
import Cash from 'vue-material-design-icons/Cash.vue'
import CreditCard from 'vue-material-design-icons/CreditCard.vue'
import ViewDashboard from 'vue-material-design-icons/ViewDashboard.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'

const store = useStore()
const route = useRoute()
const router = useRouter()
const initializing = ref(true)
const languageCode = getLanguage()

const accounts = computed(() => store.state.accounts)
const loading = computed(() => store.state.accountsLoading)
const accountError = computed(() => store.state.accountsError)
const isEncrypted = computed(() => store.state.isEncrypted)

function number(value) {
  const result = Number(value)
  return Number.isFinite(result) ? result : 0
}

function currencyCode(account) {
  return String(account?.currency?.code ?? account?.currency ?? 'EUR')
}

function money(value, account) {
  return new Intl.NumberFormat(languageCode, {
    style: 'currency',
    currency: currencyCode(account),
  }).format(number(value))
}

function accountTotalsLabel(account) {
  return `Total: ${money(account.total?.total_amount, account)} · Checked: ${money(account.total?.total_marked_amount, account)}`
}

function pendingDiscardPrompt(context) {
  const pending = store.state.transactionPending
  const details = pending.description || `${pending.total} pending transaction changes`
  return `${context} This will permanently discard ${details}. This cannot be undone.`
}

async function openOverview() {
  if (route.name !== 'Accounts') await router.push({ name: 'Accounts' })
}

async function closeFile() {
  if (store.state.transactionPending.active
    && !window.confirm(pendingDiscardPrompt('Close the current Grisbi file?'))) {
    return
  }
  store.commit('setTransactionPending', { active: false, total: 0, description: '' })
  store.commit('clearFileSession')
  await router.push('/')
}

function enterPassword() {
  router.push('/typepass')
}

function safeParse(json) {
  if (!json) return []
  try {
    const parsed = JSON.parse(json)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    return []
  }
}

function addToStorage(path) {
  if (!path) return
  const history = safeParse(localStorage.getItem('historyfiles'))
  const current = history.find(item => item?.name === path)
  const updated = [
    { ...current, name: path, openedAt: new Date().toISOString() },
    ...history.filter(item => item?.name !== path),
  ].slice(0, 30)
  localStorage.setItem('historyfiles', JSON.stringify(updated))
}

async function fetchAccounts() {
  try {
    await store.dispatch('fetchAccounts')
    addToStorage(store.state.filePath)
  } catch (error) {
    // The normalized error is exposed through store.state.accountsError.
  }
}

async function initialize() {
  initializing.value = true
  try {
    const queryFile = Array.isArray(route.query.file) ? route.query.file[0] : route.query.file
    if (queryFile) {
      store.commit('setFilePath', String(queryFile))
      store.commit('setFilePassword', '')
      store.commit('setAccounts', [])
    }

    if (!store.state.filePath) {
      store.commit('setAccountsError', {
        code: 'file-required',
        message: 'Select a Grisbi file from Nextcloud Files or recent files.',
      })
      return
    }

    const document = await store.dispatch('checkPassword')
    if (document.encrypted && !store.state.filePassword) {
      await router.replace('/typepass')
      return
    }
    await fetchAccounts()
  } catch (error) {
    // The normalized error is exposed through store.state.accountsError.
  } finally {
    initializing.value = false
  }
}

onMounted(initialize)
</script>

<style scoped>
.shell-state { display: grid; place-items: center; align-content: center; gap: 10px; min-height: 260px; }
.shell-state p { margin: 0; }
.error-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
</style>
