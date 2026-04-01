import { mount } from '@vue/test-utils'

import FulfillmentQueuePanel from '@/components/fulfillment/FulfillmentQueuePanel.vue'
import type { FulfillmentQueueOrder } from '@/types'

function makeOrder(overrides: Partial<FulfillmentQueueOrder>): FulfillmentQueueOrder {
  return {
    id: 'order-1',
    user_id: 'user-1',
    username: 'student',
    status: 'confirmed',
    order_type: 'pickup',
    slot_start: '2026-04-01T12:30:00Z',
    subtotal_cents: 1000,
    delivery_fee_cents: 0,
    total_cents: 1000,
    eta_minutes: 18,
    confirmed_at: '2026-04-01T12:10:00Z',
    preparing_at: null,
    ready_at: null,
    dispatched_at: null,
    handed_off_at: null,
    delivered_at: null,
    updated_at: '2026-04-01T12:10:00Z',
    lines: [
      {
        id: 'line-1',
        menu_item_id: 'menu-1',
        item_name: 'Veggie Wrap',
        quantity: 1,
        unit_price_cents: 1000,
        line_total_cents: 1000,
      },
    ],
    address: null,
    ...overrides,
  }
}

describe('FulfillmentQueuePanel', () => {
  it('emits transition for pickup queue actions', async () => {
    const wrapper = mount(FulfillmentQueuePanel, {
      props: {
        title: 'Pickup queue',
        subtitle: 'test',
        queueType: 'pickup',
        orders: [makeOrder({ status: 'confirmed' })],
        loading: false,
        saving: false,
      },
    })

    await wrapper.find('button').trigger('click')
    const emitted = wrapper.emitted('transition')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0]).toEqual(['order-1', 'preparing', undefined])
  })

  it('emits pickup-code verification in ready_for_pickup state', async () => {
    const wrapper = mount(FulfillmentQueuePanel, {
      props: {
        title: 'Pickup queue',
        subtitle: 'test',
        queueType: 'pickup',
        orders: [makeOrder({ status: 'ready_for_pickup' })],
        loading: false,
        saving: false,
      },
    })

    await wrapper.find('input').setValue('123456')
    const verifyButton = wrapper.findAll('button').find((btn) => btn.text().includes('Verify + hand off'))
    expect(verifyButton).toBeTruthy()
    await verifyButton!.trigger('click')

    const emitted = wrapper.emitted('verifyPickupCode')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0]).toEqual(['order-1', '123456'])
  })

  it('emits delivery transition actions', async () => {
    const wrapper = mount(FulfillmentQueuePanel, {
      props: {
        title: 'Delivery queue',
        subtitle: 'test',
        queueType: 'delivery',
        orders: [makeOrder({ status: 'out_for_delivery', order_type: 'delivery' })],
        loading: false,
        saving: false,
      },
    })

    await wrapper.find('button').trigger('click')
    const emitted = wrapper.emitted('transition')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0]).toEqual(['order-1', 'delivered', undefined])
  })
})
