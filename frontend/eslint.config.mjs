// eslint-config-next 16 ships a native flat config array, so it is spread
// directly. (The FlatCompat shim that older Next projects use crashes against
// it with a circular-structure error.)
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...nextCoreWebVitals,
  ...nextTypescript,
];

export default config;
