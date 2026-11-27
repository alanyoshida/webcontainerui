// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLinksValidator from 'starlight-links-validator';
import { remarkSiteLinks } from './src/lib/remark-site-links.mjs';

// Endereço e caminho base vêm do ambiente para que um domínio próprio seja
// só uma troca de variáveis no workflow (ver design.md D3).
const site = process.env.SITE_URL ?? 'https://alanyoshida.github.io';
const base = process.env.SITE_BASE ?? '/webcontainerui';

/** @param {string} en @param {string} pt @param {string} directory */
const section = (en, pt, directory) => ({
	label: en,
	translations: { 'pt-BR': pt },
	items: [{ autogenerate: { directory } }],
});

export default defineConfig({
	site,
	base,
	trailingSlash: 'always',
	markdown: { remarkPlugins: [[remarkSiteLinks, { base }]] },
	integrations: [
		starlight({
			title: 'WebContainerUI',
			description:
				'Multi-user portal for full Linux desktops and CLI coding agents in the browser.',
			defaultLocale: 'root',
			locales: {
				root: { label: 'English', lang: 'en' },
				'pt-br': { label: 'Português (Brasil)', lang: 'pt-BR' },
			},
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/alanyoshida/webcontainerui',
				},
			],
			sidebar: [
				section('Getting started', 'Começar', 'getting-started'),
				section('Architecture', 'Arquitetura', 'architecture'),
				section('Security', 'Segurança', 'security'),
				section('Operations', 'Operação', 'operations'),
				section('Reference', 'Referência', 'reference'),
			],
			favicon: '/favicon.svg',
			components: {
				SiteTitle: './src/components/starlight/SiteTitle.astro',
				ThemeProvider: './src/components/starlight/ThemeProvider.astro',
				ThemeSelect: './src/components/starlight/ThemeSelect.astro',
			},
			customCss: ['./src/styles/fonts.css', './src/styles/theme.css'],
			plugins: [starlightLinksValidator()],
		}),
	],
});
