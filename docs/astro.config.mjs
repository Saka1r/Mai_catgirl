// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// ВРЕМЕННАЯ ДИАГНОСТИКА
console.log('🔍 ENV CHECK:', {
  GITHUB_ACTIONS: process.env.GITHUB_ACTIONS,
  CI: process.env.CI,
  NODE_ENV: process.env.NODE_ENV,
});

const isProduction = process.env.GITHUB_ACTIONS === 'true' || process.env.CI === 'true';
const base = isProduction ? '/Mai_catgirl' : '/';

console.log('🎯 Using base:', base);


export default defineConfig({
  site: 'https://saka1r.github.io',
  base: process.env.GITHUB_ACTIONS ? '/Mai_catgirl' : '/',
  // base: '/Mai_catgirl',
  integrations: [
    starlight({
      title: 'Mai Userbot',
      description: 'Ленивая кошечка-собеседница в Telegram на локальной LLM',
      defaultLocale: 'root',
      locales: {
        root: { label: 'Русский', lang: 'ru' },
      },
      logo: { src: './src/assets/logo.svg' },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Saka1r/Mai_catgirl' },
      ],
      sidebar: [
        {
          label: 'Начало',
          items: [
            { label: 'Главная', link: '/' },
            { label: 'Установка', link: '/install/' },
          ],
        },
        {
          label: 'Гайд',
          items: [
            { label: 'Возможности', link: '/features/' },
            { label: 'Конфигурация', link: '/config/' },
          ],
        },
      ],
      customCss: ['./src/styles/retro.css'],
      components: {
        Footer: './src/components/RetroFooter.astro',
        NotFound: './src/overrides/components/NotFound.astro',
      },
    }),
  ],
});
