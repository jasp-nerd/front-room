// Asset and style imports, resolved by Vite in the web app and by esbuild in the bundle.
declare module "*.module.css" {
  const classes: Record<string, string>;
  export default classes;
}
declare module "*.svg" {
  const url: string;
  export default url;
}
declare module "*.webp" {
  const url: string;
  export default url;
}
declare module "*.png" {
  const url: string;
  export default url;
}
