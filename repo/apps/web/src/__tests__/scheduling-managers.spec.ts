import { mount } from '@vue/test-utils'

import DeliveryZoneManager from '@/components/orders/DeliveryZoneManager.vue'
import SlotCapacityManager from '@/components/orders/SlotCapacityManager.vue'

describe('Scheduling managers', () => {
  it('emits delivery zone save and delete actions', async () => {
    const wrapper = mount(DeliveryZoneManager, {
      props: {
        zones: [
          {
            id: 'zone-1',
            zip_code: '10001',
            flat_fee_cents: 350,
            is_active: true,
          },
        ],
        loading: false,
        saving: false,
      },
    })

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('10002')
    await inputs[1].setValue('500')
    await inputs[2].setValue(false)

    await wrapper.find('.zone-manager__form button').trigger('click')
    const saves = wrapper.emitted('saveZone')
    expect(saves).toBeTruthy()
    expect(saves?.[0][0]).toEqual({ zip_code: '10002', flat_fee_cents: 500, is_active: false })

    await wrapper.find('.danger').trigger('click')
    const deletes = wrapper.emitted('deleteZone')
    expect(deletes).toBeTruthy()
    expect(deletes?.[0][0]).toBe('zone-1')
  })

  it('blocks invalid delivery zone submissions with inline validation feedback', async () => {
    const wrapper = mount(DeliveryZoneManager, {
      props: {
        zones: [],
        loading: false,
        saving: false,
      },
    })

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('10A0')
    await inputs[1].setValue('-3')

    await wrapper.find('.zone-manager__form button').trigger('click')

    expect(wrapper.emitted('saveZone')).toBeFalsy()
    expect(wrapper.text()).toContain('Fix delivery-zone form errors before saving.')
    expect(wrapper.text()).toContain('ZIP must be a 5-digit US ZIP code')
    expect(wrapper.text()).toContain('Flat fee must be a whole number of cents')
  })

  it('emits slot capacity load, upsert, and remove', async () => {
    const wrapper = mount(SlotCapacityManager, {
      props: {
        capacities: [
          {
            id: 'slot-1',
            slot_start: '2026-04-01T12:30:00Z',
            capacity: 2,
          },
        ],
        loading: false,
        saving: false,
      },
    })

    const dateInput = wrapper.find('input[type="date"]')
    await dateInput.setValue('2026-04-01')
    await dateInput.trigger('change')
    const loads = wrapper.emitted('loadForDate')
    expect(loads).toBeTruthy()
    expect(loads?.[0][0]).toBe('2026-04-01')

    await wrapper.find('input[type="datetime-local"]').setValue('2026-04-01T12:45')
    await wrapper.find('input[type="number"]').setValue('4')
    await wrapper.find('.slot-manager__controls button').trigger('click')

    const upserts = wrapper.emitted('upsert')
    expect(upserts).toBeTruthy()
    expect(upserts?.[0][0]).toEqual({
      slot_start: new Date('2026-04-01T12:45').toISOString(),
      capacity: 4,
    })

    await wrapper.find('.danger').trigger('click')
    const removes = wrapper.emitted('remove')
    expect(removes).toBeTruthy()
    expect(removes?.[0][0]).toBe('2026-04-01T12:30:00Z')
  })
})
