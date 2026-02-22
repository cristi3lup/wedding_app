/** @type {import('tailwindcss').Config} */
module.exports = {
  // Combinăm căile din ambele blocuri vechi
  content: [
    './**/*.html',
    './**/*.py',
    './**/*.js',
    './invapp/templates/**/*.html',
    './invapp/static/**/*.js',
  ],
  darkMode: 'class', // Sincronizat cu base.html
  theme: {
    extend: {
      fontFamily: {
        'sans': ['Montserrat', 'Poppins', 'Lato', 'sans-serif'],
        'serif': ['Cormorant Garamond', 'Bodoni Moda', 'Playfair Display', 'serif'],
        'script': ['Great Vibes', 'cursive'],
        'display': ['Cinzel Decorative', 'serif'],
        'ticket': ['Oswald', 'sans-serif'],
        'hand': ['Caveat', 'cursive'],
        'body': ['"Lato"', 'sans-serif'],
      },
      colors: {
        // Theme 1: Peony/Minimalist
        'brand-bg': '#fdfcf9',
        'brand-text': '#5c5c5c',
        'brand-heading': '#2a2a2a',
        'brand-accent': '#d4afb9',
        'brand-accent-dark': '#b9909b',

        // Theme 2: Botanical
        'botanical-green': '#5D7355',

        // Theme 3: Lemon/Travel
        'gold': '#C5A065',
        'gold-accent': '#f2d6a4',
        'lemon-gold': '#d4af37',

        // General Wedding Palette
        wedding: {
          50: '#f9f8f6',
          100: '#f2efe9',
          200: '#e6dfd3',
          500: '#b0a695',
          900: '#4a4a4a',
        }
      },
      animation: {
        'fade-in-up': 'fadeInUp 1s ease-out forwards',
        'wiggle': 'wiggle 1s ease-in-out infinite',
      },
      keyframes: {
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [
    // Aceste plugin-uri sunt esențiale
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}