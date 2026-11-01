/**
 * Iniciais do avatar do usuário: primeira letra da parte local do e-mail +
 * primeira letra do domínio, maiúsculas (ver design.md D4).
 */
export function emailInitials(email) {
  const [local, domain] = email.split("@");
  const first = local?.[0] ?? "";
  const second = domain?.[0] ?? "";
  return (first + second).toUpperCase();
}
