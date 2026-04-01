import { mount } from '@vue/test-utils'
import LoginForm from '@/components/auth/LoginForm.vue'

describe('LoginForm', () => {
  it('emits submit payload', async () => {
    const wrapper = mount(LoginForm, {
      props: {
        mfaRequired: false,
      },
    })

    expect((wrapper.find('input[autocomplete="username"]').element as HTMLInputElement).value).toBe('')
    expect((wrapper.find('input[type="password"]').element as HTMLInputElement).value).toBe('')

    await wrapper.find('input[autocomplete="username"]').setValue('student-user')
    await wrapper.find('input[type="password"]').setValue('safe-password')
    await wrapper.find('form').trigger('submit.prevent')

    const emitted = wrapper.emitted('submit')
    expect(emitted).toBeTruthy()
    expect(emitted?.[0][0]).toEqual({ username: 'student-user', password: 'safe-password', totpCode: undefined })
  })

  it('provides strong autocomplete and mobile input hints', () => {
    const wrapper = mount(LoginForm, {
      props: {
        mfaRequired: true,
      },
    })

    const username = wrapper.get('input[name="username"]')
    const password = wrapper.get('input[name="password"]')
    const totp = wrapper.get('input[name="totp_code"]')

    expect(username.attributes('autocomplete')).toBe('username')
    expect(password.attributes('autocomplete')).toBe('current-password')
    expect(totp.attributes('autocomplete')).toBe('one-time-code')
    expect(totp.attributes('inputmode')).toBe('numeric')
    expect(totp.attributes('pattern')).toBe('[0-9]*')
  })
})
