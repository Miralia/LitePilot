/**
 * 从项目源码扫描实际使用的 Iconify 图标，并生成按需集合。
 * 构建只打包使用到的图标，避免把完整图标库放进浏览器入口包。
 */
import { promises as fs } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

// Get current directory
const __dirname = dirname(fileURLToPath(import.meta.url))
const projectSrcDir = join(__dirname, '..')

// Create require function for importing JSON files in ESM
const require = createRequire(import.meta.url)

// Installation: npm install --save-dev @iconify/utils @iconify/json @iconify/iconify
import type { IconifyJSON, IconifyMetaData } from '@iconify/types'
import { getIcons, minifyIconSet, stringToIcon } from '@iconify/utils'

/**
 * Script configuration
 */
interface BundleScriptCustomJSONConfig {
  // Path to JSON file
  filename: string

  // List of icons to import. If missing, all icons will be imported
  icons?: string[]
}

interface BundleScriptConfig {
  // Icons to bundled from @iconify/json packages
  icons?: string[]

  // List of JSON files to bundled
  // Entry can be a string, pointing to filename or a BundleScriptCustomJSONConfig object (see type above)
  // If entry is a string or object without 'icons' property, an entire JSON file will be bundled
  json?: (string | BundleScriptCustomJSONConfig)[]
}

const sources: BundleScriptConfig = {
  icons: ['lucide:sparkles', 'line-md:loading-twotone-loop'],

  json: [],
}

// Iconify component (this changes import statement in generated file)
// Available options: '@iconify/react' for React, '@iconify/vue' for Vue 3, '@iconify/vue2' for Vue 2, '@iconify/svelte' for Svelte
const component = '@iconify/vue'

// Set to true to use require() instead of import
const commonJS = false

// File to save bundle to
const target = join(__dirname, 'icons-bundle.js')

/**
 * Do stuff!
 */
// eslint-disable-next-line sonarjs/cognitive-complexity
;(async function () {
  const scannedIcons = await collectUsedIcons(projectSrcDir)

  if (sources.icons) {
    sources.icons.push(...scannedIcons)
    sources.icons = Array.from(new Set(sources.icons)).sort()
  } else {
    sources.icons = scannedIcons
  }

  let bundle = commonJS
    ? `const { addCollection } = require('${component}');\n\n`
    : `import { addCollection } from '${component}';\n\n`

  // Create directory for output if missing
  const dir = dirname(target)
  try {
    await fs.mkdir(dir, {
      recursive: true,
    })
  } catch (err) {
    //
  }

  /**
   * Convert sources.icons to sources.json
   */
  if (sources.icons) {
    const sourcesJSON = sources.json ? sources.json : (sources.json = [])

    // Sort icons by prefix
    const organizedList = organizeIconsList(sources.icons)
    for (const prefix in organizedList) {
      let filename
      try {
        filename = require.resolve(`@iconify-json/${prefix}/icons.json`)
      } catch (err) {
        filename = require.resolve(`@iconify/json/json/${prefix}.json`)
      }

      sourcesJSON.push({
        filename,
        icons: organizedList[prefix],
      })
    }
  }

  /**
   * Bundle JSON files
   */
  if (sources.json) {
    for (let i = 0; i < sources.json.length; i++) {
      const item = sources.json[i]

      // Load icon set
      const filename = typeof item === 'string' ? item : item.filename
      let content = JSON.parse(await fs.readFile(filename, 'utf8')) as IconifyJSON

      // Filter icons
      if (typeof item !== 'string' && item.icons?.length) {
        const filteredContent = getIcons(content, item.icons)
        if (!filteredContent) throw new Error(`Cannot find required icons in ${filename}`)

        content = filteredContent
      }

      // Remove metadata and add to bundle
      removeMetaData(content)
      minifyIconSet(content)
      bundle += `addCollection(${JSON.stringify(content)});\n`
      console.log(`Bundled icons from ${filename}`)
    }
  }

  // Save to file
  await fs.writeFile(target, bundle, 'utf8')

  console.log(`Saved ${target} (${bundle.length} bytes)`)
})().catch(err => {
  console.error(err)
  // 构建图标失败时必须终止构建，避免继续发布上一次遗留的超大 icons-bundle。
  process.exitCode = 1
})

async function collectUsedIcons(rootDir: string): Promise<string[]> {
  const icons = new Set<string>()
  const files = await walkDirectory(rootDir)
  const sourceFiles = files.filter(file => /\.(vue|ts|js|tsx|jsx)$/.test(file))

  for (const file of sourceFiles) {
    if (file.includes('/@iconify/')) {
      continue
    }

    const content = await fs.readFile(file, 'utf8')

    for (const match of content.matchAll(/\b(lucide|material-symbols|line-md|tabler):([a-z0-9-]+)\b/g)) {
      icons.add(`${match[1]}:${match[2]}`)
    }

    for (const match of content.matchAll(/\bmdi:([a-z0-9-]+)\b/g)) {
      icons.add(`mdi:${match[1]}`)
    }

    for (const match of content.matchAll(/\btabler-([a-z0-9-]+)\b/g)) {
      icons.add(`tabler:${match[1]}`)
    }

    for (const match of content.matchAll(/\bmdi-([a-z0-9-]+)\b/g)) {
      icons.add(`mdi:${match[1]}`)
    }
  }

  return Array.from(icons).sort()
}

async function walkDirectory(dir: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries) {
    const fullPath = join(dir, entry.name)

    if (entry.isDirectory()) {
      files.push(...(await walkDirectory(fullPath)))
      continue
    }

    files.push(fullPath)
  }

  return files
}

/**
 * Remove metadata from icon set
 */
function removeMetaData(iconSet: IconifyJSON) {
  const props: (keyof IconifyMetaData)[] = ['info', 'chars', 'categories', 'themes', 'prefixes', 'suffixes']

  props.forEach(prop => {
    delete iconSet[prop]
  })
}

/**
 * Sort icon names by prefix
 */
function organizeIconsList(icons: string[]): Record<string, string[]> {
  const sorted: Record<string, string[]> = Object.create(null)

  icons.forEach(icon => {
    const item = stringToIcon(icon)
    if (!item) return

    const prefix = item.prefix

    const prefixList = sorted[prefix] ? sorted[prefix] : (sorted[prefix] = [])

    const name = item.name
    if (!prefixList.includes(name)) prefixList.push(name)
  })

  return sorted
}
