import { emailInitials } from "./initials";

test("primeira letra da parte local + primeira letra do domínio, maiúsculas", () => {
  expect(emailInitials("admin@local.test")).toBe("AL");
  expect(emailInitials("joao.silva@exemplo.test")).toBe("JE");
});
