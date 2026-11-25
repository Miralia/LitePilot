import type AppDialog from './AppDialog'

declare module 'vue' {
  export interface GlobalComponents {
    VAutocomplete: (typeof import('vuetify/components/VAutocomplete'))['VAutocomplete']
    VCheckbox: (typeof import('vuetify/components/VCheckbox'))['VCheckbox']
    VCombobox: (typeof import('vuetify/components/VCombobox'))['VCombobox']
    VDialog: typeof AppDialog
    VRadioGroup: (typeof import('vuetify/components/VRadioGroup'))['VRadioGroup']
    VSelect: (typeof import('vuetify/components/VSelect'))['VSelect']
    VSlider: (typeof import('vuetify/components/VSlider'))['VSlider']
    VSwitch: (typeof import('vuetify/components/VSwitch'))['VSwitch']
    VTextarea: (typeof import('vuetify/components/VTextarea'))['VTextarea']
    VTextField: (typeof import('vuetify/components/VTextField'))['VTextField']
  }
}

export {}
