import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('deployment proxy scope', () => {
  it('does not ship the superseded upstream nginx template', () => {
    expect(existsSync('public/nginx.conf')).toBe(false)
  })

  it('does not ship the superseded source service script or its runtime-only dependencies', () => {
    const packageJson = JSON.parse(readFileSync('package.json', 'utf-8'))

    expect(existsSync('public/service.js')).toBe(false)
    expect(packageJson.dependencies).not.toHaveProperty('express')
    expect(packageJson.dependencies).not.toHaveProperty('express-http-proxy')
    expect(packageJson).not.toHaveProperty('bin')
    expect(packageJson).not.toHaveProperty('pkg')
    expect(packageJson.scripts).not.toHaveProperty('pkg')
  })
})
