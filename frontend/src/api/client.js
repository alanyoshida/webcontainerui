export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `erro ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, body) {
  const resp = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) return null;

  const isJson = resp.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await resp.json() : null;

  if (!resp.ok) {
    throw new ApiError(resp.status, data?.detail);
  }
  return data;
}

async function requestMultipart(method, path, formData) {
  // Sem Content-Type explícito: o browser define multipart/form-data com o
  // boundary correto a partir do FormData, diferente de `request`, que
  // sempre envia JSON.
  const resp = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    body: formData,
  });

  const isJson = resp.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await resp.json() : null;

  if (!resp.ok) {
    throw new ApiError(resp.status, data?.detail);
  }
  return data;
}

export const api = {
  login: (email, password) => request("POST", "/auth/login", { email, password }),
  logout: () => request("POST", "/auth/logout"),
  me: () => request("GET", "/auth/me"),

  getCatalog: () => request("GET", "/catalog"),
  getPublicConfig: () => request("GET", "/config"),

  getSshIdentity: () => request("GET", "/me/ssh-identity"),
  regenerateSshIdentity: () => request("POST", "/me/ssh-identity/regenerate"),

  listInstances: () => request("GET", "/instances"),
  createInstance: (imageId) => request("POST", "/instances", { image_id: imageId }),
  stopInstance: (id) => request("POST", `/instances/${id}/stop`),
  deleteInstance: (id, confirm) => request("DELETE", `/instances/${id}?confirm=${confirm}`),

  adminListUsers: () => request("GET", "/admin/users"),
  adminCreateUser: (email, password, isAdmin) =>
    request("POST", "/admin/users", { email, password, is_admin: isAdmin }),
  adminDisableUser: (userId) => request("POST", `/admin/users/${userId}/disable`),

  adminListGroups: () => request("GET", "/admin/groups"),
  adminCreateGroup: (name) => request("POST", "/admin/groups", { name }),
  adminRenameGroup: (groupId, name) => request("PATCH", `/admin/groups/${groupId}`, { name }),
  adminDeleteGroup: (groupId) => request("DELETE", `/admin/groups/${groupId}`),
  adminListMembers: (groupId) => request("GET", `/admin/groups/${groupId}/members`),
  adminAddMember: (groupId, userId) =>
    request("POST", `/admin/groups/${groupId}/members`, { user_id: userId }),
  adminRemoveMember: (groupId, userId) =>
    request("DELETE", `/admin/groups/${groupId}/members/${userId}`),
  adminListGroupImages: (groupId) => request("GET", `/admin/groups/${groupId}/images`),

  adminListImages: () => request("GET", "/admin/images"),
  adminCreateImage: (payload) => request("POST", "/admin/images", payload),
  adminRetryPull: (imageId) => request("POST", `/admin/images/${imageId}/retry-pull`),
  adminDisableImage: (imageId) => request("POST", `/admin/images/${imageId}/disable`),
  adminUploadImageIcon: (imageId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestMultipart("POST", `/admin/images/${imageId}/icon`, formData);
  },

  adminGrantImage: (groupId, imageId) =>
    request("POST", `/admin/groups/${groupId}/images`, { image_id: imageId }),
  adminRevokePreview: (groupId, imageId) =>
    request("GET", `/admin/groups/${groupId}/images/${imageId}/revoke-preview`),
  adminRevokeImage: (groupId, imageId, confirm) =>
    request("DELETE", `/admin/groups/${groupId}/images/${imageId}?confirm=${confirm}`),

  adminUsageLive: () => request("GET", "/admin/usage/live"),
  adminUsageRuns: (limit, offset) => request("GET", `/admin/usage/runs?limit=${limit}&offset=${offset}`),
  adminUsageSummary: () => request("GET", "/admin/usage/summary"),
};
