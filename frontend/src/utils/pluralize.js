/**
 * "1 imagem" / "N imagens" — usado nos painéis de vínculo (AGENTS.md,
 * Skills, MCP) onde a contagem de imagens vinculadas aparecia sempre como
 * "imagem(ns)", mesmo no singular.
 */
export function imageCountLabel(count) {
  return count === 1 ? "1 imagem" : `${count} imagens`;
}
