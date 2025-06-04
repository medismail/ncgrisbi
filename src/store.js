import { createStore } from 'vuex'

const store = createStore({
  state: {
    accounts: [],
    filePath: '',
    filePassword: '',
    isEncrypted: false
  },
  mutations: {
    setAccounts(state, accounts) {
      state.accounts = accounts
    },
    setFilePath(state, filePath) {
      state.filePath = filePath
    },
    setFilePassword(state, filePassword) {
      state.filePassword = filePassword
    },
    setEncrypted(state, encrypted) {
      state.isEncrypted = encrypted
    }
  },
  actions: {
    async fetchAccounts({ commit, state }) {
      if (!state.filePath) {
        console.error('File path is required')
        return
      }

      //const jsonData = '{"filePath":"' + state.filePath + '","filePassword":"' + state.filePassword + '"}'
      const data = { filePath: state.filePath, filePassword: state.filePassword }
      const jsonData = JSON.stringify(data)
      const requestOptions = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: jsonData
      }

      try {
        const response = await fetch('/apps/ncgrisbi/api/accounts', requestOptions)
        const accounts = await response.json()
        commit('setAccounts', accounts)
      } catch (error) {
        console.error('Failed to fetch accounts:', error)
      }
    },
    async checkPassword({ commit, state }) {
      if (!state.filePath) {
        console.error('File path is required')
        return
      }
      try {
        const response = await fetch('/apps/ncgrisbi/api/checkencrypted?filePath='+state.filePath)
        const status = await response.json()
        const encrypted = status.Encrypted == "True"
        commit('setEncrypted', encrypted)
      } catch (error) {
        console.error('Failed to check password:', error)
      }
    }
  }
})

export default store
