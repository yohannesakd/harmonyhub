import { mount } from '@vue/test-utils'

import AddressBookManager from '@/components/orders/AddressBookManager.vue'

describe('AddressBookManager', () => {
  it('emits normalized create payload for valid US address input', async () => {
    const wrapper = mount(AddressBookManager, {
      props: {
        addresses: [],
        loading: false,
        saving: false,
      },
    })

    await wrapper.find('input[placeholder="Home"]').setValue('Home')
    await wrapper.find('input[placeholder="Patron Name"]').setValue('Student User')
    await wrapper.find('input[placeholder="123 Main St"]').setValue('123 Main Street')
    await wrapper.find('input[placeholder="Apt / Suite"]').setValue('')
    await wrapper.find('input[placeholder="New York"]').setValue('New York')
    await wrapper.find('input[placeholder="NY"]').setValue('ny')
    await wrapper.find('input[placeholder="10001"]').setValue('100011234')
    await wrapper.find('input[placeholder="555-111-0000"]').setValue('(555) 111-0000')

    await wrapper.find('.address-book__actions button').trigger('click')

    const created = wrapper.emitted('create')
    expect(created).toBeTruthy()
    expect(created?.[0][0]).toEqual({
      label: 'Home',
      recipient_name: 'Student User',
      line1: '123 Main Street',
      line2: null,
      city: 'New York',
      state: 'NY',
      postal_code: '10001-1234',
      phone: '555-111-0000',
      is_default: false,
    })
  })

  it('blocks invalid submissions and shows clear field feedback', async () => {
    const wrapper = mount(AddressBookManager, {
      props: {
        addresses: [],
        loading: false,
        saving: false,
      },
    })

    await wrapper.find('.address-book__actions button').trigger('click')

    expect(wrapper.emitted('create')).toBeFalsy()
    expect(wrapper.text()).toContain('Fix the highlighted fields before saving the address.')
    expect(wrapper.text()).toContain('Label is required.')
    expect(wrapper.text()).toContain('Recipient name is required')

    await wrapper.find('input[placeholder="Home"]').setValue('Campus')
    await wrapper.find('input[placeholder="Patron Name"]').setValue('Sam User')
    await wrapper.find('input[placeholder="123 Main St"]').setValue('123 Main')
    await wrapper.find('input[placeholder="New York"]').setValue('Albany')
    await wrapper.find('input[placeholder="NY"]').setValue('ZZ')
    await wrapper.find('input[placeholder="10001"]').setValue('10')
    await wrapper.find('input[placeholder="555-111-0000"]').setValue('12')

    await wrapper.find('.address-book__actions button').trigger('click')

    expect(wrapper.emitted('create')).toBeFalsy()
    expect(wrapper.text()).toContain('Use a valid 2-letter US state code')
    expect(wrapper.text()).toContain('ZIP must be 5 digits or ZIP+4')
    expect(wrapper.text()).toContain('Phone must be a valid US number')
  })

  it('provides strong autofill and mobile-entry hints for address fields', () => {
    const wrapper = mount(AddressBookManager, {
      props: {
        addresses: [],
        loading: false,
        saving: false,
      },
    })

    expect(wrapper.get('input[name="recipient_name"]').attributes('autocomplete')).toBe('name')
    expect(wrapper.get('input[name="address_line1"]').attributes('autocomplete')).toBe('address-line1')
    expect(wrapper.get('input[name="address_line2"]').attributes('autocomplete')).toBe('address-line2')
    expect(wrapper.get('input[name="city"]').attributes('autocomplete')).toBe('address-level2')
    expect(wrapper.get('input[name="state"]').attributes('autocomplete')).toBe('address-level1')
    expect(wrapper.get('input[name="postal_code"]').attributes('autocomplete')).toBe('postal-code')
    expect(wrapper.get('input[name="postal_code"]').attributes('inputmode')).toBe('numeric')
    expect(wrapper.get('input[name="phone"]').attributes('autocomplete')).toBe('tel')
    expect(wrapper.get('input[name="phone"]').attributes('inputmode')).toBe('tel')
  })
})
