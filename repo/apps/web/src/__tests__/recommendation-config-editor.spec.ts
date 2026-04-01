import { mount } from '@vue/test-utils'

import RecommendationConfigEditor from '@/components/recommendations/RecommendationConfigEditor.vue'

describe('RecommendationConfigEditor', () => {
  it('emits scope selection and normalized save payload', async () => {
    const wrapper = mount(RecommendationConfigEditor, {
      props: {
        canManage: true,
        loading: false,
        saving: false,
        config: {
          id: null,
          scope: {
            scope: 'event_store',
            organization_id: 'org-1',
            program_id: 'program-1',
            event_id: 'event-1',
            store_id: 'store-1',
          },
          inherited_from_scope: 'program',
          enabled_modes: {
            popularity_30d: true,
            recent_activity_72h: true,
            tag_match: true,
          },
          weights: {
            popularity_30d: 0.5,
            recent_activity_72h: 0.3,
            tag_match: 0.2,
          },
          pins_enabled: true,
          max_pins: 3,
          pin_ttl_hours: null,
          enforce_pairing_rules: true,
          allow_staff_event_store_manage: false,
          updated_at: new Date().toISOString(),
        },
      },
    })

    await wrapper.findAll('.scope-switch button')[0].trigger('click')
    const scopeEvents = wrapper.emitted('selectScope')
    expect(scopeEvents).toBeTruthy()
    expect(scopeEvents?.[0][0]).toBe('organization')

    const weightInputs = wrapper.findAll('input[type="number"]')
    await weightInputs[0].setValue('2')
    await weightInputs[1].setValue('1')
    await weightInputs[2].setValue('1')

    await wrapper.find('button.config-editor__save').trigger('click')
    const saveEvents = wrapper.emitted('save')
    expect(saveEvents).toBeTruthy()
    expect(saveEvents?.[0][0].weights).toEqual({
      popularity_30d: 0.5,
      recent_activity_72h: 0.25,
      tag_match: 0.25,
    })
  })
})
