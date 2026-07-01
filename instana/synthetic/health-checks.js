/**
 * Instana Synthetic Monitoring ΓÇö API Script
 * Test: Health checks for all four banking services
 *
 * Type:    API Script
 * Trigger: Every 1 minute
 *
 * Variables (set in Instana UI under Synthetic test ΓåÆ Variables):
 *   BASE_URL   https://npd-banking.co
 */

const BASE_URL = $synthetic.variables.BASE_URL || 'https://npd-banking.co';

const services = [
  { name: 'auth-service',         path: '/api/auth/health' },
  { name: 'account-service',      path: '/api/account/health' },
  { name: 'transfer-service',     path: '/api/transfer/health' },
  { name: 'notification-service', path: '/api/notifications/health' },
];

(async () => {

  for (const svc of services) {
    const res = await $http.get(`${BASE_URL}${svc.path}`, {
      timeout: 5000,
    });
    $assert.equal(res.status, 200,
      `${svc.name} health check returned ${res.status}, expected 200`);

    const body = res.json();
    $assert.equal(body.status, 'healthy',
      `${svc.name} reported status="${body.status}", expected "healthy"`);
  }

})();