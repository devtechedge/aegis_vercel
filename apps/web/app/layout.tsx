import './globals.css'

export const metadata = { title: 'AEGIS', description: 'Autonomous Enterprise Graph Intelligence System' }

const THEME_BOOT = `(function(){try{var k="aegis-theme";var t=localStorage.getItem(k);if(t!=="light"&&t!=="dark")t="dark";var r=document.documentElement;r.setAttribute("data-theme",t);r.style.colorScheme=t;if(t==="dark")r.classList.add("dark");else r.classList.remove("dark");}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>{children}</body>
    </html>
  )
}
