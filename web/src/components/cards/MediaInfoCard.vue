<script lang="ts" setup>
import type { PropType } from 'vue'
import type { Context } from '@/api/types'
import { isNullOrEmptyObject } from '@/@core/utils'

// 输入参数
defineProps({
  context: Object as PropType<Context>,
})

// TMDB图片转换为w500大小
function getW500Image(url = '') {
  if (!url) return ''
  return url.replace('original', 'w500')
}

// 打开TMDB详情页面
function openTmdbPage(type: string, tmdbId: number) {
  if (!type || !tmdbId) return

  const url = `https://www.themoviedb.org/${type === '电影' ? 'movie' : 'tv'}/${tmdbId}`
  window.open(url, '_blank')
}
</script>

<template>
  <div v-show="context">
    <VCol>
      <div
        v-if="context?.meta_info?.name"
        class="d-flex justify-space-between flex-wrap flex-md-nowrap flex-column flex-md-row"
      >
        <div v-if="context?.media_info?.poster_path" class="ma-auto">
          <VImg
            width="10rem"
            aspect-ratio="2/3"
            class="object-cover aspect-w-2 aspect-h-3 rounded-lg ring-1 ring-gray-500"
            :src="getW500Image(context?.media_info?.poster_path)"
            cover
          >
            <template #placeholder>
              <div class="w-full h-full">
                <VSkeletonLoader class="object-cover aspect-w-2 aspect-h-3" />
              </div>
            </template>
          </VImg>
        </div>
        <div class="flex-grow">
          <VCardItem class="pb-1">
            <div class="text-center text-md-left text-h6 font-weight-bold line-clamp-2 overflow-hidden text-ellipsis">
              {{ context?.media_info?.title || context?.meta_info?.name }}
              <span v-if="context?.meta_info?.season_episode" class="text-sm text-medium-emphasis align-top">
                {{ context?.meta_info?.season_episode }}
              </span>
            </div>
            <VCardSubtitle class="text-center text-md-left">
              {{ context?.media_info?.year || context?.meta_info?.year }}
            </VCardSubtitle>
          </VCardItem>

          <VCardText
            v-if="context?.media_info?.overview"
            class="line-clamp-4 overflow-hidden text-ellipsis text-center text-md-left ..."
          >
            {{ context?.media_info?.overview }}
          </VCardText>

          <VCardItem class="text-center text-md-left">
            <!-- 类型 -->
            <VChip
              v-if="context?.media_info?.type || context?.meta_info?.type"
              variant="elevated"
              class="me-1 mb-1 text-white bg-blue-500"
            >
              {{ context?.media_info?.type || context?.meta_info?.type }}
            </VChip>
            <!-- TMDBID -->
            <VChip
              v-if="context?.media_info?.tmdb_id"
              variant="elevated"
              class="me-1 mb-1 text-white bg-green-500"
              @click="openTmdbPage(context?.media_info?.type || '', context?.media_info?.tmdb_id)"
            >
              {{ context?.media_info?.tmdb_id }}
            </VChip>
            <!-- meta_info -->
            <VChip v-if="context?.meta_info?.web_source" variant="elevated" class="me-1 mb-1 text-white bg-purple-500">
              {{ context?.meta_info?.web_source }}
            </VChip>
            <!-- 来源 -->
            <VChip v-if="context?.meta_info?.resource_type" variant="elevated" class="me-1 mb-1 text-white bg-red-500">
              {{ context?.meta_info?.resource_type }}
            </VChip>
            <!-- 分辨率 -->
            <VChip v-if="context?.meta_info?.resource_pix" variant="elevated" class="me-1 mb-1 text-white bg-red-500">
              {{ context?.meta_info?.resource_pix }}
            </VChip>
            <!-- 音频编码 -->
            <VChip
              v-if="context?.meta_info?.audio_encode"
              variant="elevated"
              class="me-1 mb-1 text-white bg-orange-500"
            >
              {{ context?.meta_info?.audio_encode }}
            </VChip>
            <!-- Atmos：音频的附属属性 -->
            <VChip
              v-if="context?.meta_info?.audio_atmos"
              variant="elevated"
              class="me-1 mb-1 text-white bg-deep-orange-500"
            >
              Atmos
            </VChip>
            <!-- HDR 规格：视频的附属属性 -->
            <VChip
              v-for="flag in context?.meta_info?.video_hdr || []"
              :key="flag"
              variant="elevated"
              class="me-1 mb-1 text-white bg-teal-500"
            >
              {{ flag }}
            </VChip>
            <!-- 色彩采样：视频的附属属性 -->
            <VChip
              v-if="context?.meta_info?.video_chroma"
              variant="elevated"
              class="me-1 mb-1 text-white bg-teal-500"
            >
              {{ context?.meta_info?.video_chroma }}
            </VChip>
            <!-- 视频编码 -->
            <VChip
              v-if="context?.meta_info?.video_encode"
              variant="elevated"
              class="me-1 mb-1 text-white bg-orange-500"
            >
              {{ context?.meta_info?.video_encode }}
            </VChip>
            <!-- 特殊版本 -->
            <VChip
              v-for="item in context?.meta_info?.special_edition || []"
              :key="item"
              variant="elevated"
              class="me-1 mb-1 text-white bg-purple-500"
            >
              {{ item }}
            </VChip>
            <!-- 剪辑版本 -->
            <VChip
              v-if="context?.meta_info?.cut_version"
              variant="elevated"
              class="me-1 mb-1 text-white bg-indigo-500"
            >
              {{ context?.meta_info?.cut_version }}
            </VChip>
            <!-- 发布信息 -->
            <VChip
              v-for="item in context?.meta_info?.release_info || []"
              :key="item"
              variant="elevated"
              class="me-1 mb-1 text-white bg-cyan-500"
            >
              {{ item }}
            </VChip>
            <VChip v-if="context?.meta_info?.resource_team" variant="elevated" class="me-1 mb-1 text-white bg-cyan-500">
              {{ context?.meta_info?.resource_team }}
            </VChip>
          </VCardItem>
        </div>
      </div>
      <VAlert v-if="!context?.meta_info?.name" icon="mdi-alert-circle-outline"> 识别失败，无法识别到有效信息！ </VAlert>
    </VCol>
    <VExpansionPanels v-show="!isNullOrEmptyObject(context?.meta_info.apply_words)">
      <VExpansionPanel>
        <VExpansionPanelTitle> 识别词应用详情 </VExpansionPanelTitle>
        <VExpansionPanelText>
          <VChip variant="elevated" class="me-1 mb-1 break-all" color="primary">
            {{ context?.meta_info.org_string }}
          </VChip>
          <VChip
            v-for="(val, key) in context?.meta_info.apply_words"
            :key="key"
            :val="val"
            variant="outlined"
            color="info"
            class="me-1 mb-1 break-all"
          >
            {{ val }}
          </VChip>
        </VExpansionPanelText>
      </VExpansionPanel>
    </VExpansionPanels>
  </div>
</template>
