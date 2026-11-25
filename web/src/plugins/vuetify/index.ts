import { createVuetify } from 'vuetify'
import { VAutocomplete } from 'vuetify/components/VAutocomplete'
import { VBtn } from 'vuetify/components/VBtn'
import { VCheckbox } from 'vuetify/components/VCheckbox'
import { VCombobox } from 'vuetify/components/VCombobox'
import { VRadioGroup } from 'vuetify/components/VRadioGroup'
import { VSelect } from 'vuetify/components/VSelect'
import { VSlider } from 'vuetify/components/VSlider'
import { VSwitch } from 'vuetify/components/VSwitch'
import { VTextarea } from 'vuetify/components/VTextarea'
import { VTextField } from 'vuetify/components/VTextField'
import AppDialog from './AppDialog'
import { createResponsiveInputAdapter } from './AppInput'
import defaults from './defaults'
import { icons } from './icons'
import type { ResponsiveInputComponentName } from './responsiveInputNames'
import theme from './theme'

const responsiveInputComponents = {
  VAutocomplete: createResponsiveInputAdapter(VAutocomplete, { name: 'Autocomplete', kind: 'field' }),
  VCheckbox: createResponsiveInputAdapter(VCheckbox, { name: 'Checkbox', kind: 'choice' }),
  VCombobox: createResponsiveInputAdapter(VCombobox, { name: 'Combobox', kind: 'field' }),
  VRadioGroup: createResponsiveInputAdapter(VRadioGroup, { name: 'RadioGroup', kind: 'group' }),
  VSelect: createResponsiveInputAdapter(VSelect, { name: 'Select', kind: 'field' }),
  VSlider: createResponsiveInputAdapter(VSlider, { name: 'Slider', kind: 'range' }),
  VSwitch: createResponsiveInputAdapter(VSwitch, { name: 'Switch', kind: 'choice' }),
  VTextarea: createResponsiveInputAdapter(VTextarea, { name: 'Textarea', kind: 'multiline' }),
  VTextField: createResponsiveInputAdapter(VTextField, { name: 'TextField', kind: 'field' }),
} satisfies Record<ResponsiveInputComponentName, ReturnType<typeof createResponsiveInputAdapter>>

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
