<template>
  <NcAppNavigation>
    <template #list>
      <NcAppNavigationItem
        v-for="histfile in historyfiles"
        :key="basename(histfile.name)"
        :name="basename(histfile.name)"
        to="/accounts"
        @click="setFilePath(histfile.name)"
      >
        <template #icon>
          <File />
        </template>
        <template #actions>
          <NcActionButton @click="delFromStorage(histfile.name)">
            <template #icon>
              <Delete :size="20" />
            </template>
            Delete
          </NcActionButton>
        </template>
      </NcAppNavigationItem>
    </template>
  </NcAppNavigation>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NcAppNavigation, NcAppNavigationItem, NcActionButton } from '@nextcloud/vue' 
import File from 'vue-material-design-icons/File.vue'
import Delete from 'vue-material-design-icons/Delete.vue'
import { useStore } from 'vuex'

const store = useStore()

const historyfiles = ref([])

function basename(str) {
  return str.split('/').reverse()[0]
}

function setFilePath(filePath) {
  store.commit('setFilePath', filePath)
}

function safeParse(jsonStr) {
  if (!jsonStr) return null;
  try {
    return JSON.parse(jsonStr);
  } catch (error) {
    return null;
  }
}

function delFromStorage(path) {
  const storedFiles = localStorage.getItem('historyfiles') || ''
  var historyFiles = safeParse(storedFiles)
  const index = historyFiles.findIndex(elem =>{return elem.name === path})
  if (index > -1) {
    historyFiles.splice(index, 1)
    localStorage.setItem('historyfiles', JSON.stringify(historyFiles))
    historyfiles.value = historyFiles
  }
}

const fetchHistoryfiles = () => {
  const storedFiles = localStorage.getItem('historyfiles') || ''
  historyfiles.value = safeParse(storedFiles)
}

onMounted(fetchHistoryfiles)
</script>
