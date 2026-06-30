import React, { useRef, useState } from "react";
import { api } from "./api";
import Card from "./ui/Card";

export default function Register({ onGoLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const passwordRef = useRef(null);

  // ── client-side validation ──────────────────────────────────────────────
  function validate() {
    const errors = {};
    if (!username.trim()) {
      errors.username = "Username is required";
    } else if (username.trim().length < 3) {
      errors.username = "Username must be at least 3 characters";
    }
    if (!password) {
      errors.password = "Password is required";
    } else if (password.length < 6) {
      errors.password = "Password must be at least 6 characters";
    }
    return errors;
  }

  // ── submission ──────────────────────────────────────────────────────────
  const submit = async () => {
    if (loading) return;
    setServerError("");
    setSuccess(false);

    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setLoading(true);
    try {
      await api.register(username.trim(), password);
      setSuccess(true);
      // Auto-navigate to login after a short moment so the user sees the message
      setTimeout(onGoLogin, 1500);
    } catch (e) {
      const raw = e.message || "Registration failed. Please try again.";
      if (raw.toLowerCase().includes("already taken") ||
          raw.toLowerCase().includes("409")) {
        setFieldErrors({ username: "That username is already taken. Choose another." });
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
    <Card
      title="Create account"
      desc="Register a new user to test transfers and realtime notifications."
      footer="Passwords are hashed with bcrypt — never stored in plain text."
    >
      <div className="space-y-4">
        {/* Username */}
        <div>
          <label className="text-xs font-medium text-slate-600" htmlFor="reg-username">
            Username
          </label>
          <input
            id="reg-username"
            autoComplete="username"
            autoFocus
            className={`mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500 ${
              fieldErrors.username ? "border-red-400 bg-red-50" : ""
            }`}
            placeholder="min 3 characters"
            value={username}
            onChange={(e) => changeUsername(e.target.value)}
            onKeyDown={onUsernameKey}
            disabled={loading || success}
          />
          {fieldErrors.username && (
            <p className="mt-1 text-xs text-red-600">{fieldErrors.username}</p>
          )}
        </div>

        {/* Password */}
        <div>
          <label className="text-xs font-medium text-slate-600" htmlFor="reg-password">
            Password
          </label>
          <input
            id="reg-password"
            ref={passwordRef}
            autoComplete="new-password"
            type="password"
            className={`mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500 ${
              fieldErrors.password ? "border-red-400 bg-red-50" : ""
            }`}
            placeholder="min 6 characters"
            value={password}
            onChange={(e) => changePassword(e.target.value)}
            onKeyDown={onPasswordKey}
            disabled={loading || success}
          />
          {fieldErrors.password && (
            <p className="mt-1 text-xs text-red-600">{fieldErrors.password}</p>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="button"
            disabled={loading || success}
            onClick={submit}
            className="flex-1 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? "Creating…" : "Create account"}
          </button>
          <button
            type="button"
            onClick={onGoLogin}
            disabled={loading}
            className="rounded-xl border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            Back
          </button>
        </div>

        {/* Success banner */}
        {success && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            ✓ Account created — redirecting to sign in…
          </div>
        )}

        {/* Server-level error banner */}
        {serverError && (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span className="mt-0.5 shrink-0">⚠</span>
            <span>{serverError}</span>
          </div>
        )}
      </div>
    </Card>
  );
}
