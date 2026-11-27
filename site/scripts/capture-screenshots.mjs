#!/usr/bin/env node
// Regenera as capturas de tela da landing a partir do stack de dev.
//
//   node scripts/capture-screenshots.mjs            (ou: npm run screenshots)
//
// Pré-requisitos: stack de dev no ar em http://127.0.0.1:8000
// (deploy/docker-compose.dev.yml), startup concluído, e as imagens das
// sessões capturadas disponíveis (ver DESKTOP_IMAGE e AGENT_IMAGE). Usa o
// login dev público do repositório para preparar o cenário.
//
// As sessões são abertas por um usuário descartável criado só para isso
// (DEMO_EMAIL). Excluir uma instância apaga o volume do usuário naquela
// imagem; com um usuário próprio, o script nunca toca em instância nem em
// volume de quem já usa o stack. Não troque por uma conta real.
// Roda sob demanda, não no CI: as capturas de sessão exigem Docker real.
import { mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const BASE = process.env.WCUI_BASE_URL ?? 'http://127.0.0.1:8000';
const EMAIL = process.env.WCUI_ADMIN_EMAIL ?? 'admin@local.test';
const PASSWORD = process.env.WCUI_ADMIN_PASSWORD ?? 'senha-admin-dev-123456';
const DESKTOP_IMAGE = process.env.WCUI_SHOT_DESKTOP ?? 'Ubuntu KDE';
const AGENT_IMAGE = process.env.WCUI_SHOT_AGENT ?? 'OpenCode';
const GROUP = 'Demonstração';
const DEMO_EMAIL = 'capturas@local.test';
const DEMO_PASSWORD = 'senha-capturas-dev-123456';
const VIEWPORT = { width: 1440, height: 900 };
const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'assets', 'screenshots');

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

function client(context) {
	return async (method, path, data, { allow = [] } = {}) => {
		const response = await context.request.fetch(`${BASE}/api${path}`, { method, data });
		if (!response.ok() && !allow.includes(response.status())) {
			throw new Error(`${method} ${path}: ${response.status()} ${await response.text()}`);
		}
		const text = await response.text();
		return text ? JSON.parse(text) : null;
	};
}

async function capture(page, name) {
	await page.screenshot({ path: join(OUT, `${name}.png`) });
	console.log(`capturado: ${name}.png`);
}

async function main() {
	mkdirSync(OUT, { recursive: true });
	const browser = await chromium.launch();
	const options = { viewport: VIEWPORT, deviceScaleFactor: 1, locale: 'pt-BR' };
	const adminContext = await browser.newContext(options);
	const demoContext = await browser.newContext(options);
	const admin = client(adminContext);
	const demo = client(demoContext);
	const created = [];

	try {
		// Cenário: usuário descartável num grupo com acesso a todo o catálogo.
		await admin('POST', '/auth/login', { email: EMAIL, password: PASSWORD });
		await admin('POST', '/admin/users', { email: DEMO_EMAIL, password: DEMO_PASSWORD, is_admin: false }, { allow: [409] });
		const demoUser = (await admin('GET', '/admin/users')).find((user) => user.email === DEMO_EMAIL);
		if (!demoUser) throw new Error(`usuário ${DEMO_EMAIL} não foi criado`);
		const groups = await admin('GET', '/admin/groups');
		const group = groups.find((g) => g.name === GROUP) ?? (await admin('POST', '/admin/groups', { name: GROUP }));
		await admin('POST', `/admin/groups/${group.id}/members`, { user_id: demoUser.id }, { allow: [409] });
		// O catálogo só mostra imagem pronta: espera os downloads do primeiro
		// boot para a captura não sair com entradas faltando.
		let images = await admin('GET', '/admin/images');
		for (let waited = 0; images.some((image) => image.pull_state === 'pulling') && waited < 900; waited += 10) {
			if (waited === 0) console.log('aguardando o download das imagens do catálogo...');
			await sleep(10_000);
			images = await admin('GET', '/admin/images');
		}
		const pending = images.filter((image) => image.pull_state !== 'ready').map((image) => image.display_name);
		if (pending.length > 0) console.warn(`imagens fora do catálogo nesta captura: ${pending.join(', ')}`);
		for (const image of images) {
			await admin('POST', `/admin/groups/${group.id}/images`, { image_id: image.id }, { allow: [409] });
		}

		const adminPage = await adminContext.newPage();
		await adminPage.goto(`${BASE}/admin/catalogo`, { waitUntil: 'networkidle' });
		await sleep(800);
		await capture(adminPage, 'admin');

		await demo('POST', '/auth/login', { email: DEMO_EMAIL, password: DEMO_PASSWORD });
		const page = await demoContext.newPage();
		await page.goto(BASE, { waitUntil: 'networkidle' });
		await page.getByRole('region', { name: 'Catálogo de imagens' }).waitFor();
		await sleep(800);
		await capture(page, 'catalog');

		const sessions = [
			{ name: 'agent-session', image: AGENT_IMAGE, settle: 8_000 },
			{ name: 'desktop-session', image: DESKTOP_IMAGE, settle: 30_000 },
		];
		for (const session of sessions) {
			const image = images.find((candidate) => candidate.display_name === session.image);
			if (!image) throw new Error(`imagem "${session.image}" não está no catálogo`);
			const instance = await demo('POST', '/instances', { image_id: image.id });
			created.push(instance.id);

			for (let attempt = 0; ; attempt += 1) {
				const current = (await demo('GET', '/instances')).find((i) => i.id === instance.id);
				if (current?.state === 'running') break;
				if (current?.state === 'failed' || attempt > 90) {
					throw new Error(`instância de "${session.image}" não chegou a "running" (${current?.state})`);
				}
				await sleep(2_000);
			}

			await page.goto(BASE, { waitUntil: 'networkidle' });
			await page.getByRole('button', { name: 'Abrir sessão' }).first().click();
			await page.locator('iframe[title^="Sessão da instância"]').waitFor();
			// O conteúdo do iframe (ttyd ou Selkies) leva alguns segundos para pintar.
			await sleep(session.settle);
			await capture(page, session.name);

			await demo('POST', `/instances/${instance.id}/stop`);
			await demo('DELETE', `/instances/${instance.id}?confirm=true`);
			created.pop();
		}
	} finally {
		// Só instâncias do usuário descartável, criadas nesta execução.
		for (const id of created) {
			await demo('POST', `/instances/${id}/stop`).catch(() => {});
			await demo('DELETE', `/instances/${id}?confirm=true`).catch(() => {});
		}
		await browser.close();
	}
}

main().catch((error) => {
	console.error(error.message);
	process.exit(1);
});
