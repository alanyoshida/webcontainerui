import { render, screen } from "@testing-library/react";
import InstanceSession from "./InstanceSession";

test("o endereço usado é relativo à própria origem, não um host de container", () => {
  render(<InstanceSession instanceId="abc-123" />);

  const iframe = screen.getByTitle(/Sessão da instância abc-123/);
  const src = iframe.getAttribute("src");

  expect(src).toBe("/i/abc-123/");
  expect(src).not.toMatch(/^https?:\/\//); // nunca aponta para outra origem
});
