import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { DEFAULT_API_BASE_URL } from '@/lib/runtimeEnv'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Insight Orchestra',
  description: 'Multi-agent data intelligence — clean, hypothesize, debate, visualize.',
}

// Runs before paint to set the theme class and avoid a flash of the wrong theme.
const themeInit = `
(function () {
  try {
    var stored = localStorage.getItem('io-theme');
    var system = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var theme = stored || system;
    if (theme === 'dark') document.documentElement.classList.add('dark');
    document.documentElement.style.colorScheme = theme;
  } catch (e) {}
})();
`

// The API base URL below has to be read per request, not baked in at build
// time — otherwise the published image hardcodes the host it was built with.
// See lib/runtimeEnv.ts.
export const dynamic = 'force-dynamic'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const apiBaseUrl =
    process.env.PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE_URL
  // `<` is escaped so a stray "</script>" in the value can't close this tag.
  const envInit = `window.__IO_ENV__=${JSON.stringify({ apiBaseUrl }).replace(/</g, '\\u003c')};`

  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrains.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        {/* Must precede the app bundle so the value is present on first import. */}
        <script dangerouslySetInnerHTML={{ __html: envInit }} />
      </head>
      <body className="bg-bg text-fg">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
