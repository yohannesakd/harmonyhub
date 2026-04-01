import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const stylesPath = resolve(__dirname, '..', 'styles.css')

describe('global runtime styles', () => {
  it('does not depend on external Google Fonts runtime imports', () => {
    const css = readFileSync(stylesPath, 'utf-8')
    expect(css).not.toMatch(/fonts\.googleapis\.com/i)
    expect(css).not.toMatch(/fonts\.gstatic\.com/i)
  })

  it('defines a visible focus-visible treatment for core controls', () => {
    const css = readFileSync(stylesPath, 'utf-8')
    expect(css).toContain('a:focus-visible')
    expect(css).toContain('button:focus-visible')
    expect(css).toContain('input:focus-visible')
    expect(css).toContain('select:focus-visible')
    expect(css).toContain('textarea:focus-visible')
    expect(css).toContain('--focus-ring-color')
  })
})
