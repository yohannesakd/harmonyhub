import { mount } from '@vue/test-utils'

import RepertoireResultCard from '@/components/repertoire/RepertoireResultCard.vue'

describe('RepertoireResultCard', () => {
  it('renders repertoire metadata', () => {
    const wrapper = mount(RepertoireResultCard, {
      props: {
        item: {
          id: 'rep-1',
          title: 'Moonlight Sonata',
          composer: 'L. van Beethoven',
          tags: ['classical', 'featured'],
          performer_names: ['Ava Martinez', 'Chloe Ng'],
          regions: ['North Region'],
        },
      },
    })

    expect(wrapper.text()).toContain('Moonlight Sonata')
    expect(wrapper.text()).toContain('L. van Beethoven')
    expect(wrapper.text()).toContain('classical')
    expect(wrapper.text()).toContain('Ava Martinez')
    expect(wrapper.text()).toContain('North Region')
  })
})
