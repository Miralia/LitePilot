export const responsiveInputCoreComponentNames = [
  'VAutocomplete',
  'VCheckbox',
  'VCombobox',
  'VRadioGroup',
  'VSelect',
  'VSlider',
  'VSwitch',
  'VTextarea',
  'VTextField',
] as const

export const responsiveInputComponentNames = responsiveInputCoreComponentNames

export type ResponsiveInputComponentName = (typeof responsiveInputComponentNames)[number]
