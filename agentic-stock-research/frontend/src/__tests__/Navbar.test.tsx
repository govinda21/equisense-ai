import { describe, it, expect } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { Navbar } from '../components/Navbar'

describe('Navbar', () => {
  it('toggles dark class on html element', () => {
    const { getByRole } = render(<Navbar />)
    const btn = getByRole('button', { name: /toggle theme/i })
    // initial no dark
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    fireEvent.click(btn)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    fireEvent.click(btn)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
