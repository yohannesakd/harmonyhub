import { mount } from '@vue/test-utils'

import ImportBatchManager from '@/components/imports/ImportBatchManager.vue'

describe('ImportBatchManager', () => {
  it('emits upload/select/normalize/apply actions', async () => {
    const wrapper = mount(ImportBatchManager, {
      props: {
        batches: [
          {
            id: 'batch-1',
            uploaded_asset_id: 'asset-1',
            kind: 'member',
            status: 'uploaded',
            total_rows: 2,
            valid_rows: 1,
            issue_count: 1,
            duplicate_count: 0,
            processed_count: 0,
            validation_issues_json: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            processed_at: null,
          },
        ],
        selectedBatch: {
          batch: {
            id: 'batch-1',
            uploaded_asset_id: 'asset-1',
            kind: 'member',
            status: 'uploaded',
            total_rows: 2,
            valid_rows: 1,
            issue_count: 1,
            duplicate_count: 0,
            processed_count: 0,
            validation_issues_json: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            processed_at: null,
          },
          rows: [],
        },
        loading: false,
        acting: false,
        canManage: true,
      },
    })

    const file = new File(['display_name,email\nTest,test@example.com\n'], 'members.csv', { type: 'text/csv' })
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')
    await wrapper.find('.imports-manager__upload button').trigger('click')

    expect(wrapper.emitted('uploadBatch')?.[0][0]).toEqual({ kind: 'member', file })

    await wrapper.find('.imports-manager__list button').trigger('click')
    expect(wrapper.emitted('selectBatch')?.[0][0]).toBe('batch-1')

    const actionButtons = wrapper.findAll('.imports-manager__actions button')
    await actionButtons[0].trigger('click')
    await actionButtons[1].trigger('click')
    expect(wrapper.emitted('normalizeBatch')?.[0][0]).toBe('batch-1')
    expect(wrapper.emitted('applyBatch')?.[0][0]).toBe('batch-1')
  })
})
