<script setup lang="ts">
import { reactive, ref } from 'vue'

import type { DeliveryZone, DeliveryZoneInput } from '@/types'
import { normalizeUsPostalCode } from '@/utils/usAddressValidation'

const props = defineProps<{
  zones: DeliveryZone[]
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  saveZone: [payload: DeliveryZoneInput, zoneId?: string]
  deleteZone: [zoneId: string]
}>()

const form = reactive<DeliveryZoneInput>({
  zip_code: '',
  flat_fee_cents: 0,
  is_active: true,
})

const formError = ref<string | null>(null)
const zipError = ref<string | null>(null)
const feeError = ref<string | null>(null)

function clearErrors() {
  formError.value = null
  zipError.value = null
  feeError.value = null
}

function clearZipError() {
  zipError.value = null
  formError.value = null
}

function clearFeeError() {
  feeError.value = null
  formError.value = null
}

function validateForm(): DeliveryZoneInput | null {
  clearErrors()

  const zipCode = normalizeUsPostalCode(form.zip_code)
  const fee = Number(form.flat_fee_cents)

  if (!/^\d{5}$/.test(zipCode)) {
    zipError.value = 'ZIP must be a 5-digit US ZIP code (e.g., 10001).'
  }

  if (!Number.isInteger(fee) || fee < 0 || fee > 99_999) {
    feeError.value = 'Flat fee must be a whole number of cents between 0 and 99,999.'
  }

  if (zipError.value || feeError.value) {
    formError.value = 'Fix delivery-zone form errors before saving.'
    return null
  }

  return {
    zip_code: zipCode,
    flat_fee_cents: fee,
    is_active: form.is_active,
  }
}

function save(zoneId?: string) {
  const payload = validateForm()
  if (!payload) {
    return
  }

  emit('saveZone', payload, zoneId)
}

function edit(zone: DeliveryZone) {
  form.zip_code = zone.zip_code
  form.flat_fee_cents = zone.flat_fee_cents
  form.is_active = zone.is_active
  clearErrors()
}
</script>

<template>
  <section class="zone-manager">
    <header>
      <h3>Delivery zones</h3>
      <p>ZIP-based flat fees for active event/store.</p>
    </header>

    <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>

    <div class="zone-manager__form">
      <label>
        ZIP
        <input
          v-model="form.zip_code"
          :disabled="loading || saving"
          :aria-invalid="Boolean(zipError) || undefined"
          maxlength="10"
          placeholder="10001"
          @input="clearZipError"
        />
        <small v-if="zipError" class="field-error">{{ zipError }}</small>
      </label>
      <label>
        Flat fee (cents)
        <input
          v-model.number="form.flat_fee_cents"
          :disabled="loading || saving"
          :aria-invalid="Boolean(feeError) || undefined"
          type="number"
          min="0"
          step="1"
          @input="clearFeeError"
        />
        <small v-if="feeError" class="field-error">{{ feeError }}</small>
      </label>
      <label class="checkbox">
        <input v-model="form.is_active" :disabled="loading || saving" type="checkbox" /> Active
      </label>
      <button type="button" :disabled="loading || saving" @click="save()">Create / upsert zone</button>
    </div>

    <ul>
      <li v-for="zone in zones" :key="zone.id">
        <span>
          <strong>{{ zone.zip_code }}</strong> · ${{ (zone.flat_fee_cents / 100).toFixed(2) }}
          · {{ zone.is_active ? 'active' : 'inactive' }}
        </span>
        <div>
          <button type="button" class="secondary" :disabled="loading || saving" @click="edit(zone)">Edit</button>
          <button type="button" class="secondary" :disabled="loading || saving" @click="save(zone.id)">Save edit</button>
          <button type="button" class="danger" :disabled="loading || saving" @click="emit('deleteZone', zone.id)">Delete</button>
        </div>
      </li>
      <li v-if="zones.length === 0">No delivery zones configured.</li>
    </ul>
  </section>
</template>

<style scoped>
.zone-manager {
  border: 1px solid rgba(18, 36, 58, 0.16);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.94);
  padding: 1rem;
  display: grid;
  gap: 0.8rem;
}

h3 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

header p {
  margin: 0.35rem 0 0;
  color: #2f4b67;
}

.zone-manager__form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.55rem;
  align-items: end;
}

label {
  display: grid;
  gap: 0.2rem;
  font-size: 0.82rem;
  color: #2b4561;
}

input {
  border: 1px solid rgba(30, 51, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.4rem 0.5rem;
}

button {
  border: none;
  border-radius: 0.5rem;
  background: #1d4673;
  color: #fff;
  padding: 0.42rem 0.66rem;
  cursor: pointer;
}

.secondary {
  background: rgba(22, 34, 55, 0.1);
  color: #1f3450;
}

.danger {
  background: #7c2342;
}

ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

li {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
}

li > div {
  display: flex;
  gap: 0.35rem;
}

.form-error {
  margin: 0;
  color: #8a1e35;
  font-size: 0.82rem;
}

.field-error {
  color: #8a1e35;
  font-size: 0.72rem;
}
</style>
