/**
 * dsh-shutup — host half.
 *
 * Cancels the web startup token gate (`?token=` -> signed cookie) by
 * neutralizing the `connection` service's browser authentication, while
 * keeping the Host trust fence (loopback / --trusted-host 403s) intact.
 *
 * What gets patched (instance + prototype, so reloads stay patched):
 * - `requestRejection(req)`: 401 (missing/invalid cookie) becomes "allow",
 *   403 (untrusted Host / cross-site) is preserved.
 * - `authorizeIndex(req, res)`: always allow serving index.html; never 401.
 * - `authenticatedUrl(baseUrl)`: return the clean `/` URL with no token,
 *   so the `dsh web:` line and the auto-opened browser carry no secret.
 * - `browserAuth.isAuthenticated`: forced true as defense-in-depth.
 *
 * The `--no-open` inversion itself is declarative in cordis.patch.yml
 * (`openBrowser: !!js "!ctx.webStartup.openBrowser"`); this file only
 * handles the token gate.
 */

export const name = 'shutup'

function cleanRootUrl(baseUrl) {
  try {
    const u = new URL(baseUrl)
    u.pathname = '/'
    u.search = ''
    u.hash = ''
    return u.href
  } catch {
    return baseUrl
  }
}

function patchConnectionInstance(conn) {
  if (!conn || conn.__shutup_patched) return false
  conn.__shutup_patched = true

  // --- instance-level patches (affect the live object the routes close over) ---
  const origRejection = typeof conn.requestRejection === 'function'
    ? conn.requestRejection.bind(conn)
    : null
  conn.requestRejection = (req) => {
    if (!origRejection) return undefined
    const code = origRejection(req)
    // Drop the auth layer (401), keep the trust fence (403).
    if (code === 401) return undefined
    return code
  }

  conn.authorizeIndex = () => true

  conn.authenticatedUrl = (baseUrl) => cleanRootUrl(baseUrl)

  try {
    const ba = conn.browserAuth
    if (ba && !ba.__shutup_patched) {
      ba.__shutup_patched = true
      if (typeof ba.isAuthenticated === 'function') ba.isAuthenticated = () => true
      if (typeof ba.authorizeIndex === 'function') ba.authorizeIndex = () => true
      if (typeof ba.authenticatedUrl === 'function') {
        ba.authenticatedUrl = (baseUrl) => cleanRootUrl(baseUrl)
      }
    }
  } catch {
    /* best-effort: the connection-level patches above already cover serving */
  }

  return true
}

function patchConnectionPrototype(conn) {
  try {
    const proto = conn && Object.getPrototypeOf(conn)
    if (!proto || proto.__shutup_patched) return
    proto.__shutup_patched = true

    if (typeof proto.requestRejection === 'function') {
      const orig = proto.requestRejection
      proto.requestRejection = function (req) {
        const code = orig.call(this, req)
        return code === 401 ? undefined : code
      }
    }
    if (typeof proto.authorizeIndex === 'function') {
      proto.authorizeIndex = function () { return true }
    }
    if (typeof proto.authenticatedUrl === 'function') {
      proto.authenticatedUrl = function (baseUrl) { return cleanRootUrl(baseUrl) }
    }
    if (typeof proto.isAuthenticated === 'function') {
      proto.isAuthenticated = function () { return true }
    }

    // BrowserAuth instance hanging off the connection may come from the same
    // module copy; patch its prototype too when reachable.
    try {
      const ba = conn?.browserAuth
      const baProto = ba && Object.getPrototypeOf(ba)
      if (baProto && !baProto.__shutup_patched) {
        baProto.__shutup_patched = true
        if (typeof baProto.isAuthenticated === 'function') {
          baProto.isAuthenticated = function () { return true }
        }
        if (typeof baProto.authorizeIndex === 'function') {
          baProto.authorizeIndex = function () { return true }
        }
        if (typeof baProto.authenticatedUrl === 'function') {
          baProto.authenticatedUrl = function (baseUrl) { return cleanRootUrl(baseUrl) }
        }
      }
    } catch {
      /* ignore */
    }
  } catch {
    /* ignore */
  }
}

export function apply(ctx) {
  // `connection` appears after webRuntime resolves; inject fires then and on
  // every later re-provision (HMR / reload), so the patch sticks.
  ctx.inject(['connection'], (c) => {
    const conn = c.connection
    if (!conn || conn.__shutup_patched) return
    patchConnectionInstance(conn)
    patchConnectionPrototype(conn)
    try {
      ctx.logger?.info?.('[shutup] token gate disabled: serving web UI without ?token=')
    } catch {
      /* logger is best-effort */
    }
    console.log('[shutup] token auth disabled: open the printed URL directly, no ?token= needed')
  })
}
