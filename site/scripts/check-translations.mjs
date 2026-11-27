#!/usr/bin/env node
// Garante que o inglês (raiz do site) nunca diverge do português (origem).
//
//   node scripts/check-translations.mjs                 confere tudo
//   node scripts/check-translations.mjs --stamp <en>... regrava o sourceHash
//
// Cada página inglesa guarda em `sourceHash` o SHA-256 do arquivo pt-BR do
// qual foi traduzida. Página sem par ou com hash diferente falha a checagem.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const SOURCE_LOCALE = 'pt-br';
const PAGE_EXTENSIONS = ['.md', '.mdx'];

export function hashOf(file) {
	return createHash('sha256').update(readFileSync(file)).digest('hex');
}

function walk(dir) {
	if (!existsSync(dir)) return [];
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const full = join(dir, entry.name);
		if (entry.isDirectory()) return walk(full);
		return PAGE_EXTENSIONS.some((ext) => entry.name.endsWith(ext)) ? [full] : [];
	});
}

const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---/;
const HASH_LINE = /^sourceHash:\s*["']?([0-9a-f]+)["']?\s*$/m;

function readPageHash(file) {
	const frontmatter = readFileSync(file, 'utf8').match(FRONTMATTER);
	return frontmatter?.[1].match(HASH_LINE)?.[1] ?? null;
}

function writePageHash(file, hash) {
	const text = readFileSync(file, 'utf8');
	const frontmatter = text.match(FRONTMATTER);
	if (!frontmatter) throw new Error(`${file}: sem frontmatter`);
	const body = HASH_LINE.test(frontmatter[1])
		? frontmatter[1].replace(HASH_LINE, `sourceHash: ${hash}`)
		: `${frontmatter[1]}\nsourceHash: ${hash}`;
	writeFileSync(file, text.replace(FRONTMATTER, `---\n${body}\n---`));
}

/** Pares origem -> tradução: páginas de docs e textos da landing. */
export function pairs(root) {
	const docs = join(root, 'src', 'content', 'docs');
	const sourceDocs = join(docs, SOURCE_LOCALE);
	const landing = join(root, 'src', 'content', 'landing');
	const result = walk(sourceDocs).map((source) => ({
		kind: 'page',
		source,
		translation: join(docs, relative(sourceDocs, source)),
	}));
	const landingSource = join(landing, `${SOURCE_LOCALE}.json`);
	if (existsSync(landingSource)) {
		result.push({ kind: 'json', source: landingSource, translation: join(landing, 'en.json') });
	}
	return result;
}

function recordedHash(pair) {
	if (pair.kind === 'json') {
		return JSON.parse(readFileSync(pair.translation, 'utf8')).sourceHash ?? null;
	}
	return readPageHash(pair.translation);
}

/** @returns {{ missing: string[], stale: string[] }} caminhos relativos a `root` */
export function check(root) {
	const missing = [];
	const stale = [];
	for (const pair of pairs(root)) {
		if (!existsSync(pair.translation)) {
			missing.push(relative(root, pair.source));
		} else if (recordedHash(pair) !== hashOf(pair.source)) {
			stale.push(relative(root, pair.translation));
		}
	}
	return { missing, stale };
}

/** Regrava o hash de uma tradução depois de revisada contra a origem atual. */
export function stamp(root, translationPath) {
	const target = resolve(translationPath);
	const pair = pairs(root).find((candidate) => resolve(candidate.translation) === target);
	if (!pair) throw new Error(`${translationPath}: não é tradução de nenhuma página pt-BR`);
	if (!existsSync(pair.translation)) throw new Error(`${translationPath}: arquivo não existe`);
	const hash = hashOf(pair.source);
	if (pair.kind === 'json') {
		const data = JSON.parse(readFileSync(pair.translation, 'utf8'));
		writeFileSync(pair.translation, `${JSON.stringify({ ...data, sourceHash: hash }, null, '\t')}\n`);
	} else {
		writePageHash(pair.translation, hash);
	}
	return hash;
}

function main(argv) {
	const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
	if (argv[0] === '--stamp') {
		const targets = argv.slice(1);
		if (targets.length === 0) {
			console.error('uso: check-translations.mjs --stamp <tradução> [...]');
			return 2;
		}
		for (const target of targets) {
			stamp(root, target);
			console.log(`carimbado: ${relative(root, resolve(target))}`);
		}
		return 0;
	}
	const { missing, stale } = check(root);
	for (const file of missing) console.error(`sem tradução em inglês: ${file}`);
	for (const file of stale) console.error(`tradução defasada: ${file}`);
	if (missing.length + stale.length > 0) {
		console.error(
			'\nRevise a tradução e rode: node scripts/check-translations.mjs --stamp <tradução>',
		);
		return 1;
	}
	console.log(`traduções em dia (${pairs(root).length} pares)`);
	return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	process.exit(main(process.argv.slice(2)));
}
