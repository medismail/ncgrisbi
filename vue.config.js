// vue.config.js
module.exports = {
  publicPath: './',
  outputDir: './dist/',
  indexPath: 'templates/main.php',
  configureWebpack: {
    entry: {
      app: './src/main.js'
    },
    resolve: {
      fallback: {
        "path": require.resolve("path-browserify")
      }
    }
  },
  devServer: {
    port: 8081,
    proxy: {
      '/api': {
        target: 'http://localhost/nextcloud',
        changeOrigin: true,
        pathRewrite: { '^/api': '/index.php/apps/ncgrisbi/api' }
      }
    }
  },
  filenameHashing: false, //  Disable filename hashing
  css: {
    extract: true // Ensure CSS is extracted to separate files
  }
}
