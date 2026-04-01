<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ mfaRequired: boolean }>()

const emit = defineEmits<{
  submit: [payload: { username: string; password: string; totpCode?: string }]
}>()

const username = ref('')
const password = ref('')
const totpCode = ref('')

function onSubmit() {
  emit('submit', {
    username: username.value,
    password: password.value,
    totpCode: props.mfaRequired ? totpCode.value : undefined,
  })
}
</script>

<template>
  <form class="login-form" @submit.prevent="onSubmit">
    <label class="login-form__field">
      <span>Username</span>
      <input
        v-model="username"
        name="username"
        autocomplete="username"
        autocapitalize="none"
        autocorrect="off"
        spellcheck="false"
        required
      />
    </label>

    <label class="login-form__field">
      <span>Password</span>
      <input v-model="password" name="password" type="password" autocomplete="current-password" required />
    </label>

    <label v-if="mfaRequired" class="login-form__field">
      <span>TOTP code</span>
      <input
        v-model="totpCode"
        name="totp_code"
        autocomplete="one-time-code"
        inputmode="numeric"
        pattern="[0-9]*"
        minlength="6"
        maxlength="8"
        placeholder="123456"
        required
      />
    </label>

    <button class="login-form__submit" type="submit">Sign in</button>
  </form>
</template>

<style scoped>
.login-form {
  display: grid;
  gap: 1rem;
}

.login-form__field {
  display: grid;
  gap: 0.45rem;
  font-size: 0.86rem;
}

input {
  padding: 0.65rem 0.7rem;
  border-radius: 0.6rem;
  border: 1px solid rgba(19, 30, 51, 0.25);
  background: rgba(255, 255, 255, 0.75);
}

.login-form__submit {
  margin-top: 0.45rem;
  border: none;
  border-radius: 0.7rem;
  background: linear-gradient(130deg, #1a4e8a, #5c1f82);
  color: #fff;
  padding: 0.72rem 1rem;
  cursor: pointer;
}
</style>
