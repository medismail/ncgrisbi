<template>
  <main class="password-page">
    <section class="password-card" aria-labelledby="password-title">
      <header>
        <Key :size="32" aria-hidden="true" />
        <div>
          <h1 id="password-title">Unlock Grisbi file</h1>
          <p>Enter the password used to encrypt this file.</p>
        </div>
      </header>

      <form @submit.prevent="submitPassword">
        <NcPasswordField
          ref="passwordField"
          v-model="password"
          label="File password"
          placeholder="Enter file password"
          autocomplete="current-password"
          :disabled="submitting"
          :aria-invalid="errorMessage ? 'true' : undefined"
          @update:model-value="clearError"
        >
          <template #icon>
            <Key :size="20" />
          </template>
        </NcPasswordField>

        <p v-if="errorMessage" class="password-error" role="alert">
          {{ errorMessage }}
        </p>

        <div class="password-actions">
          <NcButton
            text="Choose another file"
            :disabled="submitting"
            @click="chooseAnotherFile"
          />
          <NcButton
            :text="submitting ? 'Unlocking…' : 'Unlock'"
            :disabled="submitting || !password"
            native-type="submit"
          >
            <template #icon>
              <NcLoadingIcon v-if="submitting" :size="20" />
              <Send v-else :size="20" />
            </template>
          </NcButton>
        </div>
      </form>
    </section>
  </main>
</template>

<script setup>
import { NcButton, NcLoadingIcon, NcPasswordField } from '@nextcloud/vue'
import Key from 'vue-material-design-icons/Key.vue'
import Send from 'vue-material-design-icons/Send.vue'
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { apiError } from '@/services/gsbApi'

const store = useStore()
const router = useRouter()
const password = ref('')
const passwordField = ref(null)
const submitting = ref(false)
const errorMessage = ref('')

function clearError() {
  errorMessage.value = ''
}

async function submitPassword() {
  if (!password.value || submitting.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await store.dispatch('validateFilePassword', password.value)
    await router.replace('/accounts')
  } catch (error) {
    const failure = apiError(error)
    errorMessage.value = failure.code === 'invalid-password'
      ? 'The Grisbi file password is incorrect.'
      : failure.message
    password.value = ''
    await nextTick()
    passwordField.value?.focus?.()
  } finally {
    submitting.value = false
  }
}

async function chooseAnotherFile() {
  store.commit('clearFileSession')
  await router.push('/')
}

onMounted(async () => {
  if (!store.state.filePath) {
    await router.replace('/')
    return
  }
  await nextTick()
  passwordField.value?.focus?.()
})
</script>

<style scoped>
.password-page { display: grid; place-items: center; min-height: min(560px, 100%); padding: 20px; box-sizing: border-box; }
.password-card { display: grid; gap: 20px; width: min(460px, 100%); padding: 22px; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); background: var(--color-main-background); box-shadow: 0 6px 22px rgb(0 0 0 / 10%); box-sizing: border-box; }
.password-card header { display: flex; align-items: center; gap: 13px; }
.password-card h1, .password-card p { margin: 0; }
.password-card h1 { font-size: 1.35rem; }
.password-card header p { margin-top: 4px; color: var(--color-text-maxcontrast); }
.password-card form { display: grid; gap: 12px; }
.password-error { padding: 9px 11px; border-radius: var(--border-radius); background: var(--color-error-light); color: var(--color-error-text); }
.password-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
@media (max-width: 520px) {
  .password-page { padding: 12px; }
  .password-card { padding: 16px; }
  .password-actions { display: grid; grid-template-columns: 1fr; }
}
</style>
