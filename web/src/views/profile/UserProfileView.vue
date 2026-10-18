<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'vue-toastification'
import api from '@/api'
import { useAuthStore } from '@/stores'

const { t } = useI18n()
const toast = useToast()
const authStore = useAuthStore()

// 当前登录用户名，仅用于展示
const userName = ref('')
// 新密码与确认
const newPassword = ref('')
const confirmPassword = ref('')
const isNewPasswordVisible = ref(false)
const isConfirmPasswordVisible = ref(false)
const saving = ref(false)

// 与后端一致的复杂度要求：字母、数字、特殊字符至少两项，长度大于 6
const PASSWORD_PATTERN = /^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$/

const passwordValid = computed(() => PASSWORD_PATTERN.test(newPassword.value))
const canSubmit = computed(
  () => passwordValid.value && newPassword.value === confirmPassword.value,
)

/**
 * 读取当前登录用户，仅用于展示用户名。
 */
async function fetchCurrentUser() {
  try {
    const result = await api.get('user/current')
    userName.value = result?.data?.name || ''
  }
  catch {
    // 读取失败保持空白，不影响改密
  }
}

/**
 * 提交新的登录密码，成功后要求重新登录。
 */
async function savePassword() {
  if (!passwordValid.value) {
    toast.warning(t('profile.passwordRule'))
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    toast.warning(t('profile.passwordMismatch'))
    return
  }
  saving.value = true
  try {
    const response = await api.put('user/', { password: newPassword.value })
    const result = response?.data
    if (result?.success) {
      toast.success(t('profile.passwordSaved'))
      newPassword.value = ''
      confirmPassword.value = ''
      // 密码已变更，清空登录状态并要求重新登录
      authStore.logout()
      window.location.href = '/login'
    }
    else {
      toast.error(result?.message || t('profile.passwordSaveFailed'))
    }
  }
  catch (error: any) {
    toast.error(error?.message || t('profile.passwordSaveFailed'))
  }
  finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchCurrentUser()
})
</script>

<template>
  <div>
    <VRow>
      <VCol cols="12" md="8" lg="6">
        <VCard :title="t('profile.loginCredential')">
          <VCardSubtitle class="px-4 pb-2">
            {{ t('profile.loginCredentialDesc') }}
          </VCardSubtitle>
          <VCardText>
            <VRow>
              <VCol cols="12">
                <VTextField
                  v-model="userName"
                  density="comfortable"
                  readonly
                  :label="t('user.username')"
                  prepend-inner-icon="mdi-account"
                />
              </VCol>
              <VCol cols="12">
                <VTextField
                  v-model="newPassword"
                  density="comfortable"
                  :type="isNewPasswordVisible ? 'text' : 'password'"
                  :append-inner-icon="isNewPasswordVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                  clearable
                  :label="t('user.password')"
                  :hint="t('profile.passwordRule')"
                  persistent-hint
                  autocomplete="new-password"
                  prepend-inner-icon="mdi-lock"
                  @click:append-inner="isNewPasswordVisible = !isNewPasswordVisible"
                />
              </VCol>
              <VCol cols="12">
                <VTextField
                  v-model="confirmPassword"
                  density="comfortable"
                  :type="isConfirmPasswordVisible ? 'text' : 'password'"
                  :append-inner-icon="isConfirmPasswordVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                  clearable
                  :label="t('user.confirmPassword')"
                  autocomplete="new-password"
                  prepend-inner-icon="mdi-lock-check"
                  @click:append-inner="isConfirmPasswordVisible = !isConfirmPasswordVisible"
                />
              </VCol>
            </VRow>

            <VBtn
              color="primary"
              class="mt-6"
              :loading="saving"
              :disabled="!canSubmit"
              prepend-icon="mdi-content-save"
              @click="savePassword"
            >
              {{ t('common.save') }}
            </VBtn>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>
  </div>
</template>
