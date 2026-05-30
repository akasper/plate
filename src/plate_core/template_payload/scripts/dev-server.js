const http = require('http');

const port = Number(process.env.PORT || 3000);

function page(title, body) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${title}</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 2rem; line-height: 1.5; }
      form { display: grid; gap: 0.75rem; max-width: 24rem; }
      input, button { font: inherit; padding: 0.5rem 0.75rem; }
      button { width: fit-content; }
    </style>
  </head>
  <body>
    ${body}
  </body>
</html>`;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);

  if (url.pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(page('PLATE Template Demo', '<h1>PLATE Template</h1><p>Playwright E2E demo home page.</p>'));
    return;
  }

  if (url.pathname === '/login') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(page('Login', `
      <h1>Login</h1>
      <form>
        <label>
          Email
          <input type="email" name="email" autocomplete="email" />
        </label>
        <label>
          Password
          <input type="password" name="password" autocomplete="current-password" />
        </label>
        <button type="submit">Sign in</button>
      </form>
    `));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('Not found');
});

server.listen(port, () => {
  console.log(`PLATE demo server listening on http://localhost:${port}`);
});
