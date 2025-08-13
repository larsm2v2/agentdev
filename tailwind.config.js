/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./frontend/**/*.{html,js}",
    "./src/**/*.{html,js,py}",
    "./**/*.html",
    "./frontend/email_librarian.html",
    "./frontend/components/**/*.html",
    "./frontend/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        "librarian-blue": "#3B82F6",
        "librarian-dark": "#1E3A8A",
      },
      fontFamily: {
        librarian: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
