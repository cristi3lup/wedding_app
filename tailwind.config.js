/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    // The "Catch-All" Pattern:
    // This looks for ANY .html or .py file inside ANY folder in your project.
    './**/*.html',
    './**/*.py',

    // Specific inclusion for JS if you use it in templates
    './**/*.js',
  ],
  theme: {
    extend: {
      fontFamily: {
        'sans': ['Montserrat', 'Poppins', 'Lato', 'sans-serif'],
        'serif': ['Cormorant Garamond', 'Bodoni Moda', 'serif'],
        'script': ['Great Vibes', 'cursive'],
        'display': ['Cinzel Decorative', 'serif'],
        'ticket': ['Oswald', 'sans-serif'],
        'hand': ['Caveat', 'cursive'],
      },
      colors: {
        // Peony/Minimalist Theme
        'brand-bg': '#fdfcf9',
        'brand-text': '#5c5c5c',
        'brand-heading': '#2a2a2a',
        'brand-accent': '#d4afb9',
        'brand-accent-dark': '#b9909b',

        // Botanical Theme
        'botanical-green': '#5D7355',

        // Lemon/Travel Theme
        'gold': '#C5A065',
        'gold-accent': '#f2d6a4',
        'lemon-gold': '#d4af37',
      }
    },
  },
  plugins: [],
}