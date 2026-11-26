import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cwd } from 'node:process'
import { describe, expect, it } from 'vitest'

function readRepositoryFile(path: string) {
  return readFileSync(resolve(cwd(), '..', path), 'utf-8')
}

describe('frontend CI workflow', () => {
  it('runs the complete frontend quality gate for main pushes and pull requests', () => {
    const workflow = readRepositoryFile('.github/workflows/test.yml')

    expect(workflow).toContain('pull_request:')
    expect(workflow).toContain('push:')
    expect(workflow).toContain('frontend:')
    expect(workflow).toContain('corepack enable')
    expect(workflow).toContain("node-version: '24.22.3'")
    expect(workflow).toContain('corepack yarn install --frozen-lockfile')
    expect(workflow).toContain('corepack yarn lint')
    expect(workflow).toContain('corepack yarn typecheck')
    expect(workflow).toContain('corepack yarn test:run')
    expect(workflow).toContain('corepack yarn build')
  })

  it('runs pylint for main pushes and pull requests instead of manual-only dispatch', () => {
    const workflow = readRepositoryFile('.github/workflows/pylint.yml')

    expect(workflow).toContain('pull_request:')
    expect(workflow).toContain('push:')
  })
})
