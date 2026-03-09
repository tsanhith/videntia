/**
 * @type {import('next').NextConfig}
 */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    // ESLint is run separately in CI (or locally via `npm run lint`).
    // Disabling here prevents `next build` from invoking `next lint`
    // interactively when the runner has no ESLint config cached.
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
