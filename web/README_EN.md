# LitePilot Frontend

_[中文](README.md) | English_

Frontend application for LitePilot. The user interface is Simplified Chinese only.

## Requirements

- Node.js `>= 20.19`
- Corepack with Yarn 1

## Features

- Vue 3, TypeScript and Vuetify 3
- Vite development and production builds
- Route-level lazy loading for large visualization and editor dependencies
- Progressive Web App support for the production build

## Development

Install dependencies:

```sh
corepack yarn install
```

Start the development server:

```sh
corepack yarn dev
```

Run checks:

```sh
corepack yarn typecheck
corepack yarn lint
corepack yarn test:run
```

Build for production:

```sh
corepack yarn build
```

The production output is written to `dist/`. LitePilot's local CLI builds this directory from the repository source and copies it to the top-level `public/` runtime directory; it does not download an upstream frontend release.
