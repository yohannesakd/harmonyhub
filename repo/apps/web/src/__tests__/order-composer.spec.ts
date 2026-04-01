import { mount } from '@vue/test-utils'

import OrderComposer from '@/components/orders/OrderComposer.vue'

describe('OrderComposer', () => {
  it('emits saveDraft payload for delivery order', async () => {
    const wrapper = mount(OrderComposer, {
      props: {
        menuItems: [
          {
            id: 'menu-1',
            name: 'Veggie Wrap',
            description: null,
            price_cents: 950,
            is_active: true,
          },
        ],
        addresses: [
          {
            id: 'addr-1',
            label: 'Home',
            recipient_name: 'Student User',
            line1: '123 Main',
            line2: null,
            city: 'New York',
            state: 'NY',
            postal_code: '10001',
            phone: null,
            is_default: true,
          },
        ],
        currentOrder: null,
        loading: false,
        saving: false,
        networkOnline: true,
        quoteConflictSlots: [],
        queuedConfirmConflict: null,
      },
    })

    const typeSelect = wrapper.find('select')
    await typeSelect.setValue('delivery')

    const slotInput = wrapper.find('input[type="datetime-local"]')
    await slotInput.setValue('2026-04-01T12:30')

    const addressSelect = wrapper.findAll('select')[1]
    await addressSelect.setValue('addr-1')

    await wrapper.find('input[type="number"]').setValue('2')
    await wrapper.find('button').trigger('click')

    const emitted = wrapper.emitted('saveDraft')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0][0]).toEqual({
      order_type: 'delivery',
      slot_start: new Date('2026-04-01T12:30').toISOString(),
      address_book_entry_id: 'addr-1',
      lines: [{ menu_item_id: 'menu-1', quantity: 2 }],
    })
  })

  it('emits chooseSuggestedSlot when suggestion clicked', async () => {
    const wrapper = mount(OrderComposer, {
      props: {
        menuItems: [],
        addresses: [],
        currentOrder: null,
        loading: false,
        saving: false,
        networkOnline: true,
        quoteConflictSlots: ['2026-04-01T12:30:00Z'],
        queuedConfirmConflict: null,
      },
    })

    await wrapper.find('.order-composer__conflict button').trigger('click')
    const emitted = wrapper.emitted('chooseSuggestedSlot')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0][0]).toBe('2026-04-01T12:30:00Z')
  })

  it('renders queued confirm conflict message with suggested slots', () => {
    const wrapper = mount(OrderComposer, {
      props: {
        menuItems: [],
        addresses: [],
        currentOrder: {
          id: 'order-1',
          status: 'quoted',
          order_type: 'pickup',
          slot_start: '2026-04-01T12:30:00Z',
          subtotal_cents: 1200,
          delivery_fee_cents: 0,
          total_cents: 1200,
          eta_minutes: 15,
          address_book_entry_id: null,
          delivery_zone_id: null,
          conflict_reason: null,
          cancel_reason: null,
          quote_expires_at: null,
          confirmed_at: null,
          preparing_at: null,
          ready_at: null,
          dispatched_at: null,
          handed_off_at: null,
          delivered_at: null,
          pickup_code_expires_at: null,
          pickup_code_rotated_at: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          lines: [],
        },
        loading: false,
        saving: false,
        networkOnline: false,
        quoteConflictSlots: [],
        queuedConfirmConflict: {
          message: 'Requested slot is at capacity',
          nextSlots: ['2026-04-01T12:45:00Z'],
        },
      },
    })

    expect(wrapper.text()).toContain('Queued finalize was rejected by server')
    expect(wrapper.text()).toContain('Requested slot is at capacity')
    expect(wrapper.findAll('.order-composer__conflict button')).toHaveLength(1)
  })

  it('announces key async ordering states and keeps operational form hints', async () => {
    const wrapper = mount(OrderComposer, {
      props: {
        menuItems: [
          {
            id: 'menu-1',
            name: 'Veggie Wrap',
            description: null,
            price_cents: 950,
            is_active: true,
          },
        ],
        addresses: [
          {
            id: 'addr-1',
            label: 'Home',
            recipient_name: 'Student User',
            line1: '123 Main',
            line2: null,
            city: 'New York',
            state: 'NY',
            postal_code: '10001',
            phone: null,
            is_default: true,
          },
        ],
        currentOrder: null,
        loading: false,
        saving: false,
        networkOnline: false,
        quoteConflictSlots: ['2026-04-01T12:45:00Z'],
        currentOrderSyncState: 'local_queued',
        currentOrderSyncError: 'Queue conflict on finalize',
        queuedConfirmConflict: {
          message: 'Requested slot is at capacity',
          nextSlots: [],
        },
      },
    })

    expect(wrapper.get('.order-composer__offline-note').attributes('role')).toBe('status')
    expect(wrapper.get('.order-composer__sync-state').attributes('aria-live')).toBe('polite')
    expect(wrapper.get('.order-composer__sync-error').attributes('role')).toBe('alert')
    expect(wrapper.findAll('.order-composer__conflict[role="alert"]').length).toBeGreaterThan(0)

    expect(wrapper.get('select[name="order_type"]').exists()).toBe(true)
    expect(wrapper.get('input[name="slot_start"]').attributes('type')).toBe('datetime-local')

    await wrapper.get('select[name="order_type"]').setValue('delivery')
    await wrapper.vm.$nextTick()

    expect(wrapper.get('select[name="address_book_entry_id"]').exists()).toBe(true)
    expect(wrapper.get('input[name="quantity_menu-1"]').attributes('inputmode')).toBe('numeric')
  })
})
