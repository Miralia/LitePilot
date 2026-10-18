<script lang="ts" setup>
/**
 * 内置功能配置面板。
 *
 * 三个内置能力（下载文件同步、媒体服务器联动删除、媒体库封面生成）都以
 * SystemConfigKey 保存结构化 JSON，通过 system/setting/{key} 读写。
 * 为了兼容历史布尔值，后端读取时会自动映射，这里只需按对象处理即可。
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'
import { useToast } from 'vue-toastification'

const { t } = useI18n()
const $toast = useToast()

/** 下载文件同步配置 */
interface DownloadFileSyncConf {
  enabled: boolean
  interval_minutes: number
  downloaders: string[]
  max_torrents: number
  prune_missing: boolean
  trigger_throttle_seconds: number
}

/** 媒体服务器联动删除配置 */
interface SyncDelConf {
  enabled: boolean
  servers: string[]
  delete_torrent: boolean
  delete_source_file: boolean
  remove_empty_dirs: boolean
  dry_run: boolean
}

/** 媒体文件技术信息探测配置 */
interface ProbeConf {
  enabled: boolean
  override_resolution: boolean
  override_source: boolean
  log_failure: boolean
}

/** 媒体库封面生成配置 */
interface CoverConf {
  enabled: boolean
  run_hour: number
  libraries: string[]
  width: number
  height: number
  zh_font_size: number
  en_font_size: number
  blur_size: number
  color_ratio: number
}

const conf = ref<DownloadFileSyncConf>({
  enabled: false,
  interval_minutes: 5,
  downloaders: [],
  max_torrents: 200,
  prune_missing: false,
  trigger_throttle_seconds: 30,
})
const delConf = ref<SyncDelConf>({
  enabled: false,
  servers: [],
  delete_torrent: true,
  delete_source_file: false,
  remove_empty_dirs: true,
  dry_run: false,
})
const probeConf = ref<ProbeConf>({
  enabled: true,
  override_resolution: true,
  override_source: true,
  log_failure: false,
})

const coverConf = ref<CoverConf>({
  enabled: false,
  run_hour: 4,
  libraries: [],
  width: 1920,
  height: 1080,
  zh_font_size: 150,
  en_font_size: 62,
  blur_size: 50,
  color_ratio: 0.8,
})

const downloaderOptions = ref<string[]>([])
const serverOptions = ref<string[]>([])
const libraryOptions = ref<string[]>([])
const loading = ref(true)
const saving = ref(false)

/** 读取单个配置，兼容历史布尔值 */
async function loadConf<T>(key: string, fallback: T): Promise<T> {
  const result: { [key: string]: any } = await api.get(`system/setting/${key}`)
  const value = result?.data?.value
  if (value === true) return { ...fallback, enabled: true }
  if (value && typeof value === 'object') return { ...fallback, ...value }
  return fallback
}

/** 载入全部配置与可选项 */
async function loadAll() {
  loading.value = true
  try {
    conf.value = await loadConf('DownloadFileSync', conf.value)
    delConf.value = await loadConf('SyncDelByMediaServer', delConf.value)
    coverConf.value = await loadConf('LibraryCoverGenerator', coverConf.value)
    probeConf.value = await loadConf('MediaInfoProbe', probeConf.value)

    const downloaders: any = await api.get('system/setting/Downloaders')
    downloaderOptions.value = (downloaders?.data?.value ?? []).map((item: any) => item.name)

    const servers: any = await api.get('system/setting/MediaServers')
    serverOptions.value = (servers?.data?.value ?? []).map((item: any) => item.name)

    // 媒体库列表接口需要按服务器查询，逐个取并去重
    const names = new Set<string>()
    for (const server of serverOptions.value) {
      try {
        const libraries: any = await api.get('mediaserver/library', { params: { server } })
        if (Array.isArray(libraries)) {
          libraries.forEach((item: any) => item?.name && names.add(item.name))
        }
      } catch (error) {
        console.log(error)
      }
    }
    libraryOptions.value = Array.from(names)
  } catch (error) {
    console.log(error)
  } finally {
    loading.value = false
  }
}

/** 保存单个配置 */
async function saveConf(key: string, value: unknown): Promise<boolean> {
  const result: { [key: string]: any } = await api.post(`system/setting/${key}`, value)
  return Boolean(result?.success)
}

/** 保存全部内置功能配置 */
async function save() {
  saving.value = true
  try {
    const results = await Promise.all([
      saveConf('DownloadFileSync', conf.value),
      saveConf('SyncDelByMediaServer', delConf.value),
      saveConf('LibraryCoverGenerator', coverConf.value),
      saveConf('MediaInfoProbe', probeConf.value),
    ])
    if (results.every(Boolean)) {
      $toast.success(t('setting.builtin.saveSuccess'))
    } else {
      $toast.error(t('setting.builtin.saveFailed'))
    }
  } catch (error) {
    console.log(error)
    $toast.error(t('setting.builtin.saveFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <VCard variant="tonal" class="mb-4">
    <VCardItem>
      <VCardTitle>{{ t('setting.builtin.downloadSyncTitle') }}</VCardTitle>
      <VCardSubtitle>{{ t('setting.builtin.downloadSyncGuide') }}</VCardSubtitle>
    </VCardItem>
    <VCardText>
      <VRow>
        <VCol cols="12" md="4">
          <VSwitch v-model="conf.enabled" :label="t('setting.builtin.enabled')" hide-details />
        </VCol>
        <VCol cols="12" md="4">
          <VTextField
            v-model.number="conf.interval_minutes"
            type="number"
            min="1"
            :label="t('setting.builtin.intervalMinutes')"
            :hint="t('setting.builtin.intervalMinutesHint')"
            persistent-hint
            :disabled="!conf.enabled"
          />
        </VCol>
        <VCol cols="12" md="4">
          <VTextField
            v-model.number="conf.max_torrents"
            type="number"
            min="0"
            :label="t('setting.builtin.maxTorrents')"
            :hint="t('setting.builtin.maxTorrentsHint')"
            persistent-hint
            :disabled="!conf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VTextField
            v-model.number="conf.trigger_throttle_seconds"
            type="number"
            min="0"
            :label="t('setting.builtin.triggerThrottle')"
            :hint="t('setting.builtin.triggerThrottleHint')"
            persistent-hint
            :disabled="!conf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VSelect
            v-model="conf.downloaders"
            :items="downloaderOptions"
            :label="t('setting.builtin.downloaders')"
            :hint="t('setting.builtin.downloadersHint')"
            persistent-hint
            multiple
            chips
            clearable
            :disabled="!conf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6" class="d-flex align-center">
          <VCheckbox
            v-model="conf.prune_missing"
            :label="t('setting.builtin.pruneMissing')"
            :disabled="!conf.enabled"
            hide-details
          />
        </VCol>
      </VRow>
    </VCardText>
  </VCard>

  <VCard variant="tonal" class="mb-4">
    <VCardItem>
      <VCardTitle>{{ t('setting.builtin.syncDelTitle') }}</VCardTitle>
      <VCardSubtitle>{{ t('setting.builtin.syncDelGuide') }}</VCardSubtitle>
    </VCardItem>
    <VCardText>
      <VRow>
        <VCol cols="12" md="4">
          <VSwitch v-model="delConf.enabled" :label="t('setting.builtin.enabled')" hide-details />
        </VCol>
        <VCol cols="12" md="8">
          <VSelect
            v-model="delConf.servers"
            :items="serverOptions"
            :label="t('setting.builtin.servers')"
            :hint="t('setting.builtin.serversHint')"
            persistent-hint
            multiple
            chips
            clearable
            :disabled="!delConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VCheckbox
            v-model="delConf.delete_torrent"
            :label="t('setting.builtin.deleteTorrent')"
            :hint="t('setting.builtin.deleteTorrentHint')"
            persistent-hint
            :disabled="!delConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VCheckbox
            v-model="delConf.delete_source_file"
            :label="t('setting.builtin.deleteSourceFile')"
            :hint="t('setting.builtin.deleteSourceFileHint')"
            persistent-hint
            :disabled="!delConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VCheckbox
            v-model="delConf.remove_empty_dirs"
            :label="t('setting.builtin.removeEmptyDirs')"
            :disabled="!delConf.enabled"
            hide-details
          />
        </VCol>
        <VCol cols="12" md="6">
          <VCheckbox
            v-model="delConf.dry_run"
            :label="t('setting.builtin.dryRun')"
            :hint="t('setting.builtin.dryRunHint')"
            persistent-hint
            :disabled="!delConf.enabled"
          />
        </VCol>
      </VRow>
    </VCardText>
  </VCard>

  <VCard variant="tonal" class="mb-4">
    <VCardItem>
      <VCardTitle>{{ t('setting.builtin.probeTitle') }}</VCardTitle>
      <VCardSubtitle>{{ t('setting.builtin.probeGuide') }}</VCardSubtitle>
    </VCardItem>
    <VCardText>
      <VRow>
        <VCol cols="12" md="3">
          <VSwitch v-model="probeConf.enabled" :label="t('setting.builtin.enabled')" hide-details />
        </VCol>
        <VCol cols="12" md="9">
          <VCheckbox
            v-model="probeConf.override_resolution"
            :label="t('setting.builtin.overrideResolution')"
            :hint="t('setting.builtin.overrideResolutionHint')"
            persistent-hint
            :disabled="!probeConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VCheckbox
            v-model="probeConf.override_source"
            :label="t('setting.builtin.overrideSource')"
            :hint="t('setting.builtin.overrideSourceHint')"
            persistent-hint
            :disabled="!probeConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VCheckbox
            v-model="probeConf.log_failure"
            :label="t('setting.builtin.logFailure')"
            :disabled="!probeConf.enabled"
            hide-details
          />
        </VCol>
      </VRow>
    </VCardText>
  </VCard>

  <VCard variant="tonal">
    <VCardItem>
      <VCardTitle>{{ t('setting.builtin.coverTitle') }}</VCardTitle>
      <VCardSubtitle>{{ t('setting.builtin.coverGuide') }}</VCardSubtitle>
    </VCardItem>
    <VCardText>
      <VRow>
        <VCol cols="12" md="3">
          <VSwitch v-model="coverConf.enabled" :label="t('setting.builtin.enabled')" hide-details />
        </VCol>
        <VCol cols="12" md="3">
          <VTextField
            v-model.number="coverConf.run_hour"
            type="number"
            min="0"
            max="23"
            :label="t('setting.builtin.runHour')"
            :hint="t('setting.builtin.runHourHint')"
            persistent-hint
            :disabled="!coverConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="6">
          <VSelect
            v-model="coverConf.libraries"
            :items="libraryOptions"
            :label="t('setting.builtin.libraries')"
            :hint="t('setting.builtin.librariesHint')"
            persistent-hint
            multiple
            chips
            clearable
            :disabled="!coverConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="3">
          <VTextField
            v-model.number="coverConf.width"
            type="number"
            min="320"
            :label="t('setting.builtin.width')"
            :disabled="!coverConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="3">
          <VTextField
            v-model.number="coverConf.height"
            type="number"
            min="180"
            :label="t('setting.builtin.height')"
            :disabled="!coverConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="3">
          <VTextField
            v-model.number="coverConf.zh_font_size"
            type="number"
            min="10"
            :label="t('setting.builtin.zhFontSize')"
            :disabled="!coverConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="3">
          <VTextField
            v-model.number="coverConf.en_font_size"
            type="number"
            min="8"
            :label="t('setting.builtin.enFontSize')"
            :disabled="!coverConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="3">
          <VTextField
            v-model.number="coverConf.blur_size"
            type="number"
            min="0"
            :label="t('setting.builtin.blurSize')"
            :disabled="!coverConf.enabled"
          />
        </VCol>
        <VCol cols="12" md="3">
          <VSlider
            v-model.number="coverConf.color_ratio"
            :label="t('setting.builtin.colorRatio')"
            :min="0"
            :max="1"
            :step="0.05"
            thumb-label
            hide-details
            :disabled="!coverConf.enabled"
          />
        </VCol>
      </VRow>
    </VCardText>
  </VCard>

  <div class="d-flex justify-end mt-4">
    <VBtn :loading="saving" :disabled="loading" color="primary" @click="save">
      {{ t('setting.builtin.save') }}
    </VBtn>
  </div>
</template>
