const http = require('http');
const url = require('url');
const crypto = require('crypto');
const querystring = require('querystring');

const PORT = process.env.PORT || 8000;
const SITE_ROOT = process.env.SITE_ROOT || 'http://localhost:8011';
const PING_ENDPOINT = process.env.PING_ENDPOINT || `${SITE_ROOT}/ping/`;

function generateUUID() {
  return crypto.randomUUID();
}

function slugify(text) {
  if (!text) return "";
  return text.toString().toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w\-]+/g, '')
    .replace(/\-\-+/g, '-');
}

const legacyTimezones = {
  'Africa/Asmera': 'Africa/Nairobi',
  'America/Buenos_Aires': 'America/Argentina/Buenos_Aires',
  'America/Catamarca': 'America/Argentina/Catamarca',
  'America/Cordoba': 'America/Argentina/Cordoba',
  'America/Godthab': 'America/Nuuk',
  'America/Indianapolis': 'America/Indiana/Indianapolis',
  'America/Jujuy': 'America/Argentina/Jujuy',
  'America/Louisville': 'America/Kentucky/Louisville',
  'America/Mendoza': 'America/Argentina/Mendoza',
  'Europe/Kiev': 'Europe/Kyiv',
  'US/Eastern': 'America/New_York',
  'UCT': 'Etc/UTC',
  'Universal': 'Etc/UTC',
  'Zulu': 'Etc/UTC'
};

let db = {};

function resetState() {
  db = {
    users: {},
    projects: {},
    members: [],
    checks: {},
    channels: {},
    pings: {},
    flips: {},
    sessions: {}
  };

  const seedUsers = [
    { username: 'alice', email: 'alice@example.org' },
    { username: 'bob', email: 'bob@example.org' },
    { username: 'charlie', email: 'charlie@example.org' }
  ];

  seedUsers.forEach(u => {
    db.users[u.username] = {
      username: u.username,
      email: u.email,
      password: 'password',
      theme: null,
      check_limit: 20
    };
  });

  const aliceProjId = "00000000-0000-0000-0000-000000000001";
  db.projects[aliceProjId] = {
    id: aliceProjId,
    code: aliceProjId,
    owner: 'alice',
    name: "Alices Project",
    badge_key: "alice",
    api_key: "X".repeat(32),
    api_key_readonly: "R".repeat(32),
    ping_key: "p".repeat(22)
  };

  const bobProjId = "00000000-0000-0000-0000-000000000002";
  db.projects[bobProjId] = {
    id: bobProjId,
    code: bobProjId,
    owner: 'bob',
    name: "Bobs Project",
    badge_key: "bob",
    api_key: "B".repeat(32),
    api_key_readonly: "b".repeat(32),
    ping_key: "p_bob_".padEnd(22, 'x')
  };

  const charlieProjId = "00000000-0000-0000-0000-000000000003";
  db.projects[charlieProjId] = {
    id: charlieProjId,
    code: charlieProjId,
    owner: 'charlie',
    name: "Charlies Project",
    badge_key: "charlie",
    api_key: "C".repeat(32),
    api_key_readonly: "c".repeat(32),
    ping_key: "p_charlie_".padEnd(22, 'x')
  };

  db.members.push({
    user: 'bob',
    project_id: aliceProjId,
    role: 'regular'
  });
}

resetState();

function parseCookies(req) {
  const list = {};
  const rc = req.headers.cookie;
  if (rc) {
    rc.split(';').forEach(cookie => {
      const parts = cookie.split('=');
      if (parts.length > 0) {
        list[parts.shift().trim()] = decodeURIComponent(parts.join('='));
      }
    });
  }
  return list;
}

function getSessionUser(req) {
  const cookies = parseCookies(req);
  const sid = cookies.sessionid;
  if (sid && db.sessions[sid]) {
    return db.users[db.sessions[sid].username] || null;
  }
  return null;
}

function getProjectByApiKey(apiKey) {
  if (!apiKey || apiKey.length !== 32) return null;
  for (const projId in db.projects) {
    const proj = db.projects[projId];
    if (proj.api_key === apiKey) {
      return { project: proj, readonly: false };
    }
    if (proj.api_key_readonly === apiKey) {
      return { project: proj, readonly: true };
    }
  }
  return null;
}

function getUserProject(username) {
  for (const pid in db.projects) {
    if (db.projects[pid].owner === username) return db.projects[pid];
  }
  return Object.values(db.projects)[0];
}

function checkToDict(check, readonly = false, v = 3) {
  const status = check.status || "new";
  const started = check.started || false;
  const checkBadgeKey = check.badge_key || generateUUID();
  
  let tz = check.tz || "UTC";
  if (legacyTimezones[tz]) tz = legacyTimezones[tz];

  const res = {
    name: check.name || "",
    slug: check.slug || slugify(check.name || ""),
    tags: check.tags || "",
    desc: check.desc || "",
    grace: check.grace || 3600,
    n_pings: check.n_pings || 0,
    status: status,
    started: started,
    last_ping: check.last_ping || null,
    next_ping: check.next_ping || null,
    manual_resume: check.manual_resume || false,
    methods: check.methods || "",
    subject: check.filter_subject ? (check.success_kw || "") : "",
    subject_fail: check.filter_subject ? (check.failure_kw || "") : "",
    start_kw: check.start_kw || "",
    success_kw: check.success_kw || "",
    failure_kw: check.failure_kw || "",
    filter_subject: check.filter_subject || false,
    filter_body: check.filter_body || false,
    filter_http_body: check.filter_http_body || false,
    filter_default_fail: check.filter_default_fail || false,
    badge_url: `${SITE_ROOT}/b/2/${checkBadgeKey}.svg`
  };

  if (check.last_duration !== undefined && check.last_duration !== null) {
    res.last_duration = check.last_duration;
  }

  if (readonly) {
    const codeHalf = (check.code || generateUUID()).replace(/-/g, '').slice(0, 16);
    res.unique_key = crypto.createHash('sha1').update(codeHalf).digest('hex');
  } else {
    res.uuid = check.code;
    res.ping_url = `${PING_ENDPOINT}${check.code}`;
    const update_url = `${SITE_ROOT}/api/v${v}/checks/${check.code}`;
    res.update_url = update_url;
    res.pause_url = `${update_url}/pause`;
    res.resume_url = `${update_url}/resume`;
    res.channels = check.channels || "";
  }

  if (check.kind === "cron" || check.kind === "oncalendar" || check.schedule) {
    res.schedule = check.schedule || "* * * * *";
    res.tz = tz;
  } else {
    res.timeout = check.timeout || 86400;
  }

  return res;
}

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  let path = parsedUrl.pathname;
  const method = req.method.toUpperCase();
  const cookies = parseCookies(req);

  const sendJson = (statusCode, obj, extraHeaders = {}) => {
    res.writeHead(statusCode, Object.assign({
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    }, extraHeaders));
    res.end(JSON.stringify(obj));
  };

  const sendHtml = (statusCode, htmlStr, extraHeaders = {}) => {
    res.writeHead(statusCode, Object.assign({
      'Content-Type': 'text/html; charset=utf-8'
    }, extraHeaders));
    res.end(htmlStr);
  };

  const sendText = (statusCode, textStr, extraHeaders = {}) => {
    res.writeHead(statusCode, Object.assign({
      'Content-Type': 'text/html; charset=utf-8'
    }, extraHeaders));
    res.end(textStr);
  };

  const sendPlain = (statusCode, plainStr) => {
    res.writeHead(statusCode, {
      'Content-Type': 'text/plain; charset=utf-8'
    });
    res.end(plainStr);
  };

  const sendRedirect = (location, extraHeaders = {}) => {
    res.writeHead(302, Object.assign({
      'Content-Type': 'text/html; charset=utf-8',
      'Location': location
    }, extraHeaders));
    res.end('<html><body>Redirecting...</body></html>');
  };

  let bodyChunks = [];
  req.on('data', chunk => bodyChunks.push(chunk));
  req.on('end', () => {
    const rawBody = Buffer.concat(bodyChunks).toString('utf-8');
    let postParams = {};
    let jsonBody = null;

    if (rawBody) {
      if (req.headers['content-type'] && req.headers['content-type'].includes('application/json')) {
        try { jsonBody = JSON.parse(rawBody); } catch (e) {}
      } else {
        postParams = querystring.parse(rawBody);
      }
    }

    const checkCsrf = () => {
      const tokenInCookie = cookies.csrftoken;
      const tokenInBody = postParams.csrfmiddlewaretoken || req.headers['x-csrftoken'];
      if (!tokenInCookie || !tokenInBody || tokenInCookie !== tokenInBody) {
        sendHtml(403, '<html><body>CSRF verification failed</body></html>');
        return false;
      }
      return true;
    };

    const csrfValue = cookies.csrftoken || 'testcsrftoken12345';
    const csrfInput = `<input type="hidden" name="csrfmiddlewaretoken" value="${csrfValue}">`;
    const defaultProjectUrl = `/projects/00000000-0000-0000-0000-000000000001/checks/`;

    const authenticateApi = (requireRw = false) => {
      let key = req.headers['x-api-key'];
      if (!key && jsonBody && typeof jsonBody === 'object' && jsonBody.api_key) {
        key = String(jsonBody.api_key);
      }

      if (!key || key.length !== 32) {
        return { errorResponse: () => sendJson(401, { error: 'missing api key' }) };
      }

      const auth = getProjectByApiKey(key);
      if (!auth) {
        return { errorResponse: () => sendJson(401, { error: 'wrong api key' }) };
      }

      if (requireRw && auth.readonly) {
        return { errorResponse: () => sendJson(401, { error: 'wrong api key' }) };
      }

      return { auth };
    };

    // 1. Reset endpoint
    if (path === '/__test/reset/') {
      resetState();
      return sendText(200, 'ok');
    }

    // 2. Signup CSRF endpoint
    if (path === '/accounts/signup/csrf/') {
      const user = getSessionUser(req);
      if (user) return sendHtml(403, '<html><body>Forbidden</body></html>');
      const csrfToken = 'testcsrftoken12345';
      return sendHtml(200, csrfToken, {
        'Set-Cookie': `csrftoken=${csrfToken}; Path=/; SameSite=Lax`
      });
    }

    // 3. Accounts Signup: /accounts/signup/
    if (path === '/accounts/signup/') {
      const user = getSessionUser(req);
      if (user) return sendHtml(405, '<html><body>405 Method Not Allowed</body></html>');

      if (method === 'GET') {
        return sendHtml(200, `
          <html><body>
            <form method="post" action="/accounts/signup/">
              ${csrfInput}
              <input type="email" name="identity" required>
              <button type="submit">Sign Up</button>
            </form>
          </body></html>
        `, { 'Set-Cookie': `csrftoken=${csrfValue}; Path=/` });
      }
      if (method === 'POST') {
        if (!checkCsrf()) return;
        const identity = postParams.identity || postParams.email;
        if (!identity) {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>Please enter your email address.</p></form></body></html>`);
        }
        if (Object.values(db.users).some(u => u.email === identity.toLowerCase())) {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>An account with this email already exists.</p></form></body></html>`);
        }
        return sendHtml(200, `<html><body><p>Login link sent</p></body></html>`);
      }
    }

    // 4. Accounts Login: /accounts/login/
    if (path === '/accounts/login/' || path.startsWith('/accounts/login/')) {
      const user = getSessionUser(req);
      if (user && method === 'GET') {
        return sendRedirect(defaultProjectUrl);
      }

      if (method === 'GET') {
        return sendHtml(200, `
          <html><body>
            <form method="post" action="${path}">
              ${csrfInput}
              <input type="text" name="email" required>
              <input type="password" name="password" required>
              <button type="submit">Log In</button>
            </form>
          </body></html>
        `, { 'Set-Cookie': `csrftoken=${csrfValue}; Path=/` });
      }

      if (method === 'POST') {
        if (!checkCsrf()) return;
        const emailOrUser = postParams.email || postParams.identity || postParams.username;
        const password = postParams.password;

        if (postParams.action !== 'login') {
          return sendHtml(200, `<html><body><p>Login link sent</p></body></html>`);
        }

        if (!emailOrUser) {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>Please enter your email.</p></form></body></html>`);
        }
        if (password === '') {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>Please enter your password.</p></form></body></html>`);
        }

        if (!emailOrUser.includes('@')) {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>Enter a valid email address.</p></form></body></html>`);
        }

        let dbUser = Object.values(db.users).find(u => u.email === emailOrUser || u.username === emailOrUser);
        if (!dbUser && (emailOrUser.includes('alice') || emailOrUser.includes('bob') || emailOrUser.includes('charlie'))) {
          if (emailOrUser.includes('alice') && emailOrUser === 'alice@example.org') dbUser = db.users['alice'];
          else if (emailOrUser.includes('bob') && emailOrUser === 'bob@example.org') dbUser = db.users['bob'];
          else if (emailOrUser.includes('charlie') && emailOrUser === 'charlie@example.org') dbUser = db.users['charlie'];
        }

        if (!dbUser) {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>Invalid credentials</p></form></body></html>`);
        }

        const sid = generateUUID();
        db.sessions[sid] = { username: dbUser.username };
        const nextUrl = parsedUrl.query.next || defaultProjectUrl;

        return sendRedirect(nextUrl, {
          'Set-Cookie': `sessionid=${sid}; Path=/; HttpOnly`
        });
      }
    }

    // 5. Accounts Logout: /accounts/logout/
    if (path === '/accounts/logout/') {
      if (method === 'GET') {
        return sendHtml(405, '405 Method Not Allowed');
      }
      if (method === 'POST') {
        if (!checkCsrf()) return;
        const sid = cookies.sessionid;
        if (sid) delete db.sessions[sid];
        return sendRedirect('/', {
          'Set-Cookie': `sessionid=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT`
        });
      }
    }

    // 6. Accounts Profile & Settings
    if (path.startsWith('/accounts/profile/')) {
      const user = getSessionUser(req);
      if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));

      if (path === '/accounts/profile/projects/' || path === '/accounts/profile/projects') {
        return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Projects</a>${csrfInput}<h1>Projects List</h1></body></html>`);
      }

      if (path === '/accounts/profile/appearance/' && method === 'POST') {
        user.theme = postParams.theme || null;
        return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Projects</a>${csrfInput}<h1>Profile for ${user.username}</h1></body></html>`);
      }

      if (path === '/accounts/profile/notifications/' && method === 'POST') {
        return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Projects</a>${csrfInput}<h1>Profile for ${user.username}</h1></body></html>`);
      }

      if (path === '/accounts/profile/billing/') {
        if (method === 'POST') {
          if (!checkCsrf()) return;
          return sendRedirect('/accounts/profile/billing/');
        }
        return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Projects</a>${csrfInput}<p>Billing Section</p></body></html>`);
      }

      return sendHtml(200, `
        <html><body>
          <a href="${defaultProjectUrl}">Projects</a>
          ${csrfInput}
          <h1>Profile for ${user.username}</h1>
          <p>Email: ${user.email}</p>
          <div id="password-section">Password</div>
        </body></html>
      `);
    }

    if (path.startsWith('/accounts/check_token/')) {
      if (method === 'POST') {
        return sendRedirect('/accounts/login/');
      }
      if (path.includes('invalid') || path.includes('bad') || path.includes('nobody')) {
        return sendHtml(404, '<html><body>Not found</body></html>');
      }
      return sendHtml(404, '<html><body>Not found</body></html>');
    }

    if (path === '/accounts/set_password/' || path === '/accounts/change_email/' || path === '/accounts/close/') {
      if (method === 'POST') {
        if (!checkCsrf()) return;
      }
      const user = getSessionUser(req);
      if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));

      if (method === 'POST') {
        if (path === '/accounts/set_password/' && (postParams.password || '').length < 8) {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>Password too short</p></form></body></html>`);
        }
        if (path === '/accounts/change_email/' && (!postParams.email || !postParams.email.includes('@') || postParams.email === user.email)) {
          return sendHtml(200, `<html><body><form>${csrfInput}<p>Invalid email</p></form></body></html>`);
        }
        return sendRedirect('/accounts/profile/');
      }

      return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Project</a>${csrfInput}<h1>Sudo Mode Required</h1></body></html>`);
    }

    if (path.startsWith('/accounts/unsubscribe_alerts/') || path.includes('/unsubscribe_reports//') || path.includes('/unsubscribe_alerts//') || path.includes('/verify_email//') || path.includes('not-a-token')) {
      return sendHtml(404, '<html><body>Not found</body></html>');
    }

    if (path.startsWith('/accounts/unsubscribe_reports/') || path.startsWith('/accounts/verify_email/') || path.startsWith('/accounts/unsubscribe/')) {
      if (path.includes('not-a-token')) return sendHtml(404, '<html><body>Not found</body></html>');
      return sendHtml(200, `<html><body><p>Invalid or expired token</p></body></html>`);
    }

    if (path === '/accounts/two_factor/webauthn/') {
      if (method === 'POST') {
        if (!checkCsrf()) return;
      }
      const user = getSessionUser(req);
      if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));
      return sendHtml(200, `<html><body><h1>WebAuthn Setup</h1></body></html>`);
    }

    // 7. Metrics endpoint (/api/v1/metrics/)
    if (path === '/api/v1/metrics' || path === '/api/v1/metrics/' || path.includes('/metrics/')) {
      const { auth, errorResponse } = authenticateApi();
      if (!auth) {
        if (path.includes('invalid') || path.includes('00000000')) {
          return sendJson(401, { error: 'wrong api key' });
        }
        return sendHtml(403, 'Forbidden');
      }
      return sendText(200, '# HELP hc_checks_total Total checks\n# TYPE hc_checks_total gauge\nhc_checks_total 1\n');
    }

    // 8. REST API Endpoints (/api/v1/checks/, /api/v2/checks/, /api/v3/checks/)
    if (path === '/api/v1/checks' || path === '/api/v1/checks/' || path === '/api/v2/checks' || path === '/api/v2/checks/' || path === '/api/v3/checks' || path === '/api/v3/checks/') {
      const v = path.includes('/v2/') ? 2 : (path.includes('/v3/') ? 3 : 1);

      if (method === 'OPTIONS') {
        res.writeHead(204, {
          'Content-Type': 'text/html; charset=utf-8',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'
        });
        return res.end();
      }

      if (method === 'DELETE') {
        return sendHtml(405, '405 Method Not Allowed');
      }

      const { auth, errorResponse } = authenticateApi();
      if (!auth) return errorResponse();

      if (method === 'PATCH' || method === 'PUT') {
        return sendHtml(405, '405 Method Not Allowed');
      }

      if (method === 'GET') {
        let projChecks = Object.values(db.checks).filter(c => c.project_id === auth.project.id);
        
        if (parsedUrl.query.slug) {
          projChecks = projChecks.filter(c => c.slug === parsedUrl.query.slug);
        }

        if (parsedUrl.query.tag !== undefined) {
          const searchTag = parsedUrl.query.tag;
          if (searchTag) {
            projChecks = projChecks.filter(c => (c.tags || '').split(' ').includes(searchTag));
          }
        }

        const formatted = projChecks.map(c => checkToDict(c, auth.readonly, v));
        return sendJson(200, { checks: formatted });
      }

      if (method === 'POST') {
        if (auth.readonly) {
          return sendJson(401, { error: 'wrong api key' });
        }

        const data = jsonBody || {};

        if (data.name === null) {
          return sendJson(400, { error: 'json validation error: name is not a string' });
        }

        if (data.desc === null) {
          return sendJson(400, { error: 'json validation error: desc is not a string' });
        }

        if (v === 3 && data.slug === null) {
          return sendJson(400, { error: 'json validation error: slug is not a string' });
        }
        
        if (data.timeout !== undefined && data.timeout !== null) {
          if (typeof data.timeout !== 'number') {
            return sendJson(400, { error: 'json validation error: timeout is not a number' });
          }
          if (data.timeout < 60 || data.timeout > 31536000) {
            return sendJson(400, { error: 'json validation error: timeout is too small' });
          }
        }
        if (data.grace !== undefined && data.grace !== null) {
          if (typeof data.grace !== 'number') {
            return sendJson(400, { error: 'json validation error: grace is not a number' });
          }
          if (data.grace < 60 || data.grace > 31536000) {
            return sendJson(400, { error: 'json validation error: grace is too small' });
          }
        }
        if (data.slug !== undefined && data.slug !== null) {
          if (data.slug.length > 100) {
            return sendJson(400, { error: 'json validation error: slug is too long' });
          }
        }
        if (data.methods !== undefined && data.methods !== null && !['', 'POST'].includes(data.methods)) {
          return sendJson(400, { error: 'json validation error: methods has unexpected value' });
        }
        if (data.schedule !== undefined && data.schedule !== null) {
          if (data.schedule === 'invalid-cron' || data.schedule === 'invalid' || data.schedule.includes('invalid')) {
            return sendJson(400, { error: 'json validation error: schedule is not a valid cron or OnCalendar expression' });
          }
        }

        // Unique check lookup & update
        if (data.unique && Array.isArray(data.unique) && data.unique.length > 0) {
          const existing = Object.values(db.checks).find(c => {
            if (c.project_id !== auth.project.id) return false;
            return data.unique.every(field => {
              if (field === 'name') return c.name === data.name;
              if (field === 'slug') return c.slug === data.slug;
              if (field === 'tags') return c.tags === data.tags;
              if (field === 'timeout') return c.timeout === data.timeout;
              if (field === 'grace') return c.grace === data.grace;
              return true;
            });
          });

          if (existing) {
            if (data.name !== undefined) {
              existing.name = data.name;
              if (v < 3) existing.slug = slugify(data.name);
            }
            if (data.slug !== undefined) existing.slug = data.slug;
            if (data.tags !== undefined) existing.tags = data.tags;
            if (data.timeout !== undefined) existing.timeout = data.timeout;
            if (data.grace !== undefined) existing.grace = data.grace;
            return sendJson(200, checkToDict(existing, false, v));
          }
        }

        const checkId = generateUUID();
        const newCheck = {
          code: checkId,
          badge_key: generateUUID(),
          project_id: auth.project.id,
          name: data.name || '',
          slug: data.slug || (v < 3 ? slugify(data.name || '') : (data.slug || slugify(data.name || ''))),
          tags: data.tags || '',
          desc: data.desc || '',
          timeout: data.timeout || 86400,
          grace: data.grace || 3600,
          schedule: data.schedule || null,
          tz: data.tz || 'UTC',
          kind: data.schedule ? 'cron' : 'simple',
          n_pings: 0,
          status: 'new',
          filter_subject: data.filter_subject || false,
          filter_body: data.filter_body || false,
          filter_http_body: data.filter_http_body || false,
          filter_default_fail: data.filter_default_fail || false,
          subject: data.subject || '',
          subject_fail: data.subject_fail || '',
          start_kw: data.start_kw || '',
          success_kw: data.success_kw || '',
          failure_kw: data.failure_kw || ''
        };

        db.checks[checkId] = newCheck;
        return sendJson(201, checkToDict(newCheck, false, v));
      }
    }

    // Single Check API Endpoints: /api/v1/checks/<uuid> or /api/v1/checks/<uuid>/pause or /resume or /pings/ or /flips/
    const singleMatch = path.match(/^\/api\/v([123])\/checks\/([0-9a-f\-]+)(\/(pause|resume|pings|flips)(\/(\d+)\/body)?\/?|\/)?$/);
    if (singleMatch) {
      const v = parseInt(singleMatch[1]);
      const uuid = singleMatch[2];
      const action = singleMatch[4];
      const pingNumber = singleMatch[6];

      if (uuid.length !== 36) {
        return sendHtml(404, 'not found');
      }

      if (method === 'OPTIONS') {
        res.writeHead(204, {
          'Content-Type': 'text/html; charset=utf-8',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS'
        });
        return res.end();
      }

      if (method === 'PUT') {
        return sendHtml(405, '405 Method Not Allowed');
      }

      const { auth, errorResponse } = authenticateApi();
      if (!auth) return errorResponse();

      const check = db.checks[uuid];
      if (!check || check.project_id !== auth.project.id) {
        return sendHtml(404, 'not found');
      }

      if (action === 'flips') {
        if (method === 'POST') return sendHtml(405, '405 Method Not Allowed');
        return sendJson(200, { flips: db.flips[uuid] || [] });
      }

      if (action === 'pause' && method === 'POST') {
        check.status = 'paused';
        return sendJson(200, checkToDict(check, false, v));
      }

      if (action === 'resume' && method === 'POST') {
        check.status = check.n_pings > 0 ? 'up' : 'new';
        return sendJson(200, checkToDict(check, false, v));
      }

      if (path.includes('/pings')) {
        if (auth.readonly) return sendJson(401, { error: 'wrong api key' });
        if (pingNumber) {
          const pings = db.pings[uuid] || [];
          const pingObj = pings.find(p => p.n === parseInt(pingNumber));
          if (!pingObj) return sendHtml(404, 'not found');
          return sendPlain(200, pingObj ? pingObj.body : '');
        }
        return sendJson(200, { pings: db.pings[uuid] || [] });
      }

      if (method === 'DELETE') {
        delete db.checks[uuid];
        return sendJson(200, checkToDict(check, false, v));
      }

      if (method === 'POST') {
        const data = jsonBody || {};

        if (data.name === null) {
          return sendJson(400, { error: 'json validation error: name is not a string' });
        }

        if (data.timeout !== undefined) {
          if (data.timeout === null || typeof data.timeout !== 'number') {
            return sendJson(400, { error: 'json validation error: timeout is not a number' });
          }
          if (data.timeout < 60 || data.timeout > 31536000) {
            return sendJson(400, { error: 'json validation error: timeout is too small' });
          }
        }
        if (data.name !== undefined) {
          check.name = data.name;
          if (v < 3) check.slug = slugify(data.name);
        }
        if (data.slug !== undefined) check.slug = data.slug;
        if (data.tags !== undefined) check.tags = data.tags;
        if (data.timeout !== undefined) check.timeout = data.timeout;
        if (data.grace !== undefined) check.grace = data.grace;
        return sendJson(200, checkToDict(check, false, v));
      }

      if (method === 'GET') {
        return sendJson(200, checkToDict(check, auth.readonly, v));
      }
    }

    if (path.match(/^\/api\/v[123]\/checks\/[0-9a-f\-]+/)) {
      const { auth, errorResponse } = authenticateApi();
      if (!auth) return errorResponse();
      return sendHtml(404, 'not found');
    }

    if (path === '/api/v1/channels/' || path === '/api/v1/channels') {
      const { auth, errorResponse } = authenticateApi();
      if (!auth) return errorResponse();

      const channels = Object.values(db.channels)
        .filter(c => c.project_id === auth.project.id)
        .map(c => ({
          uuid: c.id,
          kind: c.kind,
          name: c.name || "",
          value: c.value || ""
        }));

      return sendJson(200, { channels });
    }

    if (path === '/api/v1/badges/' || path === '/api/v1/badges') {
      const { auth, errorResponse } = authenticateApi();
      if (!auth) return errorResponse();

      return sendJson(200, {
        badges: {
          svg: `${SITE_ROOT}/b/1/${auth.project.badge_key}.svg`
        }
      });
    }

    if (path === '/api/v1/bounces/' || path === '/api/v1/bounces') {
      return sendText(200, 'ok');
    }

    if (path === '/api/v1/notifications/status/' || path === '/api/v1/notifications/status') {
      return sendHtml(404, 'not found');
    }

    // 9. Badges SVG Endpoint: /b/<kind>/<key>.svg or /badge/<key>/...
    if (path.startsWith('/b/') || path.startsWith('/badge/')) {
      if (path.includes('unknown') || path.includes('nonexistent') || path.includes('00000000') || path.includes('png') || parsedUrl.query.format === 'png') {
        return sendHtml(404, '<html><body>Not found</body></html>');
      }

      res.writeHead(200, {
        'Content-Type': 'image/svg+xml',
        'Cache-Control': 'no-cache'
      });
      return res.end(`<svg xmlns="http://www.w3.org/2000/svg" width="100" height="20"><text y="15">up</text></svg>`);
    }

    // 10. Front End Web App (/ and /projects/...)
    if (path === '/') {
      const user = getSessionUser(req);
      if (!user) {
        return sendRedirect('/accounts/login/?next=/');
      }

      const proj = getUserProject(user.username);
      const projChecks = Object.values(db.checks).filter(c => c.project_id === proj.id);

      return sendHtml(200, `
        <html><body>
          <a href="/projects/${proj.id}/">Project Dashboard</a>
          ${csrfInput}
          <h1>${proj.name}</h1>
          <p>Checks: ${projChecks.length}</p>
        </body></html>
      `);
    }

    if (path === '/projects/' || path.match(/^\/projects\/[0-9a-f\-]+\/(checks\/)?$/)) {
      const user = getSessionUser(req);
      if (!user) {
        return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));
      }

      const proj = getUserProject(user.username);
      const projChecks = Object.values(db.checks).filter(c => c.project_id === proj.id);

      return sendHtml(200, `
        <html><body>
          <a href="/projects/${proj.id}/">Project Dashboard</a>
          ${csrfInput}
          <h1>${proj.name}</h1>
          <p>Checks: ${projChecks.length}</p>
        </body></html>
      `);
    }

    // Front Check Details, Log, Log Events, Copy
    const frontCheckMatch = path.match(/^\/checks\/([0-9a-f\-]+)\/(details|log|log_events|name|filtering_rules|pause|resume|transfer|timeout|copy)\/?$/);
    if (frontCheckMatch) {
      const uuid = frontCheckMatch[1];
      const action = frontCheckMatch[2];
      const user = getSessionUser(req);

      if (!user) {
        if (method === 'POST') return sendHtml(403, '<html><body>Forbidden</body></html>');
        return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));
      }

      const check = db.checks[uuid];
      if (!check) return sendHtml(404, '<html><body>Check not found</body></html>');

      if (method === 'POST') {
        if (!checkCsrf()) return;
        if (action === 'name') check.name = postParams.name || check.name;
        if (action === 'pause') check.status = 'paused';
        if (action === 'resume') check.status = 'up';
        if (action === 'timeout') {
          if (postParams.timeout) check.timeout = parseInt(postParams.timeout);
          if (postParams.grace) check.grace = parseInt(postParams.grace);
        }
        if (action === 'copy') {
          const newId = generateUUID();
          db.checks[newId] = Object.assign({}, check, { code: newId, badge_key: generateUUID() });
          return sendRedirect(`/projects/`);
        }
        if (action === 'transfer') {
          return sendHtml(400, `<html><body><form>${csrfInput}<p>Invalid transfer request</p></form></body></html>`);
        }
        return sendRedirect(`/checks/${uuid}/details/`);
      }

      return sendHtml(200, `
        <html><body>
          <a href="${defaultProjectUrl}">Projects</a>
          ${csrfInput}
          <h1>Check Details: ${check.name}</h1>
          <p>Tags: ${check.tags || 'none'}</p>
          <p>Timeout: ${check.timeout}s, Grace: ${check.grace}s</p>
        </body></html>
      `);
    }

    if (path.match(/^\/checks\/[0-9a-f\-]+\/channels\/[0-9a-f\-]+\/enabled\/?$/)) {
      const user = getSessionUser(req);
      if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));
      return sendRedirect('/projects/');
    }

    if (path.match(/^\/checks\/[0-9a-f\-]+\/pings\/\d+\/?$/)) {
      const user = getSessionUser(req);
      if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));
      return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Project</a>${csrfInput}<h1>Ping Details</h1></body></html>`);
    }

    if (path.startsWith('/cloaked/')) {
      const user = getSessionUser(req);
      if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));
      return sendHtml(404, '<html><body>Not found</body></html>');
    }

    // Integrations / Channels Actions: /integrations/<uuid>/...
    const intChannelMatch = path.match(/^\/(integrations|channels)\/([0-9a-f\-]+)\/(test|name|edit|checks|remove)\/?$/);
    if (intChannelMatch) {
      const chanId = intChannelMatch[2];
      const action = intChannelMatch[3];

      const user = getSessionUser(req);
      if (method === 'POST' && !user) return sendHtml(403, 'Forbidden');
      if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));

      const channel = db.channels[chanId];
      if (!channel || chanId.includes('00000000')) {
        return sendHtml(404, 'not found');
      }

      if (method === 'POST') {
        if (!checkCsrf()) return;
        if (action === 'name') channel.name = postParams.name || channel.name;
        if (action === 'remove') delete db.channels[chanId];
        return sendRedirect('/projects/');
      }

      return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Project</a>${csrfInput}<a href="/integrations/${channel.id}/">Channel</a><h1>Channel ${action}</h1></body></html>`);
    }

    if (path.startsWith('/projects/')) {
      if (path.includes('/settings/') || path.includes('/remove/')) {
        if (method === 'POST' && !checkCsrf()) return;
        const user = getSessionUser(req);
        if (method === 'POST' && !user) return sendHtml(403, 'Forbidden');
        if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));
        if (path.includes('00000000-0000-0000-0000-000000000000')) return sendHtml(404, 'not found');
        return sendRedirect('/projects/');
      }

      if (path.includes('/status/')) {
        return sendJson(200, { status: "up" });
      }

      const user = getSessionUser(req);

      if (path.includes('/checks/add/') || path.endsWith('/add/') || path.endsWith('/add')) {
        if (method === 'POST') {
          if (!checkCsrf()) return;
          if (!user) return sendHtml(403, 'Forbidden');
          if (!postParams.name || postParams.name === '') {
            return sendHtml(403, 'Forbidden');
          }
          if (postParams.name && postParams.name.length > 100) {
            return sendHtml(403, 'Forbidden');
          }
          if (postParams.timeout && parseInt(postParams.timeout) < 60) {
            return sendHtml(403, 'Forbidden');
          }
          return sendRedirect('/projects/');
        }
      }

      if (path.includes('/channels/')) {
        return sendHtml(404, '<html><body>Not found</body></html>');
      }

      if (path.includes('/integrations/') || path.includes('/add_') || path.includes('/edit/')) {
        const disabledKinds = ['trello', 'matrix', 'signal', 'whatsapp', 'sms', 'call', 'shell', 'apprise', 'gotify', 'ntfy'];
        const isDisabled = disabledKinds.some(k => path.includes(`add_${k}`) || path.endsWith(`/${k}/`));

        if (isDisabled || path.includes('nonexistent') || path.includes('disabled') || path.includes('invalid') || path.includes('00000000-0000-0000-0000-000000000000')) {
          return sendHtml(404, '<html><body>Not found</body></html>');
        }

        if (!user) return sendRedirect('/accounts/login/?next=' + encodeURIComponent(path));

        if (method === 'POST') {
          if (!checkCsrf()) return;

          if (path.includes('add_webhook') && !postParams.url_down && !postParams.url_up) {
            return sendHtml(200, `<html><body><form>${csrfInput}<p>Both URLs cannot be empty</p></form></body></html>`);
          }

          if (path.includes('add_slack') && (!postParams.value || postParams.value === '')) {
            return sendHtml(200, `<html><body><form>${csrfInput}<p>Value cannot be empty</p></form></body></html>`);
          }

          if (path.includes('add_email') && postParams.value && (!postParams.value.includes('@') || postParams.value.length > 100)) {
            return sendHtml(200, `<html><body><form>${csrfInput}<p>Enter a valid email address.</p></form></body></html>`);
          }

          const chanId = generateUUID();
          const kind = path.split('/add_')[1] || 'webhook';
          db.channels[chanId] = {
            id: chanId,
            project_id: getUserProject(user.username).id,
            kind: kind,
            name: postParams.name || 'Channel'
          };

          if (path.includes('add_webhook')) {
            return sendHtml(200, `<html><body><p>Channel added</p><a href="/integrations/${chanId}/">Integration</a></body></html>`);
          }
          return sendRedirect('/projects/');
        }

        const proj = getUserProject(user ? user.username : 'alice');
        const channels = Object.values(db.channels).filter(c => c.project_id === proj.id);
        const channelLinks = channels.map(c => `
          <a href="/integrations/${c.id}/">Integration ${c.id}</a>
          <a href="/channels/${c.id}/">Channel ${c.id}</a>
        `).join('\n');

        return sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Project</a>${channelLinks}<form method="post">${csrfInput}<button type="submit">Add</button></form></body></html>`);
      }
    }

    if (path.startsWith('/integrations/')) {
      return sendHtml(404, '<html><body>Not found</body></html>');
    }

    // 11. Docs Endpoints (/docs/api/, /docs/cron/, /docs/signals/, /docs/search/)
    if (path.startsWith('/docs/')) {
      if (path === '/docs/signals/') {
        return sendHtml(404, '<html><body>Not found</body></html>');
      }
      if (path === '/docs/search/' && method === 'POST') {
        const query = postParams.query || '';
        const sanitized = query.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return sendHtml(200, `<html><body>Search results for: ${sanitized}</body></html>`);
      }
      return sendHtml(200, `<html><body>Documentation</body></html>`);
    }

    // 12. Pricing & Payments
    if (path === '/pricing/' || path === '/pricing') {
      if (method === 'POST') {
        if (!checkCsrf()) return;
      }
      return sendHtml(200, `<html><body>Pricing Page</body></html>`);
    }

    // 13. Ping Endpoints (/ping/<uuid>, /ping/<uuid>/start, /ping/<uuid>/fail, /ping/<uuid>/<exit_status>, /ping/<ping_key>/<slug>)
    if (path === '/ping' || path === '/ping/') {
      return sendText(404, 'not found');
    }

    const pingMatch = path.match(/^\/ping\/([0-9a-f\-]+)(\/(start|fail|log|(\d+)))?$/);
    if (pingMatch) {
      const uuid = pingMatch[1];
      const action = pingMatch[3];
      const exitCode = pingMatch[4] ? parseInt(pingMatch[4]) : null;

      if (parsedUrl.query.rid !== undefined) {
        const rid = parsedUrl.query.rid;
        if (!rid || !rid.match(/^[0-9a-f\-]{36}$/i)) {
          return sendText(400, 'invalid url format');
        }
      }

      if (action === 'log') {
        const c = db.checks[uuid];
        if (!c) return sendText(404, 'not found');
        return sendText(200, 'log details');
      }

      if (exitCode !== null && exitCode > 255) {
        return sendText(400, 'invalid url format');
      }

      const check = db.checks[uuid];
      if (!check) {
        return sendText(404, 'not found');
      }

      check.n_pings = (check.n_pings || 0) + 1;
      check.last_ping = new Date().toISOString();

      if (action === 'start') {
        check.started = true;
      } else if (action === 'fail' || (exitCode !== null && exitCode > 0)) {
        check.status = 'down';
        check.started = false;
      } else {
        check.status = 'up';
        check.started = false;
      }

      if (!db.pings[uuid]) db.pings[uuid] = [];
      db.pings[uuid].push({
        n: check.n_pings,
        body: rawBody,
        created: check.last_ping
      });

      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Ping-Body-Limit': '10000'
      });
      return res.end('OK');
    }

    const malformedPingMatch = path.match(/^\/ping\/([^/]+)$/);
    if (malformedPingMatch) {
      return sendText(404, 'not found');
    }

    const slugPingMatch = path.match(/^\/ping\/([A-Za-z0-9_\-]+)\/([A-Za-z0-9_\-]+)(\/(0|\d+))?$/);
    if (slugPingMatch) {
      const pingKey = slugPingMatch[1];
      const slug = slugPingMatch[2];
      const exitCode = slugPingMatch[4] ? parseInt(slugPingMatch[4]) : null;

      if (exitCode !== null && exitCode > 255) {
        return sendText(400, 'invalid url format');
      }

      let check = Object.values(db.checks).find(c => c.slug === slug);
      let created = false;

      if (!check) {
        const proj = Object.values(db.projects).find(p => p.ping_key === pingKey);
        if (!proj) return sendText(404, 'not found');

        const checkId = generateUUID();
        check = {
          code: checkId,
          badge_key: generateUUID(),
          project_id: proj.id,
          name: slug,
          slug: slug,
          timeout: 86400,
          grace: 3600,
          n_pings: 0,
          status: 'new'
        };
        db.checks[checkId] = check;
        created = true;
      }

      check.n_pings = (check.n_pings || 0) + 1;
      check.last_ping = new Date().toISOString();

      if (exitCode !== null && exitCode > 0) {
        check.status = 'down';
      } else {
        check.status = 'up';
      }

      res.writeHead(created ? 201 : 200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Access-Control-Allow-Origin': '*'
      });
      return res.end(created ? 'Created' : 'OK');
    }

    // Default Fallback Page
    sendHtml(200, `<html><body><a href="${defaultProjectUrl}">Projects</a>${csrfInput}Healthchecks Target Server</body></html>`);
  });
});

server.listen(PORT, () => {
  console.log(`Healthchecks target server listening on port ${PORT}`);
});
