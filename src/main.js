// src/main.js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'

// Create Vue app
const app = createApp(App)

// Register global components
app.use(router)
app.use(store)

// Mount app
app.mount('#content')
