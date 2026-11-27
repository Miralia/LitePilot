// 目录路径在前后端交互中统一使用末尾斜杠形式。
export function normalizeDirectoryPath(path: string) {
  if (!path) return '/'
  return path.endsWith('/') ? path : `${path}/`
}

// 获取目录路径根；POSIX 根为 /，Windows 盘符根保留盘符。
export function getDirectoryRoot(path: string) {
  return path.match(/^[A-Za-z]:\//)?.[0] ?? '/'
}

// 生成从根到当前目录的 canonical 目录链。
export function getDirectoryChain(path: string) {
  const normalizedPath = normalizeDirectoryPath(path)
  const root = getDirectoryRoot(normalizedPath)
  const chain = [root]
  let currentPath = root

  normalizedPath
    .slice(root.length)
    .split('/')
    .filter(part => part)
    .forEach(part => {
      currentPath = `${currentPath}${part}/`
      chain.push(currentPath)
    })

  return chain
}

// 获取 canonical 目录的父目录；存储根和盘符根的父级统一为 /。
export function getParentDirectoryPath(path: string) {
  const normalizedPath = normalizeDirectoryPath(path)
  if (normalizedPath === '/') return '/'

  const chain = getDirectoryChain(normalizedPath)
  const currentIndex = chain.lastIndexOf(normalizedPath)
  return currentIndex > 0 ? chain[currentIndex - 1] : '/'
}

// 获取目录项展示名；Windows 盘符根与后端返回的目录项名称保持一致。
export function getDirectoryName(path: string) {
  const normalizedPath = normalizeDirectoryPath(path)
  if (normalizedPath === '/') return '/'
  if (/^[A-Za-z]:\/$/.test(normalizedPath)) return normalizedPath.slice(0, -1)
  return normalizedPath.slice(0, -1).split('/').pop() ?? ''
}
