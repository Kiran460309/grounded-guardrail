/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eef9ff',
          100: '#d9f1ff',
          200: '#bce8ff',
          300: '#8edaff',
          400: '#59c4ff',
          500: '#33a9ff',
          600: '#1a8cf5',
          700: '#1272d8',
          800: '#155caf',
          900: '#174e8a',
        },
        surface: {
          900: '#0a0f1e',
          800: '#0f1629',
          700: '#151e36',
          600: '#1c2845',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'fade-up': 'fadeUp 0.4s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
