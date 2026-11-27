// Links internos no Markdown são escritos a partir da raiz do site e sem
// idioma — `/security/audits/` — e iguais nas duas línguas. Este plugin
// acrescenta o caminho base e o prefixo do idioma da página que os contém.
import { visit } from 'unist-util-visit';

export function remarkSiteLinks({ base }) {
	const root = base.replace(/\/$/, '');
	return (tree, file) => {
		const path = (file.path ?? file.history?.[0] ?? '').replaceAll('\\', '/');
		const locale = path.includes('/content/docs/pt-br/') ? '/pt-br' : '';
		visit(tree, ['link', 'definition'], (node) => {
			if (typeof node.url !== 'string') return;
			if (!node.url.startsWith('/') || node.url.startsWith('//')) return;
			node.url = `${root}${locale}${node.url}`;
		});
	};
}
