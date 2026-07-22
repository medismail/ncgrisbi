<?php
declare(strict_types=1);

function phase8a_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$root = dirname(__DIR__, 2);
$view = file_get_contents($root . '/src/views/TransactionListView.vue');
$panel = file_get_contents($root . '/src/components/transactions/TransactionEditorPanel.vue');
$autocomplete = file_get_contents($root . '/src/components/transactions/TransactionAutocomplete.vue');
$domain = file_get_contents($root . '/src/domain/responsiveEditor.mjs');
$draftMutations = file_get_contents($root . '/src/domain/editorDraftMutations.mjs');
$order = file_get_contents($root . '/src/domain/transactionOrdering.mjs');
$search = file_get_contents($root . '/src/domain/transactionSearch.mjs');

phase8a_check(str_contains($view, 'DynamicScroller'), 'responsive list lost virtual scrolling');
phase8a_check(str_contains($view, 'TransactionEditorPanel'), 'single responsive editor is missing');
phase8a_check(str_contains($view, 'v-model:draft="editorDraft"'), 'editor draft does not use Vue two-way binding');
phase8a_check(str_contains($view, 'class="action-menu"'), 'compact transaction action menu is missing');
phase8a_check(str_contains($view, "runAction('add'"), 'action menu does not add transactions');
phase8a_check(str_contains($view, "runAction('search'"), 'action menu does not open transaction search');
phase8a_check(str_contains($view, "runAction('save'"), 'action menu does not save transactions');
phase8a_check(str_contains($view, "runAction('discard'"), 'action menu does not discard transactions');
phase8a_check(str_contains($view, 'class="search-popover"'), 'transaction search field is missing');
phase8a_check(str_contains($view, 'matchesTransactionSearch(row, searchQuery.value)'), 'transaction rows are not filtered locally');
phase8a_check(str_contains($search, "'partyName'") && str_contains($search, "'note'"), 'search does not cover party and note');
phase8a_check(str_contains($search, "'paymentReference'") && str_contains($search, "'bankReference'"), 'search does not cover references');
phase8a_check(str_contains($view, 'mobileDate(row.date)'), 'mobile compact date is missing');
phase8a_check(str_contains($view, 'min-width: 12ch'), 'mobile party minimum width is missing');
phase8a_check(str_contains($view, "'category category category status actions actions'"), 'mobile detail ordering is not category, status, actions');
phase8a_check(str_contains($view, 'class="row-action-button"'), 'compact row action icons are missing');
phase8a_check(str_contains($view, 'aria-label="`Edit transaction'), 'edit icon is not accessible');
phase8a_check(str_contains($view, 'aria-label="`Delete transaction'), 'delete icon is not accessible');
phase8a_check(str_contains($view, 'class="display-toggle"'), 'one-click compact/detail switch is missing');
phase8a_check(str_contains($view, 'function toggleDisplayMode()'), 'compact/detail switch behavior is missing');
phase8a_check(!str_contains($view, '<option value="compact">Compact</option>'), 'old compact/detail dropdown remains');
phase8a_check(!str_contains($view, '.action-popover { position: fixed'), 'mobile action list is detached from the plus button');
phase8a_check(!str_contains($view, "if (row.isTransfer) return 'Transfer'"), 'transfer is still exposed as a transaction status');
phase8a_check(str_contains($view, "return 'Saved'"), 'saved transaction status is missing');
phase8a_check(str_contains($view, 'padding-inline: 33px'), 'Nextcloud navigation clearance padding was lost');
$notePosition = strpos($view, '<span v-if="row.note" class="detail-note">');
$paymentPosition = strpos($view, '<span v-if="row.paymentMethodName">');
phase8a_check($notePosition !== false && $paymentPosition !== false && $notePosition < $paymentPosition, 'detail line does not start with note when available');
phase8a_check(!str_contains($view, 'class="mobile-add"'), 'old single-purpose mobile add button remains');

phase8a_check(str_contains($view, 'sortTransactionsRecentFirst(rows.value)'), 'UI-82 recent-first ordering is missing');
phase8a_check(str_contains($order, 'dateDifference') && str_contains($order, 'compareIntegerTextDesc'), 'UI-82 does not sort date then transaction number');
phase8a_check(str_contains($view, 'const orderedRows = computed'), 'UI-82 ordering is not cached separately from filtering');

phase8a_check(str_contains($view, 'remain preserved in this browser'), 'UI-97 ETag conflict does not explicitly preserve drafts');
phase8a_check(str_contains($view, 'Reload & discard drafts'), 'UI-98 conflict reload action is not explicit');
phase8a_check(str_contains($view, 'This cannot be undone.'), 'UI-98 discard confirmation is not explicit');
phase8a_check(str_contains($view, 'validationErrorKey'), 'UI-99 validation failure row tracking is missing');
phase8a_check(str_contains($view, 'validation-error'), 'UI-99 validation failure row styling is missing');
phase8a_check(str_contains($view, 'scrollToItem'), 'UI-99 validation failure row is not revealed');
phase8a_check(str_contains($view, 'compatibility-warning'), 'UI-100 compatibility warning indicator is missing');
phase8a_check(str_contains($view, 'compatibilityWarningCount'), 'UI-100 warning count is missing');
phase8a_check(!str_contains($view, 'conflict.value = Boolean(response.snapshot.warnings'), 'UI-100 warnings incorrectly block unrelated editing');

phase8a_check(str_contains($view, "event.key === 'ArrowDown'") && str_contains($view, "event.key === 'ArrowUp'"), 'UI-104 row keyboard navigation is missing');
phase8a_check(str_contains($view, "event.key === 'Home'") && str_contains($view, "event.key === 'End'"), 'UI-104 first/last row keyboard navigation is missing');
phase8a_check(str_contains($view, "event.key === 'Enter'"), 'UI-105 Enter does not open the selected transaction');
phase8a_check(str_contains($view, "event.key !== 'Escape' || !editorDraft.value"), 'UI-106 Escape editor close handling is missing');
phase8a_check(str_contains($view, "event.key === ' ' || event.code === 'Space'"), 'UI-107 Space marked-state toggle is missing');
phase8a_check(str_contains($view, 'selectedRowKey'), 'keyboard-selected row state is missing');
phase8a_check(str_contains($view, ':tabindex="row.key === selectedRowKey ? 0 : -1"'), 'row keyboard focus is not roving');

phase8a_check(str_contains($view, 'pendingChangeSummary'), 'pending transaction summary is missing');
phase8a_check(str_contains($view, 'preferredDisplayMode'), 'Grisbi line preference is not used');
phase8a_check(str_contains($view, "markFilter.value === 'unchecked'"), 'unchecked filter is missing');
phase8a_check(!str_contains($view, 'setTransactionMarks'), 'view constructs raw mark mutations instead of using domain planner');
phase8a_check(str_contains($panel, 'Save draft & add another'), 'multi-entry workflow is missing');
phase8a_check(str_contains($panel, 'Account transfer'), 'dedicated transfer editor is missing');
phase8a_check(str_contains($panel, 'Advanced fields'), 'advanced field disclosure is missing');
phase8a_check(str_contains($panel, 'applyPartyCompletionTrace'), 'traceable party completion is missing');
phase8a_check(!preg_match('/props\.draft\.[A-Za-z0-9_]+\s*=/', $panel), 'editor directly assigns to the draft prop');
phase8a_check(!str_contains($panel, 'v-model="draft.'), 'template v-model still mutates the draft prop');
phase8a_check(str_contains($panel, 'v-model="localDraft.'), 'editor does not use a local reactive draft');
phase8a_check(str_contains($panel, "emit('update:draft', clone(value))"), 'local draft is not emitted to pending batch state');
phase8a_check(str_contains($panel, '.editor-backdrop { position: absolute'), 'editor still covers the Nextcloud top bar');
phase8a_check(str_contains($panel, '.panel-footer { display: flex'), 'editor footer is not a single row');
phase8a_check(str_contains($panel, 'setDraftMarked(localDraft'), 'marked-state mutation does not use the local draft');
phase8a_check(str_contains($panel, 'resetCategoryDependentFields(localDraft'), 'category dependent reset does not use the local draft');
phase8a_check(str_contains($panel, 'resetTransferPaymentFields(localDraft'), 'transfer payment reset does not use the local draft');
phase8a_check(str_contains($draftMutations, 'Object.assign(draft'), 'draft mutation domain helpers are missing');
phase8a_check($autocomplete !== false && str_contains($autocomplete, 'role="combobox"'), 'autocomplete accessibility contract is missing');
phase8a_check(str_contains($autocomplete, 'ArrowDown') && str_contains($autocomplete, 'ArrowUp'), 'autocomplete keyboard navigation is missing');
phase8a_check(str_contains($autocomplete, 'recentIds'), 'recent autocomplete ordering is missing');
phase8a_check(str_contains($domain, 'buildResponsiveMutationOperations'), 'responsive batch planner is missing');
phase8a_check(str_contains($domain, 'partySelectionId'), 'exact Grisbi party ID selection is missing');
phase8a_check(str_contains($domain, "operations.push({ type: 'setTransactionMarks', marks })"), 'quick marks are not merged into one batch');
phase8a_check(!str_contains($view, 'setInterval('), 'autosave was enabled before approval');

echo "phase8a responsive UI source contract tests passed\n";
