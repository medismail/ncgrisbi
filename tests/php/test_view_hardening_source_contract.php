<?php
declare(strict_types=1);

function view_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$root = dirname(__DIR__, 2);
$package = file_get_contents($root . '/package.json');
$main = file_get_contents($root . '/src/main.js');
$store = file_get_contents($root . '/src/store.js');
$service = file_get_contents($root . '/src/services/gsbApi.js');
$accountShell = file_get_contents($root . '/src/views/AccountListView.vue');
$overview = file_get_contents($root . '/src/views/AccountOverview.vue');
$password = file_get_contents($root . '/src/views/PasswordEnterView.vue');
$history = file_get_contents($root . '/src/views/HistoryView.vue');
$transactions = file_get_contents($root . '/src/views/TransactionListView.vue');
$editor = file_get_contents($root . '/src/components/transactions/TransactionEditorPanel.vue');
$autocomplete = file_get_contents($root . '/src/components/transactions/TransactionAutocomplete.vue');
$snapshotWire = file_get_contents($root . '/src/domain/snapshotWire.mjs');
$responsiveEditor = file_get_contents($root . '/src/domain/responsiveEditor.mjs');
$responsiveCss = file_get_contents($root . '/src/styles/phase8a-responsive.css');
$phase5Protocol = file_get_contents($root . '/lib/bin/ncgrisbi/phase5_protocol.py');
$completionHistory = file_get_contents($root . '/lib/bin/ncgrisbi/completion_history.py');

view_check(str_contains($store, 'transactionPending'), 'shared pending transaction state is missing');
view_check(str_contains($store, 'accountsLoading') && str_contains($store, 'accountsError'), 'account loading/error state is missing');
view_check(str_contains($store, 'validateFilePassword'), 'password validation action is missing');
view_check(str_contains($service, 'export async function fetchAccounts'), 'normalized account API service is missing');
view_check(str_contains($service, 'export async function fetchDocumentState'), 'document state API service is missing');
view_check(str_contains($package, '"@nextcloud/dialogs"'), 'Nextcloud toast dependency is missing');
view_check(str_contains($main, "@nextcloud/dialogs/style.css"), 'Nextcloud toast styles are missing');
view_check(str_contains($service, 'showSuccess') && str_contains($service, 'showError'), 'save result toasts are missing');

view_check(!str_contains($accountShell, 'NcAppNavigationNew'), 'non-functional Add account control remains');
view_check(str_contains($accountShell, 'pendingDiscardPrompt'), 'Close File does not protect pending drafts');
view_check(str_contains($accountShell, 'NcLoadingIcon') && str_contains($accountShell, 'accountError'), 'account shell loading/error UI is missing');
view_check(str_contains($accountShell, ":active=\"route.name === 'Accounts'\""), 'account overview navigation is not exact-active');
view_check(str_contains($accountShell, ':allow-collapse="true"'), 'account totals are not collapsible');
view_check(str_contains($accountShell, 'Total:') && str_contains($accountShell, 'Checked:'), 'account navigation totals are incomplete');
view_check(str_contains($accountShell, '<template #description>') || str_contains($accountShell, ':description="accountError.message"'), 'account error empty content has no description');

view_check(str_contains($overview, '<RouterLink'), 'account cards are not navigable');
view_check(str_contains($overview, 'Difference'), 'account checked difference is missing');
view_check(str_contains($overview, 'currencyTotals'), 'currency summary cards are missing');
view_check(!str_contains($overview, 'Math.round(account.total'), 'negative balance styling still rounds values');
view_check(str_contains($overview, 'name="No accounts found"'), 'account empty content name is missing');
view_check(str_contains($overview, '<template #icon>'), 'account empty content icon slot is missing');

view_check(str_contains($password, "store.dispatch('validateFilePassword'"), 'password is not validated before navigation');
view_check(str_contains($password, 'submitting'), 'password loading state is missing');
view_check(str_contains($password, 'password-error'), 'password error feedback is missing');
view_check(!str_contains($password, 'Password placeholder'), 'placeholder copy remains on password screen');

view_check(str_contains($history, 'return Array.isArray(parsed)'), 'history parser does not guarantee an array');
view_check(str_contains($history, 'openedAt'), 'recent history ordering timestamp is missing');
view_check(str_contains($history, 'Remove from history'), 'history action still implies file deletion');
view_check(str_contains($history, 'Open Nextcloud Files'), 'history empty guidance is missing');
view_check(str_contains($history, ':key="historyFile.name"'), 'history entries are not keyed by full path');
view_check(str_contains($history, ':name="historyFiles.length'), 'history empty content name is missing');
view_check(str_contains($history, ':description="historyDescription"'), 'history empty content description is missing');
view_check(str_contains($history, '<template #icon>') && str_contains($history, '<template #action>'), 'history empty content slots are incorrect');
view_check(!str_contains($history, '<template #desc>'), 'obsolete NcEmptyContent desc slot remains');

view_check(str_contains($transactions, 'NcPopover'), 'compatibility warnings do not use a Nextcloud popover');
view_check(str_contains($transactions, 'compatibility-popover'), 'compatibility warning content is missing');
view_check(str_contains($transactions, "window.addEventListener('beforeunload'"), 'browser draft-loss guard is missing');
view_check(str_contains($transactions, 'onBeforeRouteLeave'), 'route draft-loss guard is missing');
view_check(str_contains($transactions, "store.commit('setTransactionPending'"), 'transaction view does not publish pending state');
view_check(str_contains($responsiveCss, ':has(.search-popover)'), 'open search does not reserve header space');
view_check(str_contains($responsiveCss, 'margin-bottom: 56px'), 'search header spacing is too small or missing');

view_check(str_contains($editor, 'fieldError'), 'field-level editor error state is missing');
view_check(str_contains($editor, 'focusInvalidField'), 'invalid transaction field is not focused');
view_check(str_contains($editor, ':aria-invalid="fieldInvalid'), 'native transaction fields lack aria-invalid');
view_check(str_contains($editor, ':error="fieldInvalid'), 'autocomplete fields do not receive validation state');
view_check(str_contains($autocomplete, 'errorMessage'), 'autocomplete error message support is missing');
view_check(str_contains($autocomplete, "defineExpose({ focus })"), 'autocomplete cannot be focused after validation');
view_check(str_contains($autocomplete, 'completionRank'), 'autocomplete does not rank current-account completion first');
view_check(str_contains($autocomplete, 'preferredCompletionPartyId'), 'duplicate payee selection does not resolve to the preferred current-account ID');

view_check(str_contains($snapshotWire, 'sortTransactionsRecentFirst(transactions)'), 'same-account completion is not recent-first');
view_check(str_contains($snapshotWire, 'sourceAccountId: account.id'), 'same-account completion does not override cross-account fallback');
view_check(str_contains($snapshotWire, 'targetPaymentMethodId'), 'transfer counterpart payment is missing from completion hints');
view_check(str_contains($snapshotWire, 'preferredPartyIdByName'), 'duplicate payees are not grouped by visible name');
view_check(str_contains($snapshotWire, 'preferredCompletionPartyId'), 'preferred current-account payee ID is not exposed');
view_check(str_contains($responsiveEditor, 'Exact') === false, 'test wording leaked into production completion code');
view_check(str_contains($responsiveEditor, 'hint.targetPaymentMethodId'), 'exact transfer counterpart payment is not applied');
view_check(str_contains($responsiveEditor, 'row.isNew && row.paymentMethodSelectionId == null'), 'implicit default payment blocks party completion');

view_check(str_contains($phase5Protocol, 'prefer_current_account_history'), 'protocol does not normalize completion history');
view_check(str_contains($completionHistory, 'for transaction in reversed(transactions)'), 'backend completion does not use the last current-account transaction');
view_check(str_contains($completionHistory, 'if party_id in preferred_by_party:'), 'backend does not explicitly prefer current-account history');
view_check(str_contains($completionHistory, 'merged.append(fallback_by_party[party_id])'), 'backend fallback is not limited to missing current-account history');

echo "view hardening source contract tests passed\n";
