/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  safelist: [
    // Grid system classes
    'grid',
    'grid-cols-12',
    'col-span-1',
    'col-span-2', 
    'col-span-3',
    'col-span-4',
    'gap-x-2',
    // Size utility
    'size-4',
    // Color classes for dynamic content
    'text-emerald-400',
    'text-red-400',
    'bg-blue-500/10',
    'bg-blue-500/20',
    'hover:bg-blue-500/20',
    'hover:bg-gray-700/20'
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}