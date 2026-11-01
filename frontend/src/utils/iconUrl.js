/**
 * Capa de catálogo carregada somente de origem própria (change
 * http-hardening, achado B5): só uma URL sob `/uploads/` — o armazenamento
 * do portal — é usada como `src`; qualquer outra origem cai no mesmo
 * tratamento visual de capa ausente, sem requisição externa.
 */
export function localCoverUrl(iconUrl) {
  if (typeof iconUrl === "string" && iconUrl.startsWith("/uploads/")) {
    return iconUrl;
  }
  return null;
}
