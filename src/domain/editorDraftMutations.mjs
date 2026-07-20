export function setDraftMarked(draft, checked) {
  Object.assign(draft, { marked: checked ? 1 : 0 })
}

export function resetCategoryDependentFields(draft) {
  Object.assign(draft, {
    subcategoryName: '',
    subcategorySelectionId: null,
    transferAccountSelectionId: null,
    transferPaymentMethodName: '',
    transferPaymentMethodSelectionId: null,
  })
}

export function resetTransferPaymentFields(draft) {
  Object.assign(draft, {
    transferPaymentMethodName: '',
    transferPaymentMethodSelectionId: null,
  })
}

function cloneDraft(source) {
  if (typeof structuredClone === 'function') return structuredClone(source)
  return JSON.parse(JSON.stringify(source))
}

export function syncEditorDraft(target, source) {
  const copy = cloneDraft(source)
  for (const key of Object.keys(target)) {
    if (!(key in copy)) delete target[key]
  }
  Object.assign(target, copy)
}
