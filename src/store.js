import { createStore } from 'vuex'
import {
  apiError,
  fetchAccounts as fetchAccountsRequest,
  fetchDocumentState,
} from './services/gsbApi'

const emptyPendingState = () => ({
  active: false,
  total: 0,
  description: '',
})

const store = createStore({
  state: {
    accounts: [],
    accountsLoading: false,
    accountsError: null,
    filePath: '',
    filePassword: '',
    isEncrypted: false,
    transactionPending: emptyPendingState(),
  },
  mutations: {
    setAccounts(state, accounts) {
      state.accounts = Array.isArray(accounts) ? accounts : []
    },
    setAccountsLoading(state, loading) {
      state.accountsLoading = Boolean(loading)
    },
    setAccountsError(state, error) {
      state.accountsError = error ?? null
    },
    setFilePath(state, filePath) {
      state.filePath = filePath
    },
    setFilePassword(state, filePassword) {
      state.filePassword = filePassword
    },
    setEncrypted(state, encrypted) {
      state.isEncrypted = encrypted
    },
    setTransactionPending(state, pending) {
      state.transactionPending = {
        active: Boolean(pending?.active),
        total: Number(pending?.total ?? 0),
        description: String(pending?.description ?? ''),
      }
    },
    clearFileSession(state) {
      state.accounts = []
      state.accountsLoading = false
      state.accountsError = null
      state.filePath = ''
      state.filePassword = ''
      state.isEncrypted = false
      state.transactionPending = emptyPendingState()
    },
  },
  actions: {
    async fetchAccounts({ commit, state }, options = {}) {
      if (!state.filePath) {
        const error = new Error('Select a Grisbi file before loading accounts.')
        commit('setAccountsError', apiError(error))
        throw error
      }

      commit('setAccountsLoading', true)
      commit('setAccountsError', null)
      try {
        const password = options.filePassword ?? state.filePassword
        const accounts = await fetchAccountsRequest({
          filePath: state.filePath,
          filePassword: password,
        })
        commit('setAccounts', accounts)
        if (options.commitPassword) commit('setFilePassword', password)
        return accounts
      } catch (error) {
        commit('setAccounts', [])
        commit('setAccountsError', apiError(error))
        throw error
      } finally {
        commit('setAccountsLoading', false)
      }
    },
    async checkPassword({ commit, state }) {
      if (!state.filePath) {
        const error = new Error('Select a Grisbi file before checking encryption.')
        commit('setAccountsError', apiError(error))
        throw error
      }
      try {
        const document = await fetchDocumentState({ filePath: state.filePath })
        commit('setEncrypted', document.encrypted)
        return document
      } catch (error) {
        commit('setAccountsError', apiError(error))
        throw error
      }
    },
    async validateFilePassword({ dispatch }, password) {
      return dispatch('fetchAccounts', {
        filePassword: String(password ?? ''),
        commitPassword: true,
      })
    },
  },
})

export default store
