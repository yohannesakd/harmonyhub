import { mount } from '@vue/test-utils'

import DirectoryRecommendationRail from '@/components/recommendations/DirectoryRecommendationRail.vue'

describe('DirectoryRecommendationRail', () => {
  it('emits pin and unpin actions', async () => {
    const wrapper = mount(DirectoryRecommendationRail, {
      props: {
        loading: false,
        errorMessage: null,
        canManage: true,
        pinningIds: [],
        items: [
          {
            entry_id: 'entry-1',
            display_name: 'Ava Martinez',
            region: 'North',
            tags: ['jazz'],
            repertoire: ['Moonlight Sonata'],
            contact: {
              email: 'a***@harmonyhub.example',
              phone: '***-***-2233',
              address_line1: '*** Hidden address ***',
              masked: true,
            },
            pinned: false,
            score: {
              popularity_30d: 2,
              recent_activity_72h: 1,
              tag_match: 0.2,
              total: 3.2,
            },
          },
          {
            entry_id: 'entry-2',
            display_name: 'Ben Carter',
            region: 'South',
            tags: ['drama'],
            repertoire: ['Shakespeare Nights'],
            contact: {
              email: 'b***@harmonyhub.example',
              phone: '***-***-4455',
              address_line1: '*** Hidden address ***',
              masked: true,
            },
            pinned: true,
            score: {
              popularity_30d: 1,
              recent_activity_72h: 0,
              tag_match: 0,
              total: 1,
            },
          },
        ],
      },
    })

    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    const pinEvents = wrapper.emitted('pin')
    const unpinEvents = wrapper.emitted('unpin')
    expect(pinEvents).toBeTruthy()
    expect(unpinEvents).toBeTruthy()
    expect(pinEvents?.[0][0]).toBe('entry-1')
    expect(unpinEvents?.[0][0]).toBe('entry-2')
  })
})
