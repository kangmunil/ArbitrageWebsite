/**
 * @type {import('tailwindcss').Config}
 * @module tailwind.config
 * @description Tailwind CSS 설정 파일입니다.
 *              프로젝트에서 사용될 Tailwind 클래스, 테마 확장, 플러그인 등을 정의합니다.
 *              `content` 필드는 Tailwind가 스캔할 파일 경로를 지정하며,
 *              `safelist`는 동적으로 생성되어 Tailwind가 감지하지 못할 수 있는 클래스들을 명시적으로 포함시킵니다.
 */
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