import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

import { library } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'

import { faSignOutAlt } from '@fortawesome/free-solid-svg-icons'

// Vuetify
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import { createPinia } from 'pinia'

const vuetify = createVuetify({
  components,
  directives,
})

const pinia = createPinia()

library.add(faSignOutAlt)


const app = createApp(App)

app.component('font-awesome-icon', FontAwesomeIcon)

app.use(router)
app.use(vuetify)
app.use(pinia)

app.mount('#app')
