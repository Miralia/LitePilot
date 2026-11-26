export function removeEl(selector: string) {
  if (selector) {
    const el = document.querySelector(selector)
    el?.parentNode?.removeChild(el)
  }
}

export function ensureRenderComplete(callback: () => void) {
  requestAnimationFrame(() => {
    requestAnimationFrame(callback)
  })
}
