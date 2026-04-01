import { mount } from '@vue/test-utils'

import DirectorySearchForm from '@/components/directory/DirectorySearchForm.vue'

describe('DirectorySearchForm', () => {
  it('emits parsed search filters', async () => {
    const wrapper = mount(DirectorySearchForm)

    const fields = wrapper.findAll('input')
    await fields[0].setValue('vocal')
    await fields[1].setValue('Ava')
    await fields[2].setValue('Moonlight')
    await fields[3].setValue('jazz, featured')
    await fields[4].setValue('North Region')

    await wrapper.find('form').trigger('submit.prevent')

    const emitted = wrapper.emitted('search')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0][0]).toMatchObject({
      q: 'vocal',
      actor: 'Ava',
      repertoire: 'Moonlight',
      region: 'North Region',
      tags: ['jazz', 'featured'],
    })
  })
})
