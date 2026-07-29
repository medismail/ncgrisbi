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
