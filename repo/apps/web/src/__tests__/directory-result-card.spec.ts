import { mount } from '@vue/test-utils'

import DirectoryResultCard from '@/components/directory/DirectoryResultCard.vue'

describe('DirectoryResultCard', () => {
  it('renders masked contact and emits reveal event', async () => {
    const wrapper = mount(DirectoryResultCard, {
      props: {
        entry: {
          id: 'entry-1',
          display_name: 'Ava Martinez',
          stage_name: 'Ava M.',
          region: 'North Region',
          tags: ['jazz'],
          repertoire: ['Moonlight Sonata'],
          availability_windows: [{ starts_at: '2026-04-01T17:00:00Z', ends_at: '2026-04-01T20:00:00Z' }],
          contact: {
            email: 'a***@harmonyhub.example',
            phone: '***-***-2233',
            address_line1: '*** Hidden address ***',
            masked: true,
          },
          can_reveal_contact: true,
        },
      },
    })

    expect(wrapper.text()).toContain('a***@harmonyhub.example')
    const revealButton = wrapper.find('button')
    expect(revealButton.exists()).toBe(true)

    await revealButton.trigger('click')
    const emitted = wrapper.emitted('reveal')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0][0]).toBe('entry-1')
  })
})
