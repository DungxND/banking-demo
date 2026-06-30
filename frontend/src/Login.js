import React, { useRef, useState } from "react";
import { api, setSession } from "./api";

export default function Login({ onOk, onGoRegister }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});   // { username?, password? }
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);

  const passwordRef = useRef(null);

  // ── client-side validation ──────────────────────────────────────────────
  function validate() {
    const errors = {};
    if (!username.trim()) errors.username = "Username is required";
    if (!password) errors.password = "Password is required";
    return errors;
  }

  // ── submission ──────────────────────────────────────────────────────────
  const submit = async () => {
    if (loading) return;
    setServerError("");

    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setLoading(true);
    try {
      const r = await api.login(username.trim(), password);
      setSession(r.session);
      onOk();
    } catch (e) {
      // Map known server messages to user-friendly copy
      const raw = e.message || "Login failed. Please try again.";
      if (raw.toLowerCase().includes("invalid credentials") ||
          raw.toLowerCase().includes("401")) {
        setServerError("Incorrect username or password. Please try again.");
      } else if (raw.toLowerCase().includes("network")) {
        setServerError("Cannot reach the server. Check your connection and retry.");
      } else {
        setServerError(raw);
      }
    } finally {
      setLoading(false);
    }
  };

  // ── keyboard handlers ───────────────────────────────────────────────────
  const onUsernameKey = (e) => {
    if (e.key === "Enter") passwordRef.current?.focus();
  };
  const onPasswordKey = (e) => {
    if (e.key === "Enter") submit();
  };

  // ── field change (clear per-field error on type) ────────────────────────
  const changeUsername = (v) => {
    setUsername(v);
    if (fieldErrors.username) setFieldErrors((p) => ({ ...p, username: undefined }));
  };
  const changePassword = (v) => {
    setPassword(v);
    if (fieldErrors.password) setFieldErrors((p) => ({ ...p, password: undefined }));
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border bg-white p-7 shadow-sm">

        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="h-10 w-10 rounded-xl bg-blue-600 text-white grid place-items-center font-bold text-lg">
            B
          </div>
          <div>
            <div className="text-base font-semibold text-slate-900">NPD Banking</div>
            <div className="text-xs text-slate-500">Postgres · Redis Session · WebSocket Notify</div>
          </div>
        </div>

        <h2 className="text-xl font-semibold text-slate-900">Sign in</h2>
        <p className="text-sm text-slate-500 mt-1 mb-5">
          Enter your credentials to access your account.
        </p>

        {/* Fields */}
        <div className="space-y-4">
          {/* Username */}
          <div>
            <label className="text-xs font-medium text-slate-600" htmlFor="login-username">
              Username
            </label>
            <input
              id="login-username"
              autoComplete="username"
              autoFocus
              className={`mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.username ? "border-red-400 bg-red-50" : ""
              }`}
              placeholder="your username"
              value={username}
              onChange={(e) => changeUsername(e.target.value)}
              onKeyDown={onUsernameKey}
              disabled={loading}
            />
            {fieldErrors.username && (
              <p className="mt-1 text-xs text-red-600">{fieldErrors.username}</p>
            )}
          </div>

          {/* Password */}
          <div>
            <label className="text-xs font-medium text-slate-600" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              ref={passwordRef}
              autoComplete="current-password"
              type="password"
              className={`mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.password ? "border-red-400 bg-red-50" : ""
              }`}
              placeholder="your password"
              value={password}
              onChange={(e) => changePassword(e.target.value)}
              onKeyDown={onPasswordKey}
              disabled={loading}
            />
            {fieldErrors.password && (
              <p className="mt-1 text-xs text-red-600">{fieldErrors.password}</p>
            )}
          </div>
        </div>

        {/* Server-level error banner */}
        {serverError && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span className="mt-0.5 shrink-0">⚠</span>
            <span>{serverError}</span>
          </div>
        )}

        {/* Actions */}
        <div className="mt-5 flex gap-3">
          <button
            onClick={submit}
            disabled={loading}
            className="flex-1 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
          <button
            onClick={onGoRegister}
            disabled={loading}
            className="flex-1 rounded-xl border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            Create account
          </button>
        </div>

        <div className="mt-5 text-xs text-slate-400">
          © Banking Demo Lab · Postgres + Redis
        </div>
      </div>
    </div>
  );
}
