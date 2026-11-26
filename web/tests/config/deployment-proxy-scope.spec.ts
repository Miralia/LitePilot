import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('deployment proxy scope', () => {
  it('does not retain removed CookieCloud proxy routes', () => {
    const nginxConfig = readFileSync('public/nginx.conf', 'utf-8')

    expect(nginxConfig).not.toContain('/cookiecloud')
    expect(nginxConfig).not.toContain('CookieCloud')
  })

  it('does not ship the superseded source service script or its runtime-only dependencies', () => {
    const packageJson = JSON.parse(readFileSync('package.json', 'utf-8'))

    expect(existsSync('public/service.js')).toBe(false)
    expect(packageJson.dependencies).not.toHaveProperty('express')
    expect(packageJson.dependencies).not.toHaveProperty('express-http-proxy')
  })
})
