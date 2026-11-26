/// <reference types="vitest/config" />

import { fileURLToPath } from 'node:url'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'
import { VitePWA } from 'vite-plugin-pwa'
import { readFileSync } from 'node:fs'
import { responsiveInputCoreComponentNames } from './src/plugins/vuetify/responsiveInputNames'
import {
  createDevServiceWorkerCleanupPlugin,
  isPwaDevelopmentEnabled,
  shouldEnableDevServiceWorkerCleanup,
} from './scripts/pwa-development'

// 读取 package.json 获取版本号
const packageJson = JSON.parse(readFileSync('./package.json', 'utf-8'))

// 版本号的唯一来源是仓库根的 version.py（后端 APP_VERSION）：
// 构建脚本把同一值写入 dist/version.txt，前端内嵌版本必须与之保持一致，
// 否则登录后会误报「浏览器缓存版本与服务端版本不一致」。
const appVersion = (() => {
  try {
    const raw = readFileSync('../version.py', 'utf-8')
    const matched = raw.match(/^APP_VERSION\s*=\s*['"]([^'"]+)['"]/m)
    return matched ? matched[1] : `v${packageJson.version}`
  } catch {
    return `v${packageJson.version}`
  }
})()
const buildTime = new Date().getTime().toString()
const isTestMode = (mode: string) => mode === 'test' || process.env.VITEST === 'true'

// https://vitejs.dev/config/
export default defineConfig(({ command, mode, isPreview }) => ({
  base: './',
  plugins: [
    shouldEnableDevServiceWorkerCleanup(command, mode, isPreview, process.env.npm_lifecycle_event) &&
      createDevServiceWorkerCleanupPlugin(),
    vue(),
    vueJsx(),
    vuetify({
      autoImport: {
        // 这些录入控件由 Vuetify 全局适配器接管，避免模板局部导入绕过移动布局。
        ignore: ['VDialog', ...responsiveInputCoreComponentNames],
      },
      styles: {
        configFile: 'src/styles/variables/_vuetify.scss',
      },
    }),
    Components({
      dirs: ['src/@core/components'],
      dts: !isTestMode(mode),
    }),
    AutoImport({
      imports: ['vue', 'vue-router', '@vueuse/core', 'pinia', 'vue-i18n'],
      vueTemplate: true,
      dts: !isTestMode(mode),
    }),
    !isTestMode(mode) &&
      VitePWA({
        injectRegister: false,
        strategies: 'injectManifest',
        srcDir: 'src',
        filename: 'service-worker.ts',
        injectManifest: {
          rollupFormat: 'iife',
          maximumFileSizeToCacheInBytes: 10 * 1024 * 1024,
          // 预缓存只放首屏必需的少量文件。
          // 若把全部 js 纳入预缓存，SW 首次安装会在后台下载 9MB
          // （three.js 720KB、ace 446KB、各语言 worker 1.4MB 等），
          // 与首屏资源抢带宽，反而让页面加载变得极慢。
          // 其余资源由运行时缓存策略按需处理（script/style 走
          // StaleWhileRevalidate，图片走 CacheFirst）。
          globPatterns: [
            'index.html',
            'offline.html',
            'manifest.webmanifest',
            'favicon.ico',
            'logo.svg',
            'logo.png',
            'apple-touch-icon*.png',
            'assets/index-*.js',
            'assets/index-*.css',
          ],
        },
        devOptions: {
          enabled: isPwaDevelopmentEnabled(mode, process.env.npm_lifecycle_event),
          type: 'module',
        },
        manifest: {
          'name': 'LitePilot',
          'short_name': 'LitePilot',
          'description': 'LitePilot - 智能影视媒体库管理工具',
          'start_url': './',
          'scope': './',
          'display': 'standalone',
          'display_override': ['window-controls-overlay', 'standalone'],
          'lang': 'zh-CN',
          'dir': 'ltr',
          'categories': ['entertainment', 'multimedia', 'utilities'],
          'icons': [
            {
              'src': './android-chrome-192x192.png',
              'sizes': '192x192',
              'type': 'image/png',
              'purpose': 'any',
            },
            {
              'src': './android-chrome-192x192_maskable.png',
              'sizes': '192x192',
              'type': 'image/png',
              'purpose': 'maskable',
            },
            {
              'src': './android-chrome-512x512.png',
              'sizes': '512x512',
              'type': 'image/png',
              'purpose': 'any',
            },
            {
              'src': './android-chrome-512x512_maskable.png',
              'sizes': '512x512',
              'type': 'image/png',
              'purpose': 'maskable',
            },
          ],
          'theme_color': '#0E1116',
          'background_color': '#0E1116',
          'edge_side_panel': {
            'preferred_width': 320,
          },
          'launch_handler': {
            'client_mode': 'navigate-existing',
          },
          'handle_links': 'preferred',
          'id': 'litepilot-app',
          'shortcuts': [
            {
              'name': '仪表盘',
              'short_name': '仪表盘',
              'description': '查看系统运行状态',
              'url': './#/dashboard',
            },
            {
              'name': '整理记录',
              'short_name': '整理记录',
              'description': '查看媒体整理记录',
              'url': './#/history',
            },
            {
              'name': '文件管理',
              'short_name': '文件管理',
              'description': '浏览和管理媒体文件',
              'url': './#/filemanager',
            },
          ],
          'prefer_related_applications': false,
          'related_applications': [],
        },
      }),
  ],
  define: {
    'process.env': {},
    '__APP_VERSION__': JSON.stringify(appVersion),
    '__BUILD_TIME__': JSON.stringify(buildTime),
    '__PWA_DEVELOPMENT__': JSON.stringify(isPwaDevelopmentEnabled(mode, process.env.npm_lifecycle_event)),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@core': fileURLToPath(new URL('./src/@core', import.meta.url)),
      '@layouts': fileURLToPath(new URL('./src/@layouts', import.meta.url)),
      '@images': fileURLToPath(new URL('./src/assets/images/', import.meta.url)),
      '@styles': fileURLToPath(new URL('./src/styles/', import.meta.url)),
      '@tests': fileURLToPath(new URL('./tests', import.meta.url)),
      '@configured-variables': fileURLToPath(new URL('./src/styles/variables/_template.scss', import.meta.url)),
      'apexcharts': fileURLToPath(new URL('node_modules/apexcharts', import.meta.url)),
    },
  },
  build: {
    target: 'esnext',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    chunkSizeWarningLimit: 5000,
    // CSS 按异步 chunk 拆分：首屏只需加载入口样式，
    // 页面级样式随路由懒加载，避免单文件累积到近 1MB
    // 注意：不要为 vue / vuetify 设置 manualChunks，避免破坏框架模块初始化顺序。
    cssCodeSplit: true,
  },
  optimizeDeps: {
    exclude: ['vuetify'],
    entries: ['./src/**/*.vue'],
  },
  server: {
    proxy: {
      '/api/v1': {
        target: 'http://localhost:3001',
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: 'localhost',
      },
    },
  },
  css: {
    preprocessorOptions: {
      sass: {
        api: 'modern-compiler',
        quietDeps: true,
      },
      scss: {
        api: 'modern-compiler',
        quietDeps: true,
      },
    },
  },
  test: {
    clearMocks: true,
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        pretendToBeVisual: true,
        url: 'http://localhost/',
      },
    },
    include: ['src/**/__tests__/**/*.spec.ts', 'tests/config/**/*.spec.ts'],
    restoreMocks: true,
    server: {
      deps: {
        inline: ['vuetify'],
      },
    },
    setupFiles: ['./tests/setup.ts'],
    testTimeout: 60_000,
    unstubGlobals: true,
    coverage: {
      include: [
        'src/components/dialog/ReorganizeDialog.vue',
        'src/components/dialog/TransferQueueDialog.vue',
        'src/components/filebrowser/FileBrowser.vue',
        'src/components/filebrowser/FileList.vue',
        'src/components/filebrowser/FileNavigator.vue',
        'src/components/filebrowser/FileToolbar.vue',
        'src/stores/auth.ts',
        'src/utils/permission.ts',
        'src/utils/requestOptimizer.ts',
        'src/utils/sseManager.ts',
        'src/views/reorganize/FileBrowserView.vue',
        'src/views/reorganize/TransferHistoryView.vue',
      ],
      provider: 'v8',
      reporter: ['text', 'json-summary', 'html'],
      reportsDirectory: 'coverage',
      thresholds: {
        branches: 80,
        functions: 85,
        lines: 85,
        statements: 85,
        'src/components/dialog/ReorganizeDialog.vue': {
          branches: 75,
          functions: 80,
          lines: 80,
          statements: 80,
        },
        'src/components/dialog/TransferQueueDialog.vue': {
          branches: 80,
          functions: 85,
          lines: 85,
          statements: 85,
        },
        'src/components/filebrowser/FileBrowser.vue': {
          branches: 80,
          functions: 85,
          lines: 85,
          statements: 85,
        },
        'src/components/filebrowser/FileList.vue': {
          branches: 75,
          functions: 80,
          lines: 80,
          statements: 80,
        },
        'src/components/filebrowser/FileNavigator.vue': {
          branches: 80,
          functions: 85,
          lines: 85,
          statements: 85,
        },
        'src/components/filebrowser/FileToolbar.vue': {
          branches: 80,
          functions: 85,
          lines: 85,
          statements: 85,
        },
        'src/stores/auth.ts': {
          branches: 75,
          functions: 80,
          lines: 80,
          statements: 80,
        },
        'src/utils/permission.ts': {
          branches: 75,
          functions: 80,
          lines: 80,
          statements: 80,
        },
        'src/utils/requestOptimizer.ts': {
          branches: 85,
          functions: 90,
          lines: 90,
          statements: 90,
        },
        'src/utils/sseManager.ts': {
          branches: 85,
          functions: 90,
          lines: 90,
          statements: 90,
        },
        'src/views/reorganize/FileBrowserView.vue': {
          branches: 80,
          functions: 85,
          lines: 85,
          statements: 85,
        },
        'src/views/reorganize/TransferHistoryView.vue': {
          branches: 75,
          functions: 80,
          lines: 80,
          statements: 80,
        },
      },
    },
  },
}))
