import type { Component } from 'vue'
import { defineAsyncComponent } from 'vue'
import { createVuetify } from 'vuetify'
import { VBtn } from 'vuetify/components/VBtn'
import AppDialog from './AppDialog'
import { createResponsiveInputAdapter } from './AppInput'
import defaults from './defaults'
import { icons } from './icons'
import type { ResponsiveInputComponentName } from './responsiveInputNames'
import theme from './theme'

type ResponsiveInputLoader = () => Promise<Component>
type ResponsiveInputOptions = Parameters<typeof createResponsiveInputAdapter>[1]

const responsiveInputLoaders = {
  VAutocomplete: async () => (await import('vuetify/components/VAutocomplete')).VAutocomplete,
  VCheckbox: async () => (await import('vuetify/components/VCheckbox')).VCheckbox,
  VCombobox: async () => (await import('vuetify/components/VCombobox')).VCombobox,
  VRadioGroup: async () => (await import('vuetify/components/VRadioGroup')).VRadioGroup,
  VSelect: async () => (await import('vuetify/components/VSelect')).VSelect,
  VSlider: async () => (await import('vuetify/components/VSlider')).VSlider,
  VSwitch: async () => (await import('vuetify/components/VSwitch')).VSwitch,
  VTextarea: async () => (await import('vuetify/components/VTextarea')).VTextarea,
  VTextField: async () => (await import('vuetify/components/VTextField')).VTextField,
} satisfies Record<ResponsiveInputComponentName, ResponsiveInputLoader>

const responsiveInputOptions = {
  VAutocomplete: { name: 'Autocomplete', kind: 'field' },
  VCheckbox: { name: 'Checkbox', kind: 'choice' },
  VCombobox: { name: 'Combobox', kind: 'field' },
  VRadioGroup: { name: 'RadioGroup', kind: 'group' },
  VSelect: { name: 'Select', kind: 'field' },
  VSlider: { name: 'Slider', kind: 'range' },
  VSwitch: { name: 'Switch', kind: 'choice' },
  VTextarea: { name: 'Textarea', kind: 'multiline' },
  VTextField: { name: 'TextField', kind: 'field' },
} satisfies Record<ResponsiveInputComponentName, ResponsiveInputOptions>

function createAsyncResponsiveInput(loader: ResponsiveInputLoader, options: ResponsiveInputOptions) {
  return defineAsyncComponent(async () => createResponsiveInputAdapter(await loader(), options))
}

const responsiveInputComponents = {
  VAutocomplete: createAsyncResponsiveInput(responsiveInputLoaders.VAutocomplete, responsiveInputOptions.VAutocomplete),
  VCheckbox: createAsyncResponsiveInput(responsiveInputLoaders.VCheckbox, responsiveInputOptions.VCheckbox),
  VCombobox: createAsyncResponsiveInput(responsiveInputLoaders.VCombobox, responsiveInputOptions.VCombobox),
  VRadioGroup: createAsyncResponsiveInput(responsiveInputLoaders.VRadioGroup, responsiveInputOptions.VRadioGroup),
  VSelect: createAsyncResponsiveInput(responsiveInputLoaders.VSelect, responsiveInputOptions.VSelect),
  VSlider: createAsyncResponsiveInput(responsiveInputLoaders.VSlider, responsiveInputOptions.VSlider),
  VSwitch: createAsyncResponsiveInput(responsiveInputLoaders.VSwitch, responsiveInputOptions.VSwitch),
  VTextarea: createAsyncResponsiveInput(responsiveInputLoaders.VTextarea, responsiveInputOptions.VTextarea),
  VTextField: createAsyncResponsiveInput(responsiveInputLoaders.VTextField, responsiveInputOptions.VTextField),
} satisfies Record<ResponsiveInputComponentName, Component>

/** 预载全局录入控件模块，降低首次进入设置页时的异步渲染延迟。 */
export async function preloadResponsiveInputComponents() {
  await Promise.all(Object.values(responsiveInputLoaders).map(loader => loader()))
}

export default createVuetify({
  aliases: {
    IconBtn: VBtn,
  },
  defaults,
  icons,
  theme,
  components: {
    VDialog: AppDialog,
    ...responsiveInputComponents,
  },
})
