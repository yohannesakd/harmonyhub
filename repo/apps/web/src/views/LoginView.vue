<script setup lang="ts">
import { useRouter } from 'vue-router'

import LoginForm from '@/components/auth/LoginForm.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

async function handleSubmit(payload: { username: string; password: string; totpCode?: string }) {
  try {
    await authStore.signIn(payload.username, payload.password, payload.totpCode)
    await router.replace('/dashboard')
  } catch {
    // Errors are surfaced by store state.
  }
}
</script>

<template>
  <section class="login-page">
    <aside class="login-page__story">
      <p class="label">HarmonyHub Access</p>
      <h1>One secure surface for cast, concessions, and event operations.</h1>
      <ul>
        <li>Multi-tenant context isolation</li>
        <li>Offline sync-aware operations workflow</li>
        <li>Policy-first masking posture</li>
      </ul>
    </aside>

    <div class="login-page__card">
      <h2>Sign in</h2>
      <p class="hint">Use your assigned HarmonyHub account credentials.</p>
      <p v-if="authStore.isMfaRequired" class="hint" role="status" aria-live="polite" aria-atomic="true">
        Multi-factor authentication is required for this account. Enter your current TOTP code.
      </p>
      <LoginForm :mfa-required="authStore.isMfaRequired" @submit="handleSubmit" />
      <p v-if="authStore.errorMessage" class="error" role="alert" aria-live="assertive" aria-atomic="true">
        {{ authStore.errorMessage }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 1.2rem;
  padding: clamp(1rem, 3vw, 2rem);
}

.login-page__story,
.login-page__card {
  border-radius: 1rem;
  padding: clamp(1rem, 2.5vw, 2rem);
}

.login-page__story {
  background: radial-gradient(circle at 15% 10%, rgba(87, 29, 140, 0.82), rgba(11, 34, 69, 0.92));
  color: #f3efe4;
  display: grid;
  align-content: center;
  gap: 0.8rem;
}

.label {
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-family: 'Fraunces', serif;
  font-size: clamp(1.5rem, 3vw, 2.35rem);
}

ul {
  margin: 0;
  padding-left: 1.2rem;
  line-height: 1.8;
}

.login-page__card {
  background: rgba(248, 247, 243, 0.92);
  border: 1px solid rgba(21, 40, 68, 0.16);
  box-shadow: 0 15px 30px rgba(17, 24, 39, 0.12);
  align-self: center;
}

h2 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

.hint {
  margin: 0.3rem 0 1.2rem;
  color: #425776;
  font-size: 0.88rem;
}

.error {
  margin-top: 1rem;
  color: #8a1e35;
  font-size: 0.86rem;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }
}
</style>
