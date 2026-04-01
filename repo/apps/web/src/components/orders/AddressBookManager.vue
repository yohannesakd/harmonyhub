<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import type { AddressBookEntry, AddressBookEntryInput, SyncStatus } from '@/types'
import {
  isValidUsPostalCode,
  isValidUsState,
  normalizeUsPhone,
  normalizeUsPostalCode,
  normalizeUsState,
} from '@/utils/usAddressValidation'

const props = defineProps<{
  addresses: AddressBookEntry[]
  loading: boolean
  saving: boolean
  syncStates?: Record<string, SyncStatus>
  syncErrors?: Record<string, string | null>
}>()

const emit = defineEmits<{
  create: [payload: AddressBookEntryInput]
  update: [addressId: string, payload: AddressBookEntryInput]
  delete: [addressId: string]
}>()

const editingId = ref<string | null>(null)
const formError = ref<string | null>(null)

type AddressField = 'label' | 'recipient_name' | 'line1' | 'city' | 'state' | 'postal_code' | 'phone'

const fieldErrors = reactive<Record<AddressField, string | null>>({
  label: null,
  recipient_name: null,
  line1: null,
  city: null,
  state: null,
  postal_code: null,
  phone: null,
})

const form = reactive<AddressBookEntryInput>({
  label: '',
  recipient_name: '',
  line1: '',
  line2: null,
  city: '',
  state: '',
  postal_code: '',
  phone: null,
  is_default: false,
})

function clearFieldError(field: AddressField) {
  fieldErrors[field] = null
  if (formError.value) {
    formError.value = null
  }
}

function clearAllErrors() {
  formError.value = null
  for (const key of Object.keys(fieldErrors) as AddressField[]) {
    fieldErrors[key] = null
  }
}

function resetForm() {
  editingId.value = null
  form.label = ''
  form.recipient_name = ''
  form.line1 = ''
  form.line2 = null
  form.city = ''
  form.state = ''
  form.postal_code = ''
  form.phone = null
  form.is_default = false
  clearAllErrors()
}

function editAddress(entry: AddressBookEntry) {
  editingId.value = entry.id
  form.label = entry.label
  form.recipient_name = entry.recipient_name
  form.line1 = entry.line1
  form.line2 = entry.line2
  form.city = entry.city
  form.state = entry.state
  form.postal_code = entry.postal_code
  form.phone = entry.phone
  form.is_default = entry.is_default
  clearAllErrors()
}

function buildValidatedPayload(): AddressBookEntryInput | null {
  clearAllErrors()

  const label = form.label.trim()
  const recipientName = form.recipient_name.trim()
  const line1 = form.line1.trim()
  const line2 = form.line2?.trim() || null
  const city = form.city.trim()
  const state = normalizeUsState(form.state)
  const postalCode = normalizeUsPostalCode(form.postal_code)
  const phoneRaw = form.phone?.trim() ?? ''
  const phone = phoneRaw.length > 0 ? normalizeUsPhone(phoneRaw) : null

  if (!label) {
    fieldErrors.label = 'Label is required.'
  }
  if (recipientName.length < 2) {
    fieldErrors.recipient_name = 'Recipient name is required (2+ characters).'
  }
  if (line1.length < 5 || !/[A-Za-z]/.test(line1) || !/\d/.test(line1)) {
    fieldErrors.line1 = 'Enter a valid street address (include street number and name).'
  }
  if (city.length < 2 || !/[A-Za-z]/.test(city)) {
    fieldErrors.city = 'City is required.'
  }
  if (!isValidUsState(state)) {
    fieldErrors.state = 'Use a valid 2-letter US state code (e.g., NY).'
  }
  if (!isValidUsPostalCode(postalCode)) {
    fieldErrors.postal_code = 'ZIP must be 5 digits or ZIP+4 (e.g., 10001 or 10001-1234).'
  }
  if (phoneRaw.length > 0 && !phone) {
    fieldErrors.phone = 'Phone must be a valid US number (10 digits, optional +1).'
  }

  const hasErrors = Object.values(fieldErrors).some(Boolean)
  if (hasErrors) {
    formError.value = 'Fix the highlighted fields before saving the address.'
    return null
  }

  return {
    label,
    recipient_name: recipientName,
    line1,
    line2,
    city,
    state,
    postal_code: postalCode,
    phone,
    is_default: form.is_default,
  }
}

function saveAddress() {
  const payload = buildValidatedPayload()
  if (!payload) {
    return
  }

  if (editingId.value) {
    emit('update', editingId.value, payload)
    return
  }
  emit('create', payload)
}

function removeAddress(addressId: string) {
  emit('delete', addressId)
}

watch(
  () => props.addresses,
  () => {
    if (editingId.value && !props.addresses.find((row) => row.id === editingId.value)) {
      resetForm()
    }
  },
)
</script>

<template>
  <section class="address-book">
    <header>
      <h3>Address book</h3>
      <p>Manage your delivery addresses (US format).</p>
    </header>

    <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>

    <div class="address-book__grid">
      <label>
        Label
        <input
          v-model="form.label"
          name="address_label"
          autocomplete="off"
          :disabled="loading || saving"
          :aria-invalid="Boolean(fieldErrors.label) || undefined"
          placeholder="Home"
          @input="clearFieldError('label')"
        />
        <small v-if="fieldErrors.label" class="field-error">{{ fieldErrors.label }}</small>
      </label>
      <label>
        Recipient
        <input
          v-model="form.recipient_name"
          name="recipient_name"
          autocomplete="name"
          :disabled="loading || saving"
          :aria-invalid="Boolean(fieldErrors.recipient_name) || undefined"
          placeholder="Patron Name"
          @input="clearFieldError('recipient_name')"
        />
        <small v-if="fieldErrors.recipient_name" class="field-error">{{ fieldErrors.recipient_name }}</small>
      </label>
      <label>
        Line 1
        <input
          v-model="form.line1"
          name="address_line1"
          autocomplete="address-line1"
          :disabled="loading || saving"
          :aria-invalid="Boolean(fieldErrors.line1) || undefined"
          placeholder="123 Main St"
          @input="clearFieldError('line1')"
        />
        <small v-if="fieldErrors.line1" class="field-error">{{ fieldErrors.line1 }}</small>
      </label>
      <label>
        Line 2
        <input
          v-model="form.line2"
          name="address_line2"
          autocomplete="address-line2"
          :disabled="loading || saving"
          placeholder="Apt / Suite"
        />
      </label>
      <label>
        City
        <input
          v-model="form.city"
          name="city"
          autocomplete="address-level2"
          :disabled="loading || saving"
          :aria-invalid="Boolean(fieldErrors.city) || undefined"
          placeholder="New York"
          @input="clearFieldError('city')"
        />
        <small v-if="fieldErrors.city" class="field-error">{{ fieldErrors.city }}</small>
      </label>
      <label>
        State
        <input
          v-model="form.state"
          name="state"
          autocomplete="address-level1"
          :disabled="loading || saving"
          :aria-invalid="Boolean(fieldErrors.state) || undefined"
          maxlength="2"
          placeholder="NY"
          @input="clearFieldError('state')"
        />
        <small v-if="fieldErrors.state" class="field-error">{{ fieldErrors.state }}</small>
      </label>
      <label>
        ZIP
        <input
          v-model="form.postal_code"
          name="postal_code"
          autocomplete="postal-code"
          inputmode="numeric"
          :disabled="loading || saving"
          :aria-invalid="Boolean(fieldErrors.postal_code) || undefined"
          placeholder="10001"
          @input="clearFieldError('postal_code')"
        />
        <small v-if="fieldErrors.postal_code" class="field-error">{{ fieldErrors.postal_code }}</small>
      </label>
      <label>
        Phone
        <input
          v-model="form.phone"
          name="phone"
          autocomplete="tel"
          inputmode="tel"
          :disabled="loading || saving"
          :aria-invalid="Boolean(fieldErrors.phone) || undefined"
          placeholder="555-111-0000"
          type="tel"
          @input="clearFieldError('phone')"
        />
        <small v-if="fieldErrors.phone" class="field-error">{{ fieldErrors.phone }}</small>
      </label>
      <label class="checkbox">
        <input v-model="form.is_default" :disabled="loading || saving" type="checkbox" /> Default
      </label>
    </div>

    <div class="address-book__actions">
      <button type="button" :disabled="saving || loading" @click="saveAddress">
        {{ editingId ? 'Update address' : 'Add address' }}
      </button>
      <button v-if="editingId" type="button" class="secondary" :disabled="saving || loading" @click="resetForm">Cancel edit</button>
    </div>

    <ul class="address-book__list">
      <li v-for="entry in addresses" :key="entry.id">
        <div>
          <strong>{{ entry.label }}</strong>
          <span v-if="props.syncStates?.[entry.id]" class="sync-pill" :class="`sync-pill--${props.syncStates[entry.id]}`">
            {{ props.syncStates[entry.id] }}
          </span>
          <p>
            {{ entry.recipient_name }} · {{ entry.line1 }}<span v-if="entry.line2">, {{ entry.line2 }}</span>
            · {{ entry.city }}, {{ entry.state }} {{ entry.postal_code }}
          </p>
          <p v-if="props.syncErrors?.[entry.id]" class="sync-error">{{ props.syncErrors[entry.id] }}</p>
        </div>
        <div class="address-book__entry-actions">
          <button type="button" class="secondary" :disabled="saving || loading" @click="editAddress(entry)">Edit</button>
          <button type="button" class="danger" :disabled="saving || loading" @click="removeAddress(entry.id)">Delete</button>
        </div>
      </li>
      <li v-if="addresses.length === 0">No saved addresses in this organization context.</li>
    </ul>
  </section>
</template>

<style scoped>
.address-book {
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

.address-book__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.55rem;
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

.checkbox {
  align-content: end;
}

.address-book__actions {
  display: flex;
  gap: 0.5rem;
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

.address-book__list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

.address-book__list li {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
}

.address-book__list p {
  margin: 0.2rem 0 0;
  color: #385470;
}

.sync-pill {
  margin-left: 0.35rem;
  border-radius: 999px;
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border: 1px solid transparent;
}

.sync-pill--local_queued,
.sync-pill--syncing {
  background: rgba(250, 204, 21, 0.2);
  color: #734d00;
  border-color: rgba(250, 204, 21, 0.35);
}

.sync-pill--server_committed {
  background: rgba(34, 197, 94, 0.15);
  color: #0b5e47;
  border-color: rgba(34, 197, 94, 0.4);
}

.sync-pill--failed_retrying,
.sync-pill--conflict {
  background: rgba(244, 63, 94, 0.2);
  color: #6a0f1b;
  border-color: rgba(244, 63, 94, 0.4);
}

.sync-error {
  margin: 0.2rem 0 0;
  color: #8a1e35;
  font-size: 0.74rem;
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

.address-book__entry-actions {
  display: flex;
  gap: 0.4rem;
}
</style>
