import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { check, stamp } from './check-translations.mjs';

function project(files) {
	const root = mkdtempSync(join(tmpdir(), 'wcui-site-'));
	for (const [path, content] of Object.entries(files)) {
		mkdirSync(dirname(join(root, path)), { recursive: true });
		writeFileSync(join(root, path), content);
	}
	return root;
}

const PT = 'src/content/docs/pt-br/security/audits.md';
const EN = 'src/content/docs/security/audits.md';
const LANDING_PT = 'src/content/landing/pt-br.json';
const LANDING_EN = 'src/content/landing/en.json';

test('página sem tradução falha nomeando a origem', () => {
	const root = project({ [PT]: '---\ntitle: Auditorias\n---\ntexto\n' });
	assert.deepEqual(check(root), { missing: [PT], stale: [] });
});

test('tradução sem hash registrado conta como defasada', () => {
	const root = project({
		[PT]: '---\ntitle: Auditorias\n---\ntexto\n',
		[EN]: '---\ntitle: Audits\n---\ntext\n',
	});
	assert.deepEqual(check(root), { missing: [], stale: [EN] });
});

test('paridade passa depois de carimbar e preserva o frontmatter', () => {
	const root = project({
		[PT]: '---\ntitle: Auditorias\n---\ntexto\n',
		[EN]: '---\ntitle: Audits\nsidebar:\n  order: 2\n---\ntext\n',
	});
	stamp(root, join(root, EN));
	assert.deepEqual(check(root), { missing: [], stale: [] });
	const stamped = readFileSync(join(root, EN), 'utf8');
	assert.match(stamped, /^---\ntitle: Audits\nsidebar:\n  order: 2\nsourceHash: [0-9a-f]{64}\n---\ntext\n$/);
});

test('origem alterada depois da tradução falha nomeando a tradução', () => {
	const root = project({
		[PT]: '---\ntitle: Auditorias\n---\ntexto\n',
		[EN]: '---\ntitle: Audits\n---\ntext\n',
	});
	stamp(root, join(root, EN));
	writeFileSync(join(root, PT), '---\ntitle: Auditorias\n---\ntexto novo\n');
	assert.deepEqual(check(root), { missing: [], stale: [EN] });
	stamp(root, join(root, EN));
	assert.deepEqual(check(root), { missing: [], stale: [] });
});

test('textos da landing seguem a mesma regra', () => {
	const root = project({ [LANDING_PT]: '{"hero":"olá"}\n' });
	assert.deepEqual(check(root), { missing: [LANDING_PT], stale: [] });
	writeFileSync(join(root, LANDING_EN), '{"hero":"hello"}\n');
	assert.deepEqual(check(root), { missing: [], stale: [LANDING_EN] });
	stamp(root, join(root, LANDING_EN));
	assert.deepEqual(check(root), { missing: [], stale: [] });
	assert.equal(JSON.parse(readFileSync(join(root, LANDING_EN), 'utf8')).hero, 'hello');
});

test('carimbar arquivo que não é tradução é erro', () => {
	const root = project({ [PT]: '---\ntitle: A\n---\n' });
	assert.throws(() => stamp(root, join(root, 'src/content/docs/other.md')), /não é tradução/);
});
