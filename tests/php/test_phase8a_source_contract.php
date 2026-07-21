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

phase8a_check(str_contains($view, 'DynamicScroller'), 'responsive list lost virtual scrolling');
phase8a_check(str_contains($view, 'TransactionEditorPanel'), 'single responsive editor is missing');
phase8a_check(str_contains($view, 'v-model:draft="editorDraft"'), 'editor draft does not use Vue two-way binding');
phase8a_check(str_contains($view, 'class="action-menu"'), 'compact add/save/discard action menu is missing');
phase8a_check(str_contains($view, "runAction('add'"), 'action menu does not add transactions');
phase8a_check(str_contains($view, "runAction('save'"), 'action menu does not save transactions');
phase8a_check(str_contains($view, "runAction('discard'"), 'action menu does not discard transactions');
phase8a_check(str_contains($view, 'mobileDate(row.date)'), 'mobile compact date is missing');
phase8a_check(str_contains($view, 'minmax(12ch, 1fr)'), 'mobile party minimum width is missing');
phase8a_check(str_contains($view, 'class="detail-status"'), 'mobile detailed status is missing');
phase8a_check(!str_contains($view, 'class="mobile-add"'), 'old single-purpose mobile add button remains');
phase8a_check(str_contains($view, 'pendingChangeSummary'), 'pending transaction summary is missing');
phase8a_check(str_contains($view, 'preferredDisplayMode'), 'Grisbi line preference is not used');
phase8a_check(str_contains($view, '<option value="compact">Compact</option>'), 'manual compact mode is missing');
phase8a_check(str_contains($view, '<option value="detailed">Detailed</option>'), 'manual detailed mode is missing');
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
