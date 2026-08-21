// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';


export default defineConfig({
  site: 'https://saka1r.github.io',
  base: '/',
  //base: process.env.GITHUB_ACTIONS ? '/Mai_catgirl' : '/',
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
            { label: 'Главная', link: '/Mai_catgirl/' },
            { label: 'Установка', link: '/Mai_catgirl/install/' },
          ],
        },
        {
          label: 'Гайд',
          items: [
            { label: 'Возможности', link: '/Mai_catgirl/features/' },
            { label: 'Конфигурация', link: '/Mai_catgirl/config/' },
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
