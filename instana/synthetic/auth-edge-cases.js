/**
 * Instana Synthetic Monitoring ΓÇö API Script
 * Test: Auth service negative/edge-case paths
 *
 * Type:    API Script
 * Trigger: Every 15 minutes
 *
 * Variables (set in Instana UI under Synthetic test ΓåÆ Variables):
 *   BASE_URL      https://npd-banking.co
 *   TEST_USER     alice
 *   TEST_PASSWORD password123
 *   RECEIVER_USER bob
 */

const BASE_URL  = $synthetic.variables.BASE_URL      || 'https://npd-banking.co';
const TEST_USER = $synthetic.variables.TEST_USER     || 'alice';
const TEST_PASS = $synthetic.variables.TEST_PASSWORD || 'password123';
const RECEIVER  = $synthetic.variables.RECEIVER_USER || 'bob';

(async () => {

  // ΓöÇΓöÇ Test 1: Login with wrong password returns 401 ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const wrongPassRes = await $http.post(`${BASE_URL}/api/auth/login`, {
    json: { username: TEST_USER, password: 'definitely-wrong-password-xyz' },
    timeout: 5000,
  });
  $assert.equal(wrongPassRes.status, 401,
    `Expected 401 for wrong password, got ${wrongPassRes.status}`);

  // ΓöÇΓöÇ Test 2: Login with non-existent user returns 401 ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const noUserRes = await $http.post(`${BASE_URL}/api/auth/login`, {
    json: { username: 'nonexistent_synthetic_user_xyz', password: 'password' },
    timeout: 5000,
  });
  $assert.equal(noUserRes.status, 401,
    `Expected 401 for unknown user, got ${noUserRes.status}`);

  // ΓöÇΓöÇ Test 3: Access protected route without session returns 401 ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  // get_user_id_from_session raises HTTPException(401) when x_session is None
  const noSessionRes = await $http.get(`${BASE_URL}/api/account/balance`, {
    timeout: 5000,
  });
  $assert.equal(noSessionRes.status, 401,
    `Expected 401 for missing session, got ${noSessionRes.status}`);

  // ΓöÇΓöÇ Test 4: Transfer with invalid amount returns 400 ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
  const loginRes = await $http.post(`${BASE_URL}/api/auth/login`, {
    json: { username: TEST_USER, password: TEST_PASS },
    timeout: 8000,
  });
  $assert.equal(loginRes.status, 200, `Login failed: HTTP ${loginRes.status}`);
  const { session } = loginRes.json();

  const badAmountRes = await $http.post(`${BASE_URL}/api/transfer/transfer`, {
    headers: { 'X-Session': session },
    json: { to_username: RECEIVER, amount: -1 },
    timeout: 5000,
  });
  $assert.equal(badAmountRes.status, 400,
    `Expected 400 for negative amount, got ${badAmountRes.status}`);

  // Cleanup
  await $http.post(`${BASE_URL}/api/auth/logout`, {
    headers: { 'X-Session': session },
    timeout: 5000,
  });

})();