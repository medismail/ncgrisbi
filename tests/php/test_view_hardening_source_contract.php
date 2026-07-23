<?php
declare(strict_types=1);

function view_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$root = dirname(__DIR__, 2);
$store = file_get_contents($root . '/src/store.js');
$service = file_get_contents($root . '/src/services/gsbApi.js');
$accountShell = file_get_contents($root . '/src/views/AccountListView.vue');
$overview = file_get_contents($root . '/src/views/AccountOverview.vue');
$password = file_get_contents($root . '/src/views/PasswordEnterView.vue');
$history = file_get_contents($root . '/src/views/HistoryView.vue');
$transactions = file_get_contents($root . '/src/views/TransactionListView.vue');
$editor = file_get_contents($root . '/src/components/transactions/TransactionEditorPanel.vue');
$autocomplete = file_get_contents($root . '/src/components/transactions/TransactionAutocomplete.vue');

view_check(str_contains($store, 'transactionPending'), 'shared pending transaction state is missing');
view_check(str_contains($store, 'accountsLoading') && str_contains($store, 'accountsError'), 'account loading/error state is missing');
view_check(str_contains($store, 'validateFilePassword'), 'password validation action is missing');
view_check(str_contains($service, 'export async function fetchAccounts'), 'normalized account API service is missing');
view_check(str_contains($service, 'export async function fetchDocumentState'), 'document state API service is missing');

view_check(!str_contains($accountShell, 'NcAppNavigationNew'), 'non-functional Add account control remains');
view_check(str_contains($accountShell, 'pendingDiscardPrompt'), 'Close File does not protect pending drafts');
view_check(str_contains($accountShell, 'NcLoadingIcon') && str_contains($accountShell, 'accountError'), 'account shell loading/error UI is missing');
view_check(str_contains($accountShell, 'Accounts overview'), 'account overview navigation entry is missing');

view_check(str_contains($overview, '<RouterLink'), 'account cards are not navigable');
view_check(str_contains($overview, 'Difference'), 'account checked difference is missing');
view_check(str_contains($overview, 'currencyTotals'), 'currency summary cards are missing');
view_check(!str_contains($overview, 'Math.round(account.total'), 'negative balance styling still rounds values');

view_check(str_contains($password, "store.dispatch('validateFilePassword'"), 'password is not validated before navigation');
view_check(str_contains($password, 'submitting'), 'password loading state is missing');
view_check(str_contains($password, 'password-error'), 'password error feedback is missing');
view_check(!str_contains($password, 'Password placeholder'), 'placeholder copy remains on password screen');

view_check(str_contains($history, 'return Array.isArray(parsed)'), 'history parser does not guarantee an array');
view_check(str_contains($history, 'openedAt'), 'recent history ordering timestamp is missing');
view_check(str_contains($history, 'Remove from history'), 'history action still implies file deletion');
view_check(str_contains($history, 'Open Nextcloud Files'), 'history empty guidance is missing');
view_check(str_contains($history, ':key="historyFile.name"'), 'history entries are not keyed by full path');

view_check(str_contains($transactions, 'NcPopover'), 'compatibility warnings do not use a Nextcloud popover');
view_check(str_contains($transactions, 'compatibility-popover'), 'compatibility warning content is missing');
view_check(str_contains($transactions, "window.addEventListener('beforeunload'"), 'browser draft-loss guard is missing');
view_check(str_contains($transactions, 'onBeforeRouteLeave'), 'route draft-loss guard is missing');
view_check(str_contains($transactions, "store.commit('setTransactionPending'"), 'transaction view does not publish pending state');

view_check(str_contains($editor, 'fieldError'), 'field-level editor error state is missing');
view_check(str_contains($editor, 'focusInvalidField'), 'invalid transaction field is not focused');
view_check(str_contains($editor, ':aria-invalid="fieldInvalid'), 'native transaction fields lack aria-invalid');
view_check(str_contains($editor, ':error="fieldInvalid'), 'autocomplete fields do not receive validation state');
view_check(str_contains($autocomplete, 'errorMessage'), 'autocomplete error message support is missing');
view_check(str_contains($autocomplete, "defineExpose({ focus })"), 'autocomplete cannot be focused after validation');

echo "view hardening source contract tests passed\n";
