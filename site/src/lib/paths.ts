// Todo link interno passa por aqui: nenhum caminho absoluto escrito à mão,
// para que caminho base e domínio sejam só configuração (design.md D3).
export type Locale = 'en' | 'pt-br';

const base = import.meta.env.BASE_URL.replace(/\/$/, '');

/** Caminho de uma página do site no idioma dado, com base e barra final. */
export function href(locale: Locale, path = '/'): string {
	const prefix = locale === 'pt-br' ? '/pt-br' : '';
	const clean = path === '/' ? '/' : `/${path.replace(/^\/|\/$/g, '')}/`;
	return `${base}${prefix}${clean}`;
}

export const REPO_URL = 'https://github.com/alanyoshida/webcontainerui';
