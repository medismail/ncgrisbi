// src/router.js
import { createRouter, createWebHistory } from 'vue-router'
//import { generateUrl, getRootUrl } from '@nextcloud/router'
import { generateUrl } from '@nextcloud/router'
import HistoryView from './views/HistoryView.vue'
import PasswordEnterView from './views/PasswordEnterView.vue'
import AccountListView from './views/AccountListView.vue'
import AccountOverview from './views/AccountOverview.vue'
import TransactionList from './views/TransactionListView.vue'

const baseUrl = generateUrl('/apps/ncgrisbi/')
/*const webRootWithIndexPHP = getRootUrl() + '/index.php'
const doesURLContainIndexPHP = window.location.pathname.startsWith(webRootWithIndexPHP)
const currentBaseUrl = doesURLContainIndexPHP ? baseUrl : baseUrl.replace('/index.php/', '/')*/

const routes = [
  {
    path: '/',
    name: 'History',
    component: HistoryView
  },
  {
    path: '/typepass',
    name: 'Password',
    component: PasswordEnterView
  },
  {
    path: '/accounts',
    name: 'List',
    component: AccountListView,
    children: [
      {
        path: '',
        name: 'Accounts',
        component: AccountOverview,
      },
      {
        path: '/account/:id',
        name: 'Account',
        component: TransactionList,
        props: true
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(baseUrl),
  linkActiveClass: 'active',
  routes
})

export default router
