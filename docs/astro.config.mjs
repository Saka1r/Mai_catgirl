// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://saka1r.github.io',
  base: import.meta.env.DEV ? '/' : '/Mai_catgirl',
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
