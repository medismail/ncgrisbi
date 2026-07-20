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
phase8a_check(str_contains($view, 'mobile-add'), 'mobile add control is missing');
phase8a_check(str_contains($view, 'Save all to file'), 'global batch save is not explicit');
phase8a_check(str_contains($view, 'pendingChangeSummary'), 'pending transaction summary is missing');
phase8a_check(str_contains($view, 'preferredDisplayMode'), 'Grisbi line preference is not used');
phase8a_check(str_contains($view, "displayMode === 'compact'"), 'manual compact mode is missing');
phase8a_check(str_contains($view, "displayMode === 'detailed'"), 'manual detailed mode is missing');
phase8a_check(str_contains($view, "markFilter.value === 'unchecked'"), 'unchecked filter is missing');
phase8a_check(!str_contains($view, 'setTransactionMarks'), 'view constructs raw mark mutations instead of using domain planner');
phase8a_check(str_contains($panel, 'Save draft & add another'), 'multi-entry workflow is missing');
phase8a_check(str_contains($panel, 'Changes stay local'), 'local draft behavior is not explained');
phase8a_check(str_contains($panel, 'Account transfer'), 'dedicated transfer editor is missing');
phase8a_check(str_contains($panel, 'Advanced fields'), 'advanced field disclosure is missing');
phase8a_check(str_contains($panel, 'applyPartyCompletionTrace'), 'traceable party completion is missing');
phase8a_check(!preg_match('/props\.draft\.[A-Za-z0-9_]+\s*=/', $panel), 'editor directly mutates the draft prop');
phase8a_check(str_contains($panel, 'setDraftMarked(props.draft'), 'marked-state mutation is not delegated');
phase8a_check(str_contains($panel, 'resetCategoryDependentFields(props.draft'), 'category dependent reset is not delegated');
phase8a_check(str_contains($panel, 'resetTransferPaymentFields(props.draft'), 'transfer payment reset is not delegated');
phase8a_check(str_contains($draftMutations, 'Object.assign(draft'), 'draft mutation domain helpers are missing');
phase8a_check(str_contains($autocomplete, 'role="combobox"'), 'autocomplete accessibility contract is missing');
phase8a_check(str_contains($autocomplete, 'ArrowDown') && str_contains($autocomplete, 'ArrowUp'), 'autocomplete keyboard navigation is missing');
phase8a_check(str_contains($autocomplete, 'recentIds'), 'recent autocomplete ordering is missing');
phase8a_check(str_contains($domain, 'buildResponsiveMutationOperations'), 'responsive batch planner is missing');
phase8a_check(str_contains($domain, 'partySelectionId'), 'exact Grisbi party ID selection is missing');
phase8a_check(str_contains($domain, "operations.push({ type: 'setTransactionMarks', marks })"), 'quick marks are not merged into one batch');
phase8a_check(!str_contains($view, 'setInterval('), 'autosave was enabled before approval');

echo "phase8a responsive UI source contract tests passed\n";
