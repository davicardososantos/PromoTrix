/** @type {import('next').NextConfig} */
const nextConfig = {
  // Saída standalone para imagem Docker enxuta (ver Dockerfile), no mesmo padrão do Fintrix.
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
