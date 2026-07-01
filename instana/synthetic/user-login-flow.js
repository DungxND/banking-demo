/**
 * Instana Synthetic Monitoring ΓÇö API Script
 * Test: Full login ΓåÆ get balance ΓåÆ logout flow
 *
 * Type:    API Script
 * Trigger: Every 5 minutes
 *
 * Variables (set in Instana UI under Synthetic test ΓåÆ Variables):
 *   BASE_URL      https://npd-banking.co
 *   TEST_USER     alice
 *   TEST_PASSWORD password123
 */

const BASE_URL = $synthetic.variables.BASE_URL      || 'https://npd-banking.co';
const USERNAME = $synthetic.variables.TEST_USER     || 'alice';
const PASSWORD = $synthetic.variables.TEST_PASSWORD || 'password123';

(async () => {

  // ΓöÇΓöÇ Step 1: Login ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const loginRes = await $http.post(`${BASE_URL}/api/auth/login`, {
    json: { username: USERNAME, password: PASSWORD },
    timeout: 8000,
  });
  $assert.equal(loginRes.status, 200, `Login failed with HTTP ${loginRes.status}`);

  const { session, username } = loginRes.json();
  $assert.ok(session,  'Login response missing session token');
  $assert.ok(username, 'Login response missing username');

  // ΓöÇΓöÇ Step 2: Get balance ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const balanceRes = await $http.get(`${BASE_URL}/api/account/balance`, {
    headers: { 'X-Session': session },
    timeout: 5000,
  });
  $assert.equal(balanceRes.status, 200, `Balance check failed with HTTP ${balanceRes.status}`);

  const { balance } = balanceRes.json();
  $assert.ok(typeof balance === 'number', `Expected numeric balance, got: ${balance}`);

  // ΓöÇΓöÇ Step 3: Get profile ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const meRes = await $http.get(`${BASE_URL}/api/account/me`, {
    headers: { 'X-Session': session },
    timeout: 5000,
  });
  $assert.equal(meRes.status, 200, `Profile fetch failed with HTTP ${meRes.status}`);
  $assert.equal(meRes.json().username, USERNAME, 'Profile username mismatch');

  // ΓöÇΓöÇ Step 4: Logout ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const logoutRes = await $http.post(`${BASE_URL}/api/auth/logout`, {
    headers: { 'X-Session': session },
    timeout: 5000,
  });
  $assert.equal(logoutRes.status, 204, `Logout failed with HTTP ${logoutRes.status}`);

})();