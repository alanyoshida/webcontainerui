import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
	docs: defineCollection({
		loader: docsLoader(),
		schema: docsSchema({
			// SHA-256 da página pt-BR da qual a página inglesa foi traduzida.
			// Conferido por scripts/check-translations.mjs antes de cada build.
			extend: z.object({ sourceHash: z.string().optional() }),
		}),
	}),
};
