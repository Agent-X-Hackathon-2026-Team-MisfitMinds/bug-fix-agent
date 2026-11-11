/** @type {import('next').NextConfig} */
const backend = process.env.API_BACKEND_URL;
const config = {
  output: 'standalone',
  devIndicators: false,
  allowedDevOrigins: ['*.trycloudflare.com'],
  async rewrites() {
    return backend ? [
      { source: '/api/:path*', destination: `${backend}/:path*` },
      { source: '/auth/github', destination: `${backend}/auth/github` },
      { source: '/auth/callback', destination: `${backend}/auth/callback` },
      { source: '/webhooks/:path*', destination: `${backend}/webhooks/:path*` },
    ] : [];
  },
};
export default config;
