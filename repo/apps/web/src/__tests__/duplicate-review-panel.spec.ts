import { mount } from '@vue/test-utils'

import DuplicateReviewPanel from '@/components/imports/DuplicateReviewPanel.vue'

describe('DuplicateReviewPanel', () => {
  it('emits merge, ignore, and undo actions', async () => {
    const wrapper = mount(DuplicateReviewPanel, {
      props: {
        duplicates: [
          {
            id: 'dup-open',
            batch_id: 'batch-1',
            normalized_row_id: 'row-1',
            target_directory_entry_id: 'target-1',
            target_display_name: 'Open Candidate',
            reason: 'display_name_match',
            status: 'open',
            merge_action_id: null,
            normalized_json: { phone: '555-0101' },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: 'dup-merged',
            batch_id: 'batch-1',
            normalized_row_id: 'row-2',
            target_directory_entry_id: 'target-2',
            target_display_name: 'Merged Candidate',
            reason: 'email_match',
            status: 'merged',
            merge_action_id: 'merge-1',
            normalized_json: { email: 'artist@example.com' },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        canManage: true,
        acting: false,
      },
    })

    const inputs = wrapper.findAll('input[type="text"]')
    await inputs[0].setValue('merge note')
    await inputs[1].setValue('undo note')

    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')

    expect(wrapper.emitted('mergeDuplicate')?.[0][0]).toEqual({ duplicateId: 'dup-open', note: 'merge note' })
    expect(wrapper.emitted('ignoreDuplicate')?.[0][0]).toBe('dup-open')
    expect(wrapper.emitted('undoMerge')?.[0][0]).toEqual({ mergeActionId: 'merge-1', reason: 'undo note' })
  })
})
