<template>
  <NcAppNavigation>
    <template #list>
      <NcAppNavigationItem
        v-for="historyFile in historyFiles"
        :key="historyFile.name"
        :name="historyLabel(historyFile)"
        :title="historyFile.name"
        @click="openHistoryFile(historyFile)"
      >
        <template #icon>
          <File :size="20" />
        </template>
        <template #actions>
          <NcActionButton @click.stop="removeFromHistory(historyFile)">
            <template #icon>
              <Delete :size="20" />
            </template>
            Remove from history
          </NcActionButton>
        </template>
      </NcAppNavigationItem>
    </template>
  </NcAppNavigation>

  <NcAppContent class="history-content" app-name="ncgrisbi">
    <NcEmptyContent
      :name="historyFiles.length ? 'Recent Grisbi files' : 'Open a Grisbi file'"
      :description="historyDescription"
    >
      <template #icon>
        <File :size="64" />
      </template>
      <template #action>
        <NcButton :href="filesUrl" type="primary">
          Open Nextcloud Files
        </NcButton>
      </template>
    </NcEmptyContent>
  </NcAppContent>
</template>

<script setup>
import {
  NcActionButton,
  NcAppContent,
  NcAppNavigation,
  NcAppNavigationItem,
  NcButton,
  NcEmptyContent,
} from '@nextcloud/vue'
import { generateUrl } from '@nextcloud/router'
import Delete from 'vue-material-design-icons/Delete.vue'
import File from 'vue-material-design-icons/File.vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

const store = useStore()
const router = useRouter()
const storedHistory = ref([])
const filesUrl = generateUrl('/apps/files/')

const historyDescription = computed(() => historyFiles.value.length
  ? 'Choose a recent file from the navigation, or open another .gsb file from Nextcloud Files.'
  : 'Open a .gsb file from Nextcloud Files to start. It will then appear here for quick access.')

function safeParse(json) {
  if (!json) return []
  try {
    const parsed = JSON.parse(json)
    return Array.isArray(parsed)
      ? parsed.filter(item => item && typeof item.name === 'string' && item.name)
      : []
  } catch (error) {
    return []
  }
}

const historyFiles = computed(() => [...storedHistory.value].sort((left, right) => {
  const leftTime = Date.parse(left.openedAt ?? '') || 0
  const rightTime = Date.parse(right.openedAt ?? '') || 0
  return rightTime - leftTime || left.name.localeCompare(right.name)
}))

function basename(path) {
  return String(path).split('/').filter(Boolean).pop() || String(path)
}

function parentPath(path) {
  const parts = String(path).split('/').filter(Boolean)
  if (parts.length < 2) return '/'
  return `/${parts.slice(0, -1).join('/')}`
}

function historyLabel(file) {
  return `${basename(file.name)} — ${parentPath(file.name)}`
}

function persist(files) {
  storedHistory.value = files
  localStorage.setItem('historyfiles', JSON.stringify(files))
}

async function openHistoryFile(file) {
  const updated = [
    { ...file, openedAt: new Date().toISOString() },
    ...storedHistory.value.filter(item => item.name !== file.name),
  ]
  persist(updated)
  store.commit('setFilePath', file.name)
  store.commit('setFilePassword', '')
  store.commit('setAccounts', [])
  store.commit('setAccountsError', null)
  await router.push('/accounts')
}

function removeFromHistory(file) {
  if (!window.confirm(`Remove “${basename(file.name)}” from recent files? The Grisbi file itself will not be deleted.`)) {
    return
  }
  persist(storedHistory.value.filter(item => item.name !== file.name))
}

onMounted(() => {
  storedHistory.value = safeParse(localStorage.getItem('historyfiles'))
})
</script>

<style scoped>
.history-content { display: grid; place-items: center; min-height: 100%; padding: 20px; box-sizing: border-box; }
</style>
