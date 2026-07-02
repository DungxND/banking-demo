const API = ""; // dùng cùng origin

export function setSession(session) {
  localStorage.setItem("session", session);
}

export function getSession() {
  return localStorage.getItem("session");
}

export function clearSession() {
  localStorage.removeItem("session");
}

async function req(path, { method = "GET", body, headers = {} } = {}) {
  const session = getSession();

  const res = await fetch(API + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { "X-Session": session } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export const api = {
  register: (phone, username, password) =>
    req("/api/auth/register", {
      method: "POST",
      body: { phone, username, password }
    }),

  login: (phone, password) =>
    req("/api/auth/login", {
      method: "POST",
      body: { phone, password }
    }),

  me: () => req("/api/account/me"),

  lookupAccount: (value) => {
    // value can be a phone number or 12-digit account number
    const isPhone = !/^\d{12}$/.test(value.trim());
    const param = isPhone
      ? `phone=${encodeURIComponent(value.trim())}`
      : `account_number=${encodeURIComponent(value.trim())}`;
    return req(`/api/account/lookup?${param}`);
  },

  transfer: (to, amount) => {
    // to can be phone or 12-digit account number
    const isPhone = !/^\d{12}$/.test(to.trim());
    const body = isPhone
      ? { to_phone: to.trim(), amount: Number(amount) }
      : { to_account_number: to.trim(), amount: Number(amount) };
    return req("/api/transfer/transfer", { method: "POST", body });
  },

  notifications: () => req("/api/notifications/notifications"),

  adminStats: (secret) =>
    req("/api/account/admin/stats", { headers: { "X-Admin-Secret": secret } }),

  adminUsers: (secret, page = 1, size = 20, search = "") =>
    req(`/api/account/admin/users?page=${page}&size=${size}&search=${encodeURIComponent(search)}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  adminUserDetail: (secret, userId) =>
    req(`/api/account/admin/users/${userId}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  adminTransfers: (secret, page = 1, size = 20) =>
    req(`/api/account/admin/transfers?page=${page}&size=${size}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  adminNotifications: (secret, page = 1, size = 20, userId = "") =>
    req(`/api/account/admin/notifications?page=${page}&size=${size}${userId ? `&user_id=${userId}` : ""}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  // Health checks (no auth) — returns { status, database, redis, ... } or { error }
  async authServiceHealth() {
    try { return await req("/api/auth/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
  async accountServiceHealth() {
    try { return await req("/api/account/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
  async transferServiceHealth() {
    try { return await req("/api/transfer/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
  async notificationServiceHealth() {
    try { return await req("/api/notifications/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
};
