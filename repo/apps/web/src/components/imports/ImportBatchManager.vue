<script setup lang="ts">
import { ref } from 'vue'

import type { ImportBatch, ImportBatchDetail, ImportKind } from '@/types'

const props = defineProps<{
  batches: ImportBatch[]
  selectedBatch: ImportBatchDetail | null
  loading: boolean
  acting: boolean
  canManage: boolean
}>()

const emit = defineEmits<{
  uploadBatch: [payload: { kind: ImportKind; file: File }]
  selectBatch: [batchId: string]
  normalizeBatch: [batchId: string]
  applyBatch: [batchId: string]
}>()

const selectedKind = ref<ImportKind>('member')
const selectedFile = ref<File | null>(null)

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedFile.value = target.files?.[0] ?? null
}

function onUpload() {
  if (!selectedFile.value) {
    return
  }
  emit('uploadBatch', { kind: selectedKind.value, file: selectedFile.value })
}
</script>

<template>
  <section class="imports-manager">
    <header>
      <h3>Import batches</h3>
      <p>Upload and process CSVs in two phases: normalize, then apply.</p>
    </header>

    <div class="imports-manager__upload">
      <select v-model="selectedKind" :disabled="!canManage || acting">
        <option value="member">Member CSV</option>
        <option value="roster">Roster CSV</option>
      </select>
      <input type="file" accept=".csv,text/csv" :disabled="!canManage || acting" @change="onFileChange" />
      <button type="button" :disabled="!canManage || acting || !selectedFile" @click="onUpload">
        {{ acting ? 'Working…' : 'Upload batch' }}
      </button>
    </div>

    <ul class="imports-manager__list">
      <li v-for="batch in batches" :key="batch.id">
        <button type="button" :disabled="loading" @click="emit('selectBatch', batch.id)">
          <strong>{{ batch.kind }}</strong> · {{ batch.status }} · rows {{ batch.total_rows }}
        </button>
      </li>
    </ul>

    <div v-if="selectedBatch" class="imports-manager__detail">
      <p>
        Selected batch status: <strong>{{ selectedBatch.batch.status }}</strong> · valid {{ selectedBatch.batch.valid_rows }} ·
        duplicates {{ selectedBatch.batch.duplicate_count }}
      </p>
      <div class="imports-manager__actions">
        <button type="button" :disabled="!canManage || acting" @click="emit('normalizeBatch', selectedBatch.batch.id)">
          Normalize
        </button>
        <button type="button" :disabled="!canManage || acting" @click="emit('applyBatch', selectedBatch.batch.id)">Apply</button>
      </div>
      <details>
        <summary>Normalized rows ({{ selectedBatch.rows.length }})</summary>
        <ul>
          <li v-for="row in selectedBatch.rows" :key="row.id">
            Row {{ row.row_number }} · {{ row.processing_status }}
            <span v-if="row.issues_json"> · issues {{ JSON.stringify(row.issues_json) }}</span>
          </li>
        </ul>
      </details>
    </div>
  </section>
</template>

<style scoped>
.imports-manager {
  border: 1px solid rgba(18, 36, 58, 0.16);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.94);
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}

h3 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

header p {
  margin: 0.25rem 0 0;
  color: #2f4b67;
}

.imports-manager__upload,
.imports-manager__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

button,
select,
input {
  border-radius: 0.5rem;
  border: 1px solid rgba(16, 36, 59, 0.22);
  padding: 0.4rem 0.55rem;
}

.imports-manager__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.35rem;
}

.imports-manager__list button {
  width: 100%;
  text-align: left;
  background: #fff;
}

.imports-manager__detail p {
  margin: 0;
}
</style>
