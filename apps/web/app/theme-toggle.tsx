'use client'

import { useEffect, useState } from 'react'

type ThemeName = 'light' | 'dark'

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeName>('dark')

  useEffect(() => {
    const stored = document.documentElement.getAttribute('data-theme')
    setTheme(stored === 'light' ? 'light' : 'dark')
  }, [])

  function toggle() {
    const next: ThemeName = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    const root = document.documentElement
    root.setAttribute('data-theme', next)
    root.style.colorScheme = next
    if (next === 'dark') root.classList.add('dark')
    else root.classList.remove('dark')
    localStorage.setItem('aegis-theme', next)
  }

  const isLight = theme === 'light'

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
      title={isLight ? 'Dark mode' : 'Light mode'}
    >
      <span className={`icon ${isLight ? 'on' : 'off'}`} aria-hidden>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 14.3A9 9 0 1 1 9.7 3 7 7 0 0 0 21 14.3z" />
        </svg>
      </span>
      <span className={`icon ${isLight ? 'off' : 'on'}`} aria-hidden>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      </span>
    </button>
  )
}
