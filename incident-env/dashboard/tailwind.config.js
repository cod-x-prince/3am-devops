/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'terminal-bg': '#080810',
        'terminal-green': '#00ff88',
        'terminal-yellow': '#ffcc00',
        'terminal-orange': '#ff8800',
        'terminal-red': '#ff3333',
        'terminal-cyan': '#00ccff'
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
