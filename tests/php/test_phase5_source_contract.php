<?php
declare(strict_types=1);

function phase5_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$root = dirname(__DIR__, 2);
$routes = file_get_contents($root . '/appinfo/routes.php');
$controller = file_get_contents($root . '/lib/Controller/EditorController.php');
$service = file_get_contents($root . '/lib/Service/GsbDocumentService.php');
$view = file_get_contents($root . '/src/views/TransactionListView.vue');
$api = file_get_contents($root . '/src/services/gsbApi.js');
$wire = file_get_contents($root . '/src/domain/snapshotWire.mjs');
$editor = file_get_contents($root . '/src/domain/transactionEditor.mjs');
$protocol = file_get_contents($root . '/lib/bin/ncgrisbi/phase5_protocol.py');
$engine = file_get_contents($root . '/lib/bin/ncgrisbi/phase6_engine.py');
$snapshot = file_get_contents($root . '/lib/bin/ncgrisbi/snapshot.py');
$validator = file_get_contents($root . '/lib/bin/ncgrisbi/validator.py');
$writer = file_get_contents($root . '/lib/bin/ncgrisbi/writer.py');

phase5_check(
    str_contains($routes, "'/api/editor/account/{accountId}'"),
    'editor snapshot route is missing'
);
$accountPosition = strpos($controller, 'public function account(');
phase5_check($accountPosition !== false, 'editor controller is missing');
phase5_check(
    !str_contains(substr($controller, max(0, $accountPosition - 220), 220), 'NoCSRFRequired'),
    'editor snapshot bypasses CSRF'
);
phase5_check(str_contains($service, 'LOCK_SHARED'), 'snapshot does not use shared lock');
phase5_check(
    str_contains($api, '@nextcloud/axios') && str_contains($api, 'baseEtag'),
    'Nextcloud axios or ETag contract is missing'
);
phase5_check(str_contains($wire, 'wire.v !== 2'), 'compact snapshot decoder is missing');
phase5_check(str_contains($wire, 'linesPerTransaction'), 'Grisbi display preferences are not decoded');
phase5_check(str_contains($snapshot, '"U": preferences'), 'display preferences are not encoded');
phase5_check(str_contains($snapshot, '"W": warnings'), 'compatibility warnings are not encoded');
phase5_check(str_contains($view, 'DynamicScroller'), 'large transaction lists are not virtualized');
phase5_check(str_contains($view, 'TRANSFER_CATEGORY'), 'transfer selection is missing');
phase5_check(
    str_contains($protocol, 'apply_phase6_operations')
    && !str_contains($protocol, 'for operation_index, raw in enumerate'),
    'protocol still reparses and renders each mutation separately'
);
phase5_check(str_contains($engine, 'setTransactionMarks'), 'quick mark mutation is missing');
phase5_check(str_contains($engine, 'convertTransactionToTransfer'), 'normal-to-transfer conversion is missing');
phase5_check(str_contains($engine, 'convertTransferToTransaction'), 'transfer-to-normal conversion is missing');
phase5_check(str_contains($engine, 'allowReconciled'), 'reconciled transfer confirmation is missing');
phase5_check(str_contains($writer, 'replace_attribute'), 'attribute-level Ma patching is missing');
phase5_check(str_contains($editor, "type: 'setTransactionMarks'"), 'frontend does not batch quick marks');
phase5_check(
    str_contains($view, '!row.quickMarkable')
    && !str_contains($view, ':disabled="!isEditable(row)" @change="row.marked'),
    'marked checkbox still requires full edit mode'
);
phase5_check(
    str_contains($validator, '_collect_unique(root, "Payment", "Number"'),
    'payment IDs are not validated globally like Grisbi'
);
phase5_check(str_contains($validator, 'severity="warning"'), 'damaged transfer links remain fatal');
phase5_check(!str_contains($view, '/api/savetransaction'), 'frontend still calls legacy writer');
phase5_check(
    !str_contains($view, "'Trt'") && !str_contains($view, "'Ac'"),
    'frontend constructs raw GSB attributes'
);
phase5_check(str_contains($view, 'etag-conflict'), 'ETag conflicts are not handled');

 echo "phase6 source contract tests passed\n";
