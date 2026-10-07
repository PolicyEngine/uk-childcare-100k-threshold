/** @type {import('next').NextConfig} */
// One source for the base path: the components read the same file for plain <img src> URLs.
import basePathConfig from "./src/lib/basePath.json" with { type: "json" };

const { basePath } = basePathConfig;

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@policyengine/ui-kit"],
  // Served through the policyengine.org multizone rewrite at
  // /uk/childcare-100k-threshold, so pages and /_next assets must
  // resolve under that prefix.
  basePath,
  // Keep the bare deployment URL (linked from the README and repo page)
  // working now that the app lives under basePath.
  async redirects() {
    return [
      { source: "/", destination: basePath, basePath: false, permanent: false },
    ];
  },
};

export default nextConfig;
