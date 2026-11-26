import type { MediaInfo } from '@/api/types'

/** 媒体身份：按媒体声明的主来源解析出的稳定标识。 */
export interface MediaIdentity {
  mediaId: string
  mediaKey: string
  source: string
}

/** 按媒体声明的主来源解析媒体身份，避免辅助 ID 覆盖原始识别源。 */
export function getMediaIdentity(media?: MediaInfo): MediaIdentity | undefined {
  if (!media) return undefined

  const normalizeSource = (value?: string) => {
    const source = (value || '').trim().toLowerCase()
    return source === 'tmdb' ? 'themoviedb' : source
  }
  const sourceIds: Record<string, unknown> = {
    bangumi: media.bangumi_id,
    douban: media.douban_id,
    themoviedb: media.tmdb_id,
  }
  const buildIdentity = (identitySource: string, value: unknown): MediaIdentity | undefined => {
    if (value === undefined || value === null || !String(value).trim()) return undefined
    const mediaId = String(value).trim()
    const prefix = identitySource === 'themoviedb' ? 'tmdb' : identitySource
    return {
      mediaId,
      mediaKey: `${prefix}:${mediaId}`,
      source: identitySource,
    }
  }

  const declaredSources = [media.mediaid_prefix, media.source]
    .map(normalizeSource)
    .filter((source, index, sources) => source && sources.indexOf(source) === index)
  for (const source of declaredSources) {
    const declaredIdentity = buildIdentity(source, media.media_id ?? sourceIds[source])
    if (declaredIdentity) return declaredIdentity
  }

  for (const fallbackSource of ['themoviedb', 'bangumi', 'douban']) {
    const fallbackIdentity = buildIdentity(fallbackSource, sourceIds[fallbackSource])
    if (fallbackIdentity) return fallbackIdentity
  }
  return undefined
}
