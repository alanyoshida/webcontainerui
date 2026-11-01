import { localCoverUrl } from "./iconUrl";

test("URL sob /uploads/ é mantida", () => {
  expect(localCoverUrl("/uploads/1-abc.png")).toBe("/uploads/1-abc.png");
});

test("URL externa, relativa arbitrária e não-string viram null", () => {
  expect(localCoverUrl("https://evil.example/cover.png")).toBeNull();
  expect(localCoverUrl("//evil.example/cover.png")).toBeNull();
  expect(localCoverUrl("/api/instances")).toBeNull();
  expect(localCoverUrl(undefined)).toBeNull();
  expect(localCoverUrl(null)).toBeNull();
});
