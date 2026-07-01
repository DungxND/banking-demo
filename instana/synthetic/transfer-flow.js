/**
 * Instana Synthetic Monitoring ΓÇö API Script
 * Test: Login as sender ΓåÆ transfer ΓåÆ verify balance + notifications ΓåÆ logout
 *
 * Type:    API Script
 * Trigger: Every 10 minutes
 *
 * Variables (set in Instana UI under Synthetic test ΓåÆ Variables):
 *   BASE_URL        https://npd-banking.co
 *   SENDER_USER     alice
 *   SENDER_PASSWORD password123
 *   RECEIVER_USER   bob            (must exist and be different from sender)
 *   TRANSFER_AMOUNT 1              (keep small ΓÇö real balance is modified)
 */

const BASE_URL = $synthetic.variables.BASE_URL        || 'https://npd-banking.co';
const SENDER   = $synthetic.variables.SENDER_USER     || 'alice';
const S_PASS   = $synthetic.variables.SENDER_PASSWORD || 'password123';
const RECEIVER = $synthetic.variables.RECEIVER_USER   || 'bob';
const AMOUNT   = Number($synthetic.variables.TRANSFER_AMOUNT) || 1;

(async () => {

  // ΓöÇΓöÇ Step 1: Login sender ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const loginRes = await $http.post(`${BASE_URL}/api/auth/login`, {
    json: { username: SENDER, password: S_PASS },
    timeout: 8000,
  });
  $assert.equal(loginRes.status, 200, `Sender login failed: HTTP ${loginRes.status}`);

  const { session, balance: balanceBefore } = loginRes.json();
  $assert.ok(session, 'No session token returned on login');
  $assert.ok(balanceBefore >= AMOUNT,
    `Sender balance (${balanceBefore}) too low for transfer of ${AMOUNT}`);

  // ΓöÇΓöÇ Step 2: Execute transfer ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const transferRes = await $http.post(`${BASE_URL}/api/transfer/transfer`, {
    headers: { 'X-Session': session },
    json: { to_username: RECEIVER, amount: AMOUNT },
    timeout: 10000,
  });
  $assert.equal(transferRes.status, 200, `Transfer failed: HTTP ${transferRes.status}`);

  const transferBody = transferRes.json();
  $assert.equal(transferBody.ok, true,       'Transfer response ok !== true');
  $assert.equal(transferBody.from, SENDER,   'Transfer from-username mismatch');
  $assert.equal(transferBody.to, RECEIVER,   'Transfer to-username mismatch');
  $assert.equal(transferBody.amount, AMOUNT, 'Transfer amount mismatch');

  // ΓöÇΓöÇ Step 3: Verify balance decreased ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const balanceRes = await $http.get(`${BASE_URL}/api/account/balance`, {
    headers: { 'X-Session': session },
    timeout: 5000,
  });
  $assert.equal(balanceRes.status, 200, `Balance check failed: HTTP ${balanceRes.status}`);

  const { balance: balanceAfter } = balanceRes.json();
  $assert.equal(balanceAfter, balanceBefore - AMOUNT,
    `Expected balance ${balanceBefore - AMOUNT}, got ${balanceAfter}`);

  // ΓöÇΓöÇ Step 4: Verify notification was created ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const notifRes = await $http.get(`${BASE_URL}/api/notifications/notifications`, {
    headers: { 'X-Session': session },
    timeout: 5000,
  });
  $assert.equal(notifRes.status, 200, `Notifications fetch failed: HTTP ${notifRes.status}`);

  const notifications = notifRes.json();
  $assert.ok(Array.isArray(notifications), 'Notifications response is not an array');
  $assert.ok(notifications.length > 0, 'No notifications found after transfer');

  const latest = notifications[0];
  $assert.ok(
    latest.message.includes(String(AMOUNT)),
    `Latest notification does not mention transfer amount ${AMOUNT}: "${latest.message}"`
  );

  // ΓöÇΓöÇ Step 5: Logout ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const logoutRes = await $http.post(`${BASE_URL}/api/auth/logout`, {
    headers: { 'X-Session': session },
    timeout: 5000,
  });
  $assert.equal(logoutRes.status, 204, `Logout failed: HTTP ${logoutRes.status}`);

})();