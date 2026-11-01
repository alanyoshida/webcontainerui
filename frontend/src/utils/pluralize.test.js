import { imageCountLabel } from "./pluralize";

test("singular para 1, plural para qualquer outro valor", () => {
  expect(imageCountLabel(0)).toBe("0 imagens");
  expect(imageCountLabel(1)).toBe("1 imagem");
  expect(imageCountLabel(2)).toBe("2 imagens");
  expect(imageCountLabel(10)).toBe("10 imagens");
});
