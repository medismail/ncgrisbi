<template>
  <div class="wrapper">
    <NcPasswordField
      ref="pref"
      v-model="password"
      label="Enter Password"
      placeholder="Password placeholder"
      @keydown.enter="setFilePassword()"
    >
      <template #icon>
        <Key :size="20" />
      </template>
    </NcPasswordField>
    <NcButton
      text="Submit"
      @click="setFilePassword()"
    >
      <template #icon>
        <Send :size="20" />
      </template>
    </NcButton>
  </div>
</template>

<script setup>
import { NcPasswordField, NcButton } from '@nextcloud/vue'
import Key from 'vue-material-design-icons/Key'
import Send from 'vue-material-design-icons/Send.vue'
import { ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'

const store = useStore()
const router = useRouter()
const password = ref('')
const pref = ref(null)

function setFilePassword() {
  store.commit('setFilePassword', password.value)
  router.push('/accounts')
}

onMounted(() => {pref.value.focus()})

</script>

<style scoped>
.wrapper {
  display: grid;
  grid-template-columns: 1fr 1fr;
  justify-content: center;
  align-items: center;
  margin: 0 auto;
  gap: 10px;
}

.nc-password-field {
  grid-column: 1;
}

.nc-button {
  grid-column: 2;
  bottom: 4px
}
</style>
