export function createDashboardAPI({base = '/api/v1', fetcher = fetch} = {}) {
  let identity = null, sessionVersion = 0;
  async function request(path, {method = 'GET', body} = {}) {
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET' && identity?.csrf_token) headers['X-CSRF-Token'] = identity.csrf_token;
    const response = await fetcher(base + path, {method, credentials:'include', headers,
      ...(body === undefined ? {} : {body:JSON.stringify(body)})});
    if (response.status === 204) return null;
    const value = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(value.error?.message || 'The backend could not complete the request.'); error.status = response.status; error.code = value.error?.code; throw error; }
    return value;
  }
  return {request, get identity() { return identity; },
    async session(channel) { const version = ++sessionVersion; const result = await request('/auth/me' + (channel ? '?channel_id='+encodeURIComponent(channel) : '')); if (version === sessionVersion) identity = result; return result; },
    async logout() { sessionVersion++; await request('/auth/logout', {method:'POST'}); sessionVersion++; identity = null; },
    allowed(permission) { return identity?.selected_workspace?.permissions.includes(permission) || false; },
    command(path, version, extra = {}) { return request(path, {method:'POST', body:{request_id:crypto.randomUUID(), expected_version:version, ...extra}}); },
  };
}
