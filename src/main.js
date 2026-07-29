// src/main.js
import { createApp } from 'vue'
import '@nextcloud/dialogs/style.css'
import App from './App.vue'
import router from './router'
import store from './store'
import './styles/phase8a-responsive.css'

// Create Vue app
const app = createApp(App)

// Register global components
app.use(router)
app.use(store)

// Mount app
app.mount('#content')
