'use strict';

// Hexo server extension: serve this project from its own working copy while
// `hexo s` is running on the lisakov.com Hexo site. The page is not part of
// that site's `source/` — it is rsync'd to
// /var/www/lisakov.com/projects/open-source-comments by updater.sh, and
// `lisync` excludes the path from `hexo deploy`. This middleware mounts the
// working copy at the URL it has in production, so the page previews exactly
// as it will be served.
//
// It lives here rather than in the Hexo site because that site is not under
// version control. The site keeps a three-line `scripts/osc-preview.js` that
// requires this file, so the behaviour is versioned with the page it previews.
// Note that a Hexo `scripts/` file is dev-server tooling: it never becomes
// part of the generated site, so `hexo generate`/`deploy` has nothing to
// publish for it.
//
// Override the location with OSC_DIR, e.g.
//   OSC_DIR=~/src/open-source-comments hexo s
//
// The Isso comment server answers CORS only for the lisakov.com origin, so a
// page on localhost cannot call it directly. Rather than widen that server's
// config, its API is proxied through this one: the browser then talks to its
// own origin and CORS never comes into it. The proxy is READ-ONLY — a local
// preview must not be able to write into the live comment database. Turn it
// off with OSC_ISSO_PROXY=off.

const path = require('path');
const os = require('os');
const fs = require('fs');
const https = require('https');
const { URL } = require('url');

const MOUNT = '/projects/open-source-comments';
const API_PREFIX = '/isso-api';

const ISSO_UPSTREAM = process.env.OSC_ISSO_UPSTREAM || 'https://comments.lisakov.com';
// The origin the Isso server is configured to accept, sent upstream on the
// browser's behalf.
const ISSO_ORIGIN = process.env.OSC_ISSO_ORIGIN || 'https://lisakov.com';
const ISSO_REFERER = ISSO_ORIGIN + MOUNT + '/';

// Reading is all the preview needs: no posting, editing, deleting or voting.
const READ_ONLY_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

// Isso renders the comment preview server-side, so its Preview button is a
// POST — but one that only echoes markdown back as HTML and touches no data.
// It is the single write-shaped request the preview is allowed to make.
const SAFE_POST_PATHS = new Set(['/preview']);

// Hop-by-hop headers, plus the CORS headers that only meant something upstream.
const DROPPED_HEADERS = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade',
  'access-control-allow-origin', 'access-control-allow-credentials',
  'access-control-allow-methods', 'access-control-allow-headers',
  'access-control-expose-headers',
]);

const oscDir = path.resolve(
  process.env.OSC_DIR || path.join(os.homedir(), 'open-source-comments')
);
const indexPath = path.join(oscDir, 'index.html');

function issoProxy(log) {
  const upstream = new URL(ISSO_UPSTREAM);

  return function (req, res) {
    const pathname = (req.url || '/').split('?')[0];
    const allowed = READ_ONLY_METHODS.has(req.method)
      || (req.method === 'POST' && SAFE_POST_PATHS.has(pathname));
    if (!allowed) {
      res.writeHead(405, {
        'content-type': 'text/plain; charset=utf-8',
        allow: 'GET, HEAD, OPTIONS',
      });
      log.info('osc-preview: refused %s %s (read-only proxy)', req.method, pathname);
      res.end(
        'The local Isso proxy is read-only, so the preview cannot write to the '
        + 'live comment database. Post from ' + ISSO_ORIGIN + MOUNT + '/ instead.\n'
      );
      return;
    }

    const headers = Object.assign({}, req.headers, {
      host: upstream.host,
      origin: ISSO_ORIGIN,
      referer: ISSO_REFERER,
    });
    // Ask upstream for the real answer rather than letting it reply 304 to a
    // validator the browser holds against a different URL.
    delete headers['if-none-match'];
    delete headers['if-modified-since'];

    const upstreamReq = https.request({
      protocol: upstream.protocol,
      hostname: upstream.hostname,
      port: upstream.port || 443,
      method: req.method,
      path: req.url || '/',
      headers: headers,
      timeout: 10000,
    }, function (upstreamRes) {
      const out = {};
      Object.keys(upstreamRes.headers).forEach(function (name) {
        if (!DROPPED_HEADERS.has(name.toLowerCase())) out[name] = upstreamRes.headers[name];
      });
      res.writeHead(upstreamRes.statusCode, out);
      upstreamRes.pipe(res);
    });

    upstreamReq.on('timeout', function () { upstreamReq.destroy(new Error('timed out')); });
    upstreamReq.on('error', function (error) {
      log.warn('osc-preview: Isso proxy failed: %s', error.message);
      if (res.headersSent) { res.destroy(); return; }
      res.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
      res.end('Could not reach ' + ISSO_UPSTREAM + ': ' + error.message + '\n');
    });

    req.pipe(upstreamReq);
  };
}

// Point the page's Isso endpoint at the proxy, for this response only — the
// index.html on disk keeps the production URL and is never rewritten.
function serveRewrittenIndex(res, log) {
  fs.readFile(indexPath, 'utf8', function (error, html) {
    if (error) {
      log.warn('osc-preview: could not read %s: %s', indexPath, error.message);
      res.writeHead(500, { 'content-type': 'text/plain; charset=utf-8' });
      res.end(error.message + '\n');
      return;
    }
    const body = Buffer.from(
      html.replace(/data-isso="[^"]*"/, 'data-isso="' + MOUNT + API_PREFIX + '/"'),
      'utf8'
    );
    res.writeHead(200, {
      'content-type': 'text/html; charset=utf-8',
      'content-length': body.length,
      'cache-control': 'no-store',
    });
    res.end(body);
  });
}

// `serveStatic` is passed in by the loader in the Hexo site: this repository
// has no node_modules of its own, so the dependency has to be resolved there.
module.exports = function register(hexo, serveStatic) {
  hexo.extend.filter.register('server_middleware', function (app) {
    if (!fs.existsSync(indexPath)) {
      this.log.warn(
        'osc-preview: no index.html in %s — %s will 404. Set OSC_DIR to the working copy.',
        oscDir, MOUNT
      );
      return;
    }

    const log = this.log;
    log.info('osc-preview: serving %s from %s', MOUNT, oscDir);

    if (process.env.OSC_ISSO_PROXY === 'off') {
      log.info('osc-preview: Isso proxy off; comments will not load locally');
    } else {
      log.info('osc-preview: proxying Isso read-only to %s', ISSO_UPSTREAM);
      app.use(MOUNT + API_PREFIX, issoProxy(log));
      app.use(MOUNT, function (req, res, next) {
        const pathname = req.url.split('?')[0];
        if (pathname !== '/' && pathname !== '/index.html') return next();
        serveRewrittenIndex(res, log);
      });
    }

    app.use(MOUNT, serveStatic(oscDir, {
      index: ['index.html'],
      etag: false,
      lastModified: true,
      setHeaders(res) {
        // Always re-read from disk: the point of the preview is to see edits.
        res.setHeader('Cache-Control', 'no-store');
      }
    }));
  });
};
