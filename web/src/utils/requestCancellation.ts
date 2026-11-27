import axios from 'axios'

/** 判断异常是否来自主动取消的请求，避免把路由切换提示为用户操作失败。 */
export function isRequestCancellation(error: unknown): boolean {
  if (axios.isCancel(error)) return true
  if (!error || typeof error !== 'object') return false

  const candidate = error as { code?: unknown; name?: unknown }
  return candidate.code === 'ERR_CANCELED' || candidate.name === 'AbortError' || candidate.name === 'CanceledError'
}
