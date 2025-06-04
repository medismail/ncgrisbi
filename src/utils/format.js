// src/utils/format.js

export function formatCurrency(amount, currency, lang_code) {
  const formatted = new Intl.NumberFormat(lang_code, {
    style: 'currency',
    currency: currency
  }).format(amount)

  return {
    formatted,
    color: amount >= 0 ? 'green' : 'red'
  }
}

export function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString()
}
