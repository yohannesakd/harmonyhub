import { mount } from '@vue/test-utils'

import AccountControlPanel from '@/components/imports/AccountControlPanel.vue'

describe('AccountControlPanel', () => {
  it('emits freeze and unfreeze payloads', async () => {
    const wrapper = mount(AccountControlPanel, {
      props: {
        users: [
          {
            id: 'user-active',
            username: 'active-user',
            is_active: true,
            is_frozen: false,
            frozen_at: null,
            freeze_reason: null,
            frozen_by_user_id: null,
            unfrozen_at: null,
            unfrozen_by_user_id: null,
          },
          {
            id: 'user-frozen',
            username: 'frozen-user',
            is_active: false,
            is_frozen: true,
            frozen_at: new Date().toISOString(),
            freeze_reason: 'Policy hold',
            frozen_by_user_id: 'staff-1',
            unfrozen_at: null,
            unfrozen_by_user_id: null,
          },
        ],
        canManage: true,
        acting: false,
      },
    })

    const inputs = wrapper.findAll('input[type="text"]')
    await inputs[0].setValue('Violation escalation')
    await inputs[1].setValue('Cleared by supervisor')

    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(wrapper.emitted('freeze')?.[0][0]).toEqual({ userId: 'user-active', reason: 'Violation escalation' })
    expect(wrapper.emitted('unfreeze')?.[0][0]).toEqual({ userId: 'user-frozen', reason: 'Cleared by supervisor' })
  })
})
